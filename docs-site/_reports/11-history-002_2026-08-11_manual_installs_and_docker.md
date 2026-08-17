---
title: "2026-08-11 — Manual Installs, Model Downloads, Docker Load + Healthchecks"
nav_order: 11
---

# 2026-08-11 — Manual Installs, Model Downloads, Docker Load + Healthchecks

## Current status

- Docker: the 5 `.tar` images from Aug 10 were loaded into the daemon; redis/qdrant/pgvector/milvus/open-webui containers started and healthchecked OK (open-webui HTTP 200). Pulls of `vllm/vllm-openai` and `nvidia/cuda:12.8.0-runtime-ubuntu22.04` still fail (proxy; see findings).
- Python: manual `pip` installs into `offline-prep/venv` succeeded for vllm 0.6.1.post1 (+vllm-flash-attn 2.6.1), flash-attn 2.6.3, llama-cpp-python 0.3.34 (built from source), sglang 0.3.0 (from local wheel).
- Known fallout: vllm forced numpy 2.2.6 → 1.26.4; faiss-gpu-cu12 and scipy 1.18.0 want numpy>=2 (conflict unresolved as of this date).
- Models: all three `hf download` GGUF attempts (Llama Q4_K_M, Mistral Q4_K_M, Qwen Q4_K_M) failed with HF XET errors; no new weights landed. Mistral IQ quant files from Aug 10 remain the only LLM weights.

## Docker

`dl_docker.log` (14:29–15:03 UTC):
- `docker load` of all 5 saved tars: open-webui, milvus, pgvector, qdrant, redis — all loaded (`Loaded image: ...`).
- Retried `vllm/vllm-openai:latest` pull → `Service Unavailable` from `registry-1.docker.io`, exit 1.
- Retried `nvidia/cuda:12.8.0-runtime-ubuntu22.04` pull → `Internal Server Error` on manifest HEAD, exit 1.

`dl_docker2.log` (17:21 UTC, retry loop):
- `nvidia/cuda:12.8.0-runtime-ubuntu22.04` got most layers then failed at 5th attempt:
  `short read: expected 2069897886 bytes but got 1986490867: unexpected EOF` — proxy drops large blob downloads.

`docker_health.log` (15:36–15:37 UTC):
- Containers started for redis (PONG), qdrant (healthz passed), pgvector (accepting connections), milvus (started), open-webui (HTTP 200).
- All report `no-healthcheck` in `docker ps`.

## Python installs

- `install_sglang.log` (15:35): `pip install ./offline-prep/python-packages/sglang-0.3.0-py3-none-any.whl` (local wheel) → success.
- `install_llamacpp.log` (15:37–15:57): `pip install llama-cpp-python` (sdist 0.3.34, 71.6 MB) — one "Connection interrupted" during download (resumed). Built a 479 MB wheel, installed OK. No explicit CUDA build flags seen in log.
- `install_vllm.log` (16:29): `pip install vllm==0.6.1.post1` using indexes `https://download.pytorch.org/whl/cu124` + `https://pypi.org/simple`. Installed vllm 0.6.1.post1, vllm-flash-attn 2.6.1, ray, sentencepiece, lm-format-enforcer, mistral-common, etc. **Downgraded numpy to 1.26.4**; pip warned of conflicts with opencv-python, faiss-gpu-cu12, scipy.
- `install_flash.log` (19:00): `pip install flash-attn==2.6.3` — sdist download hit 503/500 from proxy, resumed; built flash-attn from source, installed OK.

## Model downloads (all failed)

`hf download --local-dir ...` for `bartowski/Llama-3.2-3B-Instruct-GGUF`, `bartowski/Mistral-7B-Instruct-v0.3-GGUF`, `Qwen/Qwen2.5-7B-Instruct-GGUF`:

- Each fetched the single Q4_K_M file (~23-25 min at ~1.3-1.5 MB/s) then crashed with:
  `OSError: I/O error: error decoding response body` in `huggingface_hub.file_download.xet_get` (HF XET backend).
- 5 attempts each (`dl_llama.log`, `dl_mistral.log`, `dl_qwen.log`), all rc=1. Only `.cache` + `.lock` files remain in those dirs.
- The CLI script's own last run this morning (main.log tail 06:06–06:36 UTC) also stalled: `torchaudio==2.4.0 (CUDA: True)` install timed out twice against the cu124 index.

## Takeaway

The fast-path manual pattern that works: `offline-prep/venv/bin/python3.12 -m pip install <pkg> --index-url https://download.pytorch.org/whl/cu124 [--extra-index-url https://pypi.org/simple]`, retrying/resuming through the proxy. Large HF (XET) and docker-registry downloads keep failing mid-transfer through the proxy.

