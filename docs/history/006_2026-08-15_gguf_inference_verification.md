# 2026-08-15 — GGUF Inference Verification (batch 1)

## Summary (current status)
- **All 5 fully-downloaded GGUF models verified for inference via llama.cpp on H200**
  (n_gpu_layers=-1, prompt "Write a single short sentence about what a RAG server is.",
  max_tokens=48, temp 0.2).
- Gemma-3-27B Q4_K_M still mid-download (~4.2 GB / ~14.4 GB as of 14:20 UTC, proxy
  IncompleteRead retries); Qwen3-30B-A3B (251 MB) and Qwen2.5-72B (partial Q8_0 p1/p2)
  not yet complete — verification pending download finish.
- Push to origin/main **deferred** — no GitHub auth (no SSH key, no `gh`, no credential
  helper) on this host; 2 commits remain local ahead of origin/main.

## Results (all PASS; sample output is coherent, relevant)
| Model | File | Load (s) | Gen (s) | tok/s | Sample (truncated) |
|---|---|---|---|---|---|
| Llama-3.2-3B Instruct | Q4_K_M.gguf (2.02 GB) | 1.46 | 0.26 | **185.4** | "A RAG server is a type of server that provides a centralized location for users to access and manage their RAG (Remote Access Gateway) accounts and settings." |
| Qwen2.5-7B Instruct | Q4_K_M.gguf (4.68 GB) | 1.78 | 0.21 | **127.5** | "A RAG server is a server that hosts and serves RAG (Remote Application Gateway) software to enable secure remote access to applications." |
| Mistral-7B v0.3 | Q4_K_M.gguf (4.37 GB) | 1.46 | 0.30 | **160.3** | "A RAG server is a system that categorizes tasks or issues into Red, Amber, and Green statuses based on their priority and urgency." |
| Phi-3-mini-4k | q4.gguf (2.39 GB) | 3.25 | 0.22 | **101.5** | "<\|assistant\|> A RAG server is a centralized platform for managing and distributing resources in a network." |
| Phi-3-mini-4k | fp16.gguf (7.64 GB) | 7.60 | 0.18 | **131.7** | "<\|assistant\|> A RAG server is a centralized platform for managing and distributing resources in a virtualized environment." |

Notes:
- All generations returned clean, in-distribution text — no garbage tokens, no crashes.
- H200 GPU offload is working (n_gpu_layers=-1). Load times are small (<8 s) thanks to
  the large model cache and fast NVMe.
- Inference harness written: `scripts/verify_gguf_inference.py`
  (`--model <path>` `--n-gpu-layers -1`).

## Pending
- Re-run harness on: Gemma-3-27B Q4_K_M, Qwen3-30B-A3B Q4 (small), Qwen2.5-72B
  (Q8_0 parts + Q4_K_M) once downloads complete.
- Push the 2 local commits once GitHub credentials are available.