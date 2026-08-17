---
title: "2026-08-10 — Initial Offline Prep Run"
nav_order: 10
---

# 2026-08-10 — Initial Offline Prep Run

## Current status

- First automated run of `offline_prepare_cli.py` on the H200 behind the Squid proxy.
- 43 tasks completed, 15 failed (docker vllm/cuda pulls, CUDA pip wheels, TheBloke GGUF models, initial dify clone).
- All "standard" (non-CUDA) wheels downloaded to `python-packages/`; CUDA/GPU wheels to `python-packages-cu124/`.
- 5 docker images pulled and saved as `.tar`; 4 sample projects cloned.
- 2 embedding models + Phi-3 GGUF downloaded; Qwen/Llama/Mistral GGUF downloads failed this day (retried later).
- Final import check at end of run: 1/14 OK (only huggingface_hub) — CLI left CUDA packages uninstalled. Everything was installed manually the next day (see `002_2026-08-11_manual_installs_and_docker.md`).

## What ran

- `bash start.sh` → bootstraps env (apt, docker, proxy), creates/uses venv, launches CLI in tmux session `offline_prep`.
- CLI config at time of run: proxy `http://192.168.203.2:3128`, `BASE_DIR` pointed at `/ai-gpu1/v1/Work_RAG-Server-Setup/offline-prep` (stale path — see `../findings.md`).
- Task definitions in `offline_prepare_cli.py`: 7 docker images, 8 CUDA pip packages, 20+ std pip packages, 6 HF models, 4 sample projects.

## Docker

Pulled and saved to `docker-images/*.tar`:

| Image | Result |
|-------|--------|
| `ghcr.io/open-webui/open-webui:main` | OK (1.8 GB tar) |
| `pgvector/pgvector:pg16` | OK (156 MB) |
| `milvusdb/milvus:latest` | OK (1.1 GB) |
| `qdrant/qdrant:latest` | OK (76 MB) |
| `redis:7-alpine` | OK (17 MB) |

Failed (Max retries exceeded): `vllm/vllm-openai:latest`, `nvidia/cuda:13.0-runtime-ubuntu22.04` (later retried with `12.8.0` — still failing, see findings).

## Python packages (downloaded as wheels; not installed)

`python-packages/` (standard): accelerate 0.33.0, aiohttp, bitsandbytes 0.43.3, chromadb, deepeval 4.1.7, docling, fastapi, httpx, langchain 1.3.14, langgraph, litellm, llama_index, markdown, numpy 2.5.2, openai, pandas 3.0.5, pdfplumber, pydantic 2.13.4, pymilvus, pypdf, qdrant_client, ragas 0.4.3, redis, scipy 1.18.0, sentence_transformers 3.0.1, sglang 0.3.0, transformers 4.44.0, unstructured, uvicorn.

`python-packages-cu124/`: cupy_cuda12x 13.2.0, cuda_python 13.0.0, pycuda 2024.1, numba 0.60.0, llvmlite, numpy 2.0.2/2.2.6.

Failed downloads (Max retries exceeded): `torch==2.5.0+cu124`, `torchvision`, `torchaudio`, `xformers`, `flash-attn`, `triton`, `vllm==0.6.0+cu124`, `faiss-gpu==1.8.0` — all CUDA-wheel installs via `uv pip install --index-url https://download.pytorch.org/whl/cu124`. Proxy was dropping large cu124 wheels.

## Models

| Model | Result |
|-------|--------|
| `BAAI/bge-small-en-v1.5` | OK (via Python API) |
| `sentence-transformers/all-MiniLM-L6-v2` | OK (via Python API) |
| `microsoft/Phi-3-mini-4k-instruct-gguf` | OK later in day (via API) |
| `TheBloke/Qwen2.5-7B-Instruct-GGUF` | FAIL (retried next day) |
| `TheBloke/Llama-3.2-3B-Instruct-GGUF` | FAIL |
| `TheBloke/Mistral-7B-Instruct-v0.3-GGUF` | FAIL |

`hf download` CLI failed with `Usage: hf download [OPTIONS]...` — CLI/flag incompatibility; fallback to `snapshot_download()` worked for the models that succeeded.

## Sample projects

- `dify` — OK (after 1 retry; clone of `langgenius/dify`)
- `anything-llm` — OK
- `ragflow` — OK
- `lightrag` — OK

All in `offline-prep/sample-projects/`. Copy of dify also exists at repo root `dify/` (untracked).

## Artifacts generated

- `offline-prep/COMPREHENSIVE_REPORT.md` — summary + failed task list
- `offline-prep/failed_tasks.json` / `failed_tasks.log` — failure records
- `offline-prep/import_report.txt` — end-of-run import check (1/14 OK)
- `offline-prep/logs/main.log`, `errors.log`, `download.log`, `debug.log`

## Notes

- `check_connectivity()` via `urllib` to pypi.org OK; all 4 required tools (python, pip, docker, git) present.
- `state.max_retries` raised to 5 for automation; retry waits grow 15s per attempt.
- The state file records `pip_torch==2.4.0`, `vllm==0.6.1.post1`, etc. as failed on this day's tail — these were fixed manually on Aug 11.

## Same-day follow-up (Aug 10 evening)

- Manual (non-CLI) downloads of additional GGUF quantizations for `bartowski/Mistral-7B-Instruct-v0.3-GGUF` (IQ1_S/M, IQ2_XXS/XS/S/M, IQ3_XXS/XS/S/M, Q2_K, Q3_K_S, Q5_K_M — ~60 GB total in `models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/`). No Q4_K_M variant present.
- Qwen and Llama GGUF model dirs contain only metadata (README/LICENSE/.gitattributes); no weights.
- `COMPREHENSIVE_REPORT.md` notes CUDA 13 detected and recommends FP8 quantization + flash-attention-2 for the H200.

