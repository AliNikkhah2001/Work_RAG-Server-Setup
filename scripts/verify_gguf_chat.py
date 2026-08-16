#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify GGUF inference via chat completions (applies the model's embedded
chat template, so thinking-channel models like Gemma-4 work too)."""
import argparse
import json
import time

from llama_cpp import Llama

PROMPT = "Write a single short sentence about what a RAG server is."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--max-tokens", type=int, default=64)
    args = ap.parse_args()

    t0 = time.time()
    m = Llama(model_path=args.model, n_ctx=4096, n_gpu_layers=args.n_gpu_layers, verbose=False)
    load_s = time.time() - t0
    t0 = time.time()
    out = m.create_chat_completion(
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=args.max_tokens, temperature=0.2)
    gen_s = time.time() - t0
    usage = out["usage"]
    text = out["choices"][0]["message"]["content"].strip()
    print(json.dumps({
        "model": args.model,
        "load_s": round(load_s, 2),
        "gen_s": round(gen_s, 2),
        "completion_tokens": usage["completion_tokens"],
        "tok_per_s": round(usage["completion_tokens"] / gen_s, 2) if gen_s else None,
        "sample": text[:300],
    }, indent=2))


if __name__ == "__main__":
    main()