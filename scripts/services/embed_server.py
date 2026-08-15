#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI-compatible embeddings endpoint backed by sentence-transformers."""
import argparse

import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sentence_transformers import SentenceTransformer

app = FastAPI()
model = None
MODEL_ID = "local-embed"


@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}]}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "dim": model.get_sentence_embedding_dimension()}


@app.post("/v1/embeddings")
async def embed(request: Request):
    body = await request.json()
    inputs = body.get("input")
    if isinstance(inputs, str):
        inputs = [inputs]
    emb = model.encode(inputs, normalize_embeddings=True, convert_to_numpy=True)
    emb = np.asarray(emb, dtype="float32")
    data = [{"object": "embedding", "index": i, "embedding": emb[i].tolist()} for i in range(len(inputs))]
    return {"object": "list", "data": data, "model": MODEL_ID, "usage": {"prompt_tokens": 0, "total_tokens": 0}}


@app.exception_handler(Exception)
async def err_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


def main():
    global model
    global MODEL_ID
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Sentence-transformers model name or path")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--model-id", default=None)
    args = ap.parse_args()
    if args.model_id:
        MODEL_ID = args.model_id
    model = SentenceTransformer(args.model)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
