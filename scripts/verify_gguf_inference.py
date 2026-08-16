#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Load each complete GGUF model through llama.cpp and run a short generation
to verify inference works. Reports tokens/sec and a sample of the output."""
import argparse
import json
import sys
import time

from llama_cpp import Llama

PROMPT = "Write a single short sentence about what a RAG server is."


def test_one(path: str, n_gpu_layers: int, n_ctx: int = 2048, max_tokens: int = 48) -> dict:
    t0 = time.time()
    llm = Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=False)
    t_load = time.time() - t0
    t0 = time.time()
    out = llm(PROMPT, max_tokens=max_tokens, temperature=0.2)
    t_gen = time.time() - t0
    text = out["choices"][0]["text"].strip()
    n_tok = out["usage"]["completion_tokens"]
    del llm
    return {
        "model": path,
        "load_s": round(t_load, 2),
        "gen_s": round(t_gen, 2),
        "completion_tokens": n_tok,
        "tok_per_s": round(n_tok / t_gen, 2) if t_gen > 0 else None,
        "sample": text[:200],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="path to .gguf file")
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    args = ap.parse_args()
    print(json.dumps(test_one(args.model, args.n_gpu_layers), indent=2))


if __name__ == "__main__":
    main()