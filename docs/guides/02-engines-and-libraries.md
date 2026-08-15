# Guide 02 — Inference Engines & Installed Libraries

> [Back to index](../README.md)

## Engines (Python venv `offline-prep/venv`, Python 3.12.3)

| Package | Version | Role / Notes |
|---|---|---|
| `vllm` | 0.6.1.post1 | OpenAI-compatible server on `:8000` (`qwen2.5:7b-vllm`, ~54 tok/s on H200) |
| `torch` | 2.4.0+cu124 | CUDA runtime; wheels are cu124, host driver reports CUDA 13.0 |
| `llama-cpp-python` | 0.3.34 | wrapped llama.cpp server on `:8080` (`qwen2.5:7b`) |
| `transformers` | 4.44.0 | HF model loading |
| `sglang` | 0.3.0 | installed, not serving currently |
| `flash-attn` | 2.6.3 | attention kernels |
| `bitsandbytes` | 0.50.0 | quantize/dequantize |
| `accelerate` | 1.14.0 | device placement |
| `huggingface_hub` | 0.36.2 | downloads (XET disabled via `HF_HUB_DISABLE_XET=1`) |

## What this engine set can run

From the model catalog ([Guide 05](05-models-catalog.md)), the **mid-2025** engine stack supports:

- **Llama / Llama-3.x** family (incl. Nemotron Super-49B, Ultra-253B) — llama.cpp + vLLM ✅
- **Qwen2.5 / Qwen3** (Qwen2.5-72B, Qwen3-30B-A3B) — llama.cpp (`qwen3moe`) likely, vLLM GGUF for 72B ✅
- **Gemma-3-27B**, **Phi-3**, **Mistral** ✅
- Embeddings: `bge-small-en-v1.5` (dim 384), `MiniLM-L6-v2` ✅

**Not runnable on current engines** (need upgrades — weights are still downloadable, Guide 06):

- **MiniMax-M3** — needs **llama.cpp PR #24523** (`minimax-m3` arch) or vLLM ≥ 0.10
- **Kimi K3** — needs **unsloth llama.cpp fork** (`kimi-k3` arch, KDA attention); mainline no
- **GLM-5.2** — needs **vLLM ≥ 0.23** / SGLang ≥ 0.5.13 / KTransformers (DSA arch)
- **DeepSeek-V4-Flash** — needs new vLLM + `deep_gemm` FP4 kernels

## Library inventory (key ML/data packages — all import-clean)

torch, torchvision, torchaudio, transformers, accelerate, sentence-transformers, vllm, sglang,
flash-attn, triton, bitsandbytes, faiss-gpu, xformers, langchain, llama-index (text-embeddings),
pymilvus, qdrant-client, redis, chromadb, sqlalchemy, psycopg, docling, ragas, deepeval, litellm,
openai, http.client based clients, numpy 1.26.4 (vLLM pin), scipy 1.13.1 (do not upgrade),
pandas, httpx, aiohttp, fastapi, uvicorn, huggingface_hub.

## vLLM patches currently applied (see `docs/findings.md` for detail)

- relaxed vocab assert (`vocab_parallel_embedding.py:381`) for padded GGUF vocabs (152064 vs 151936)
- `pyairports` manual stub so guided-decoding (outlines) works
- GGUF wrapper dir `offline-prep/models/gguf-wrappers/qwen2.5-7b-q4km/` (symlinked `model.gguf` + `config.json`)

**Pins:** numpy must stay 1.26.4 (vLLM), scipy 1.13.1; Prometheus docker tag stays **2.52.0**
(2.53.x SIGBUS-crashes in docker on this host).