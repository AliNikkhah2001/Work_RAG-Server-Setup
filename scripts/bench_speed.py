#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick tokens/sec benchmark for each GGUF model (single prompt, N tokens)."""
import argparse
import json
import time
from pathlib import Path

from llama_cpp import Llama

MODELS = {
    "gemma-4-31b": "offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf",
    "gemma-3-27b": "offline-prep/models/huggingface/bartowski_google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-Q4_K_M.gguf",
    "qwen3.8-27b": "offline-prep/models/huggingface/bartowski_Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf",
    "qwen3-30b": "offline-prep/models/huggingface/Qwen_Qwen3-30B-A3B-GGUF/Qwen3-30B-A3B-Q4_K_M.gguf",
    "nemotron-49b": "offline-prep/models/huggingface/bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf",
    "qwen2.5-7b": "offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    "llama3.2-3b": "offline-prep/models/huggingface/bartowski_Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    "mistral-7b": "offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
    "phi3-mini": "offline-prep/models/huggingface/microsoft_Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4.gguf",
}

PROMPT = ("سؤال: یک مقاله کوتاه درباره نقش هوش مصنوعی در پزشکی بنویس و در پایان خلاصه کن. "
          "چندین کاربرد شامل تشخیص بیماری، دارورسانی شخصی‌سازی شده، و جراحی رباتیک را شرح بده.")


def bench(path, max_tokens=256):
    llm = Llama(model_path=path, n_ctx=8192, n_gpu_layers=-1, verbose=False)
    t0 = time.time()
    out = llm.create_chat_completion(
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=max_tokens, temperature=0.3)
    dt = time.time() - t0
    toks = out["usage"]["completion_tokens"]
    return {"tokens": toks, "secs": round(dt, 2),
            "tok_sec": round(toks / dt, 1) if dt else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--out", default="logs/speed_bench.json")
    args = ap.parse_args()
    results = {}
    out_path = Path(args.out)
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
        except Exception:
            results = {}
    for name, path in MODELS.items():
        if args.only and args.only != name:
            continue
        if name in results:
            print(f"=== {name} (cached, skipping) ===", flush=True)
            continue
        print(f"=== {name} ===", flush=True)
        try:
            r = bench(path)
            print(f"  {r['tok_sec']} tok/s ({r['tokens']} tokens in {r['secs']}s)", flush=True)
            results[name] = r
        except Exception as e:
            print(f"  ERROR {e}", flush=True)
            results[name] = {"error": str(e)}
        out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()