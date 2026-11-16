#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal OpenAI-compatible chat server backed by llama.cpp (GPU0 fallback)."""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from llama_cpp import Llama

app = FastAPI(title="llama.cpp fallback")
llm: Optional[Llama] = None
MODEL_ID = "gemma-4-31b"
N_CTX = 16384
# ~3 chars/token conservative for Persian+English mix; leave room for generation.
_CHAR_BUDGET_RATIO = float(os.getenv("LLAMA_CHAR_PER_TOKEN", "3.0"))


@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local-llamacpp"}]}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "n_ctx": N_CTX, "backend": "llamacpp"}


def _fit_messages(messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
    """Trim history so prompt + completion fits n_ctx (avoids llama.cpp abort).

    Chat templates add overhead; keep a large safety margin and prefer the
    newest turns (question at the end).
    """
    # ~2.2 chars/token + reserve 25% of window for template/generation.
    usable = max(256, int(N_CTX * 0.55) - max(max_tokens, 1) - 128)
    budget = int(usable * max(2.0, _CHAR_BUDGET_RATIO - 0.5))
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    fitted_sys: List[Dict[str, Any]] = []
    for m in system[:1]:
        content = str(m.get("content", ""))[:2000]
        fitted_sys.append({"role": "system", "content": content})
        budget -= len(content)
    kept: List[Dict[str, Any]] = []
    for m in reversed(rest):
        if budget <= 0:
            break
        content = str(m.get("content", ""))
        if len(content) > budget:
            content = content[-budget:] if not kept else content[:budget]
        kept.append({"role": m.get("role", "user"), "content": content})
        budget -= len(content)
    kept.reverse()
    # Always keep at least the latest user turn.
    if not kept and rest:
        last = rest[-1]
        kept = [{"role": last.get("role", "user"), "content": str(last.get("content", ""))[-4000:]}]
    return fitted_sys + kept


def _completion_body(body: dict) -> dict:
    messages = body.get("messages") or [{"role": "user", "content": body.get("prompt", "")}]
    max_tokens = int(body.get("max_tokens") or 512)
    max_tokens = max(16, min(max_tokens, max(256, N_CTX // 4)))
    temperature = float(body.get("temperature") if body.get("temperature") is not None else 0.7)
    fitted = _fit_messages(messages, max_tokens)
    return {
        "messages": fitted,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop": body.get("stop") or None,
        "stream": bool(body.get("stream")),
    }


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    args = _completion_body(body)
    if args["stream"]:
        def gen():
            stream = llm.create_chat_completion(
                messages=args["messages"],
                max_tokens=args["max_tokens"],
                temperature=args["temperature"],
                stop=args["stop"],
                stream=True,
            )
            for chunk in stream:
                # llama-cpp already returns OpenAI-shaped chunks
                if isinstance(chunk, dict):
                    chunk.setdefault("model", MODEL_ID)
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    out = llm.create_chat_completion(
        messages=args["messages"],
        max_tokens=args["max_tokens"],
        temperature=args["temperature"],
        stop=args["stop"],
    )
    choice = (out.get("choices") or [{}])[0]
    msg = (choice.get("message") or {}).get("content") or ""
    return {
        "id": out.get("id") or "chatcmpl-llamacpp",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": choice.get("finish_reason") or "stop"}],
        "usage": out.get("usage") or {},
    }


@app.post("/v1/completions")
async def complete(request: Request):
    body = await request.json()
    args = _completion_body({**body, "messages": [{"role": "user", "content": body.get("prompt", "")}]})
    out = llm.create_chat_completion(
        messages=args["messages"],
        max_tokens=args["max_tokens"],
        temperature=args["temperature"],
        stop=args["stop"],
    )
    text = ((out.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {
        "id": out.get("id") or "cmpl-llamacpp",
        "object": "text_completion",
        "model": MODEL_ID,
        "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
    }


@app.exception_handler(Exception)
async def err_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


def main():
    global llm, MODEL_ID, N_CTX
    ap = argparse.ArgumentParser(description="llama.cpp OpenAI-compatible fallback server")
    ap.add_argument("--model", required=True, help="Path to GGUF model file")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--n-ctx", type=int, default=16384, help="Context window (GPU0 has headroom)")
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--model-id", default="gemma-4-31b")
    args = ap.parse_args()
    MODEL_ID = args.model_id
    N_CTX = int(args.n_ctx)
    print(f"[llamacpp] loading {args.model} n_ctx={N_CTX} n_gpu_layers={args.n_gpu_layers}", flush=True)
    llm = Llama(
        model_path=args.model,
        n_ctx=N_CTX,
        n_gpu_layers=args.n_gpu_layers,
        verbose=False,
    )
    print(f"[llamacpp] ready on {args.host}:{args.port} model_id={MODEL_ID}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
