#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal OpenAI-compatible chat server backed by llama.cpp."""
import argparse
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from llama_cpp import Llama

app = FastAPI()
llm: Optional[Llama] = None
MODEL_ID = "local-llm"


@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}]}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID}


def _clean_message(msg: dict) -> str:
    content = msg.get("content", "")
    return content


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    prompt = "\n".join(f"<|im_start|>{m.get('role', 'user')}\n{_clean_message(m)}<|im_end|>\n"
                       for m in messages) + "<|im_start|>assistant\n"
    max_tokens = body.get("max_tokens", 256)
    temperature = body.get("temperature", 0.7)
    out = llm(prompt, max_tokens=max_tokens, temperature=temperature, stop=body.get("stop"))
    return {
        "id": "chatcmpl-local",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": out["choices"][0]["text"]},
                     "finish_reason": "stop"}],
    }


@app.post("/v1/completions")
async def complete(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    max_tokens = body.get("max_tokens", 256)
    temperature = body.get("temperature", 0.7)
    out = llm(prompt, max_tokens=max_tokens, temperature=temperature, stop=body.get("stop"))
    return {
        "id": "cmpl-local",
        "object": "text_completion",
        "model": MODEL_ID,
        "choices": [{"index": 0, "text": out["choices"][0]["text"], "finish_reason": "stop"}],
    }


@app.exception_handler(Exception)
async def err_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


def main():
    global llm
    global MODEL_ID
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Path to GGUF model file")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--n-ctx", type=int, default=2048)
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--model-id", default=None)
    args = ap.parse_args()
    if args.model_id:
        MODEL_ID = args.model_id
    llm = Llama(model_path=args.model, n_ctx=args.n_ctx, n_gpu_layers=args.n_gpu_layers, verbose=False)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
