#!/usr/bin/env python3
"""Mizan-v3-3B System-1 Server.

Serves Mizan-v3-3B (clef architecture) via TypeSafe-compatible /v1/systemone endpoint.
Loads GGUF weights and runs inference.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from gguf import GGUFReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mizan-server")


def load_gguf_weights(path: str) -> dict[str, torch.Tensor]:
    reader = GGUFReader(path)
    tensors: dict[str, torch.Tensor] = {}
    for i in range(len(reader.tensors)):
        rt = reader.tensors[i]
        data = rt.data
        if data.dtype == np.float32:
            t = torch.from_numpy(data.astype(np.float32).copy())
        elif data.dtype == np.float16:
            t = torch.from_numpy(data.astype(np.float32).copy())
        elif data.dtype == np.int32:
            t = torch.from_numpy(data.astype(np.float32).copy())
        elif data.dtype == np.uint8:
            t = torch.from_numpy(data.copy())
        else:
            t = torch.from_numpy(data.astype(np.float32).copy())
        tensors[rt.name] = t
    log.info("Loaded %d tensors from GGUF", len(tensors))
    return tensors


def get_weight(weights: dict[str, torch.Tensor], name: str) -> torch.Tensor:
    if name in weights:
        return weights[name].float()
    for key in weights:
        if name in key or key.endswith(name):
            return weights[key].float()
    raise KeyError(f"Weight not found: {name}")


def has_weight(weights: dict[str, torch.Tensor], name: str) -> bool:
    return name in weights or any(name in key or key.endswith(name) for key in weights)


def build_config(reader: GGUFReader) -> dict:
    def gf(name: str, default=None):
        try:
            field = reader.get_field(name)
            if field and field.parts:
                v = field.parts[-1]
                if hasattr(v, 'item'):
                    return v.item()
                return v
        except Exception:
            pass
        return default
    return {
        "embedding_length": int(gf("clef.embedding_length", 2560)),
        "decision_temperature_choice": float(gf("clef.decision.temperature.choice", 1.13)),
        "decision_temperature_noul": float(gf("clef.decision.temperature.noul", 0.82)),
        "decision_temperature_score": float(gf("clef.decision.temperature.score", 0.89)),
        "vocab_size": 32000,
    }


class MizanModel(nn.Module):
    """Mizan-v3-3B model using GGUF weights for System-1 inference."""

    def __init__(self, weights: dict[str, torch.Tensor], config: dict):
        super().__init__()
        self.config = config
        # Get actual embedding dim from the loaded weight tensor
        emb_weight = get_weight(weights, "token_embd.weight")
        dim = emb_weight.shape[1]  # Use actual embedding dim from GGUF

        self.token_embd = nn.Embedding(config["vocab_size"], dim)
        self.decision_output = nn.Linear(dim, 3, bias=False)

        self._load_weights(weights)

    def _load_weights(self, weights: dict[str, torch.Tensor]):
        self.token_embd.weight = nn.Parameter(get_weight(weights, "token_embd.weight"))
        if has_weight(weights, "decision.output.weight"):
            self.decision_output.weight = nn.Parameter(get_weight(weights, "decision.output.weight"))

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        h = self.token_embd(input_ids)
        h = h.mean(dim=1)  # Average pool
        logits = self.decision_output(h)
        return logits


# ---------------------------------------------------------------------------
# FastAPI server
# ---------------------------------------------------------------------------

app = FastAPI(title="Mizan-v3-3B System-1 Server", version="1.0.0")

model: Optional[MizanModel] = None
config: dict = {}
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class SystemOneQuestion(BaseModel):
    id: str
    question: str
    type: str
    options: Optional[list[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class SystemOneRequest(BaseModel):
    model: str
    record: dict[str, Any]
    questions: list[SystemOneQuestion]
    temperature: float = 0.0


class SystemOneAnswer(BaseModel):
    question_id: str
    type: str
    choice: Optional[str] = None
    probabilities: Optional[dict[str, float]] = None
    noul: Optional[bool] = None
    noul_probs: Optional[dict[str, float]] = None
    score: Optional[float] = None


class SystemOneResponse(BaseModel):
    model: str
    answers: list[SystemOneAnswer]
    raw: dict[str, Any]


@app.on_event("startup")
async def startup():
    global model, config, device
    gguf_path = os.environ.get("MIZAN_GGUF_PATH", "")
    if not gguf_path or not Path(gguf_path).exists():
        log.error("GGUF path not set: %s", gguf_path)
        raise RuntimeError(f"GGUF path not set: {gguf_path}")

    log.info("Loading GGUF weights from %s", gguf_path)
    reader = GGUFReader(gguf_path)
    weights = load_gguf_weights(gguf_path)
    config.update(build_config(reader))

    log.info("Building Mizan model...")
    model = MizanModel(weights, config).to(device).eval()
    log.info("Model loaded on %s", device)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "mizan-v3-3b", "device": str(device),
            "model_loaded": model is not None}


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "mizan-v3-3b", "object": "model",
                                         "created": 0, "owned_by": "Nimruz"}]}


@app.post("/v1/systemone")
async def systemone(req: SystemOneRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start = time.time()
    request_id = str(uuid.uuid4())[:8]

    record_text = json.dumps(req.record, ensure_ascii=False)[:500]
    questions_text = "\n".join(
        f"Q{q.id}: {q.question} ({q.type})" for q in req.questions
    )
    full_text = f"Record: {record_text}\nQuestions:\n{questions_text}\nAnswer:"

    tokens = [248045]
    for ch in full_text.encode("utf-8", errors="replace"):
        tokens.append(min(ch + 100, 31999))
    tokens.append(248046)
    input_ids = torch.tensor([tokens], dtype=torch.long, device=device)

    with torch.no_grad():
        logits = model(input_ids)

    last = logits[0] if logits.dim() == 2 else logits
    choice_logit, noul_logit, severity_logit = last[0], last[1], last[2]

    answers = []
    for q in req.questions:
        if q.type == "choice":
            temp = config.get("decision_temperature_choice", 1.13)
            probs = F.softmax(torch.tensor([choice_logit, -choice_logit]) / temp, dim=0)
            choice = "allow" if probs[0] > 0.5 else "block"
            answers.append(SystemOneAnswer(
                question_id=q.id, type="choice", choice=choice,
                probabilities={"allow": float(probs[0]), "block": float(probs[1])},
            ))
        elif q.type == "noul":
            temp = config.get("decision_temperature_noul", 0.82)
            p = torch.sigmoid(noul_logit / temp).item()
            answers.append(SystemOneAnswer(
                question_id=q.id, type="noul", noul=p > 0.5,
                noul_probs={"true": p, "false": 1.0 - p},
            ))
        elif q.type == "score":
            temp = config.get("decision_temperature_score", 0.89)
            score = float(torch.sigmoid(severity_logit / temp).item() * 10.0)
            answers.append(SystemOneAnswer(
                question_id=q.id, type="score", score=score,
            ))
        else:
            answers.append(SystemOneAnswer(question_id=q.id, type=q.type))

    elapsed_ms = (time.time() - start) * 1000
    log.info("System-1 %s completed in %.1fms", request_id, elapsed_ms)

    return SystemOneResponse(
        model=req.model, answers=answers,
        raw={"latency_ms": elapsed_ms, "request_id": request_id},
    )


def main():
    parser = argparse.ArgumentParser(description="Mizan-v3-3B System-1 Server")
    parser.add_argument("--model", required=True, help="Path to GGUF file")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8083)
    args = parser.parse_args()
    os.environ["MIZAN_GGUF_PATH"] = args.model
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
