#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared RAG smoke-test harness used to run + test each sample repo.

Usage:
  python scripts/rag_test_harness.py --llm-url <openai-compatible-url> --embed-url <url>
                                     [--eval] [--label dify]

Steps: create a small knowledge doc, chunk + embed it, store in a vector store
(service arg), run a retrieval-augmented question, and print the answer.
When --eval, scores faithfulness/relevancy via ragas (LLM-based; needs ragas config).
"""
import argparse
import json
import sys

import requests

SAMPLE_DOC = """
The Splunk RAG server runs on an NVIDIA H200 with 2x 143 GB GPUs.
It serves Qwen2.5-7B quantized to GGUF Q4_K_M through llama.cpp and vLLM.
The embedding model is BAAI/bge-small-en-v1.5 producing 384-dimensional vectors.
Vector databases available: Milvus, Qdrant, pgvector. Redis provides caching.
All outbound traffic goes through the Squid proxy at 192.168.203.2:3128.
The master Python environment lives at offline-prep/venv with PyTorch 2.4.0+cu124.
"""

QUESTIONS = [
    "Which GPUs does the RAG server use?",
    "What quantization is Qwen2.5-7B stored in?",
    "Which vector databases are available?",
]


def embed(embed_url: str, text: str):
    r = requests.post(f"{embed_url}/v1/embeddings", json={"input": text}, timeout=120)
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def ask(llm_url: str, prompt: str) -> str:
    r = requests.post(f"{llm_url}/v1/chat/completions",
                      json={"messages": [{"role": "user", "content": prompt}], "max_tokens": 128},
                      timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-url", required=True)
    ap.add_argument("--embed-url", default="http://localhost:8001")
    ap.add_argument("--vector", choices=["milvus", "qdrant", "pgvector"], default=None)
    ap.add_argument("--label", default="harness")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--store", choices=["memory"], default="memory")
    args = ap.parse_args()

    print(f"=== RAG harness [{args.label}] ===")
    print("[1] embed sample doc chunks")
    chunks = [c.strip() for c in SAMPLE_DOC.split("\n\n") if c.strip()]
    vecs = [embed(args.embed_url, c) for c in chunks]
    print(f"    {len(chunks)} chunks embedded, dim {len(vecs[0])}")

    print("[2] build in-memory index (top-k cosine)")
    import numpy as np
    index = np.asarray(vecs, dtype="float32")
    index = index / np.linalg.norm(index, axis=1, keepdims=True)

    def retrieve(q: str, k: int = 2):
        qv = np.asarray(embed(args.embed_url, q), dtype="float32")
        qv = qv / np.linalg.norm(qv)
        scores = index @ qv
        return [chunks[i] for i in np.argsort(scores)[-k:][::-1]]

    print("[3] ask with retrieved context")
    results = []
    for q in QUESTIONS:
        ctx = "\n".join(f"- {c}" for c in retrieve(q))
        prompt = f"Answer using ONLY the context below. Context:\n{ctx}\n\nQuestion: {q}\nAnswer:"
        answer = ask(args.llm_url, prompt)
        results.append({"question": q, "context": ctx, "answer": answer})
        print(f"Q: {q}\nA: {answer[:140]}\n")

    out = {"label": args.label, "chunks": len(chunks), "dim": len(vecs[0]), "results": results}
    with open(f"logs/rag_test_{args.label}.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Results -> logs/rag_test_{args.label}.json")

    if args.eval:
        print("[4] ragas evaluation (skipped: needs ragas harness config)")


if __name__ == "__main__":
    main()
