# Findings — Environment Facts & Gotchas

Verified as of 2026-08-15. Update this file when new facts are learned; keep it current.

## Host

- Hostname: `ai-gpu1`. GPUs: 2x NVIDIA H200 NVL (143 GB each), driver 580.173.02, `nvidia-smi` reports CUDA 13.0 runtime.
- Host `nvcc` toolchain: CUDA **12.0** (`/usr/bin/nvcc`). CUDA pip wheels that install are cu124 builds.
- This repo's data lives at `/splunk-data/v1/Work_RAG-Server-Setup`. The old mount path `/ai-gpu1/v1/Work_RAG-Server-Setup` **no longer exists**.
- History: everything (scripts + venv shebangs) was originally written against `/ai-gpu1/v1/...`. On 2026-08-15 both were fixed: `BASE_DIR` now derives from `__file__`, and all venv shebangs/`activate` scripts were `sed`-rewritten to the `/splunk-data` path. If this box is ever re-mounted elsewhere, rerun that path fix (or rebuild the venv).

## Proxy (required for all network access)

- Squid proxy: `http://192.168.203.2:3128`.
- `proxy_setup.sh` configures it for shell (`~/.bashrc`), apt (`/etc/apt/apt.conf.d/99proxy`), git (`git config --global http.proxy`), and the docker daemon (`/etc/systemd/system/docker.service.d/http-proxy.conf`). `start.sh` exports it for the CLI run.
- Symptoms of the proxy dropping large transfers:
  - docker pull: `short read: expected N bytes but got M: unexpected EOF` or `Service Unavailable` / `Internal Server Error` from `registry-1.docker.io`.
  - HF downloads: `OSError: I/O error: error decoding response body` in `huggingface_hub.file_download.xet_get` (XET backend) after ~25 min.
  - pip: `Tunnel connection failed: 503/500` or "Connection interrupted" (pip resumes).

## The venv

- Master venv: `offline-prep/venv`, Python 3.12.3 (base `/usr/bin/python3`).
- **Shebang fix (done 2026-08-15)**: entry points were broken (`required file not found`) because they pointed at the dead `/ai-gpu1/...` path. All fixed to `/splunk-data/v1/...`; `pip`, `uv`, `hf`, `torchrun`, `uvicorn` run directly now. Invoke with `offline-prep/venv/bin/python3.12` if in doubt. Don't `rm -rf` it.
- Working installs as of Aug 11: torch 2.4.0+cu124, torchvision 0.19.0+cu124, torchaudio 2.4.0+cu124, transformers 4.44.0, vllm 0.6.1.post1 + vllm-flash-attn 2.6.1, flash-attn 2.6.3, llama-cpp-python 0.3.34, sglang 0.3.0, faiss-gpu-cu12 1.14.1.post1, bitsandbytes 0.50.0, docling, deepeval, ragas, langchain, llama-index.
- Unresolved conflict: vllm pins `numpy<2` → 1.26.4, but faiss-gpu-cu12 and scipy 1.18.0 require `numpy>=2`.
- **Fixed 2026-08-15**: scipy downgraded 1.18.0 → **1.13.1** (numpy-1.26-compatible). scipy 1.18.0 crashed on import (`np.long` AttributeError), which broke `sentence_transformers`. Do NOT upgrade numpy past 1.26.4 while vllm 0.6.1.post1 is in use; pin scipy at ≤1.13.x instead. faiss-gpu-cu12 1.14.1.post1 imports OK under numpy 1.26.4.
- The CLI's `install_core_tools()` runs `uv pip install ...`; uv is present in the venv but the `uv` entry point is also broken by the shebang issue.

## Paths / script gotcha

- `offline_prepare_cli.py` `BASE_DIR` is now `Path(__file__).resolve().parent / "offline-prep"` (fixed 2026-08-15; was hardcoded `/ai-gpu1/v1/...`). `PROXY_URL` is still hardcoded at line 18.
- The CLI keeps its own progress in `offline-prep/.state.json` / `.retry_queue.json`. These are **stale** relative to what was installed manually (torch 2.4.0, vllm, flash-attn, sglang, llama-cpp all installed by hand after the CLI marked them failed).

## Docker

- Working images (pulled Aug 10, loaded Aug 11): `ghcr.io/open-webui/open-webui:main`, `milvusdb/milvus:latest`, `pgvector/pgvector:pg16`, `qdrant/qdrant:latest`, `redis:7-alpine`. Saved tars in `offline-prep/docker-images/`. All 5 containers running (as of 2026-08-15); open-webui on :13000, pgvector :15432, qdrant :16333, redis :16379, milvus :19530.
- `vllm/vllm-openai:latest` and `nvidia/cuda:12.8.0-runtime-ubuntu22.04` pulls have never succeeded through the proxy.

## Models (as of Aug 11)

- Embeddings present: `BAAI/bge-small-en-v1.5`, `sentence-transformers/all-MiniLM-L6-v2` (`models/huggingface/`).
- Phi-3: `microsoft/Phi-3-mini-4k-instruct-gguf` q4 + fp16 GGUF present.
- Mistral-7B v0.3: IQ1-IQ3/Q2/Q3/Q5 quant files (~60 GB), **no Q4_K_M**.
- Qwen2.5-7B and Llama-3.2-3B GGUF dirs: metadata only, **no weights**.

## Working patterns

- Reliable pip install through proxy:
  `offline-prep/venv/bin/python3.12 -m pip install <pkg> --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple` (retry/resume works).
- Local wheels already downloaded live in `offline-prep/python-packages/` and `python-packages-cu124/` — install from these when offline: `pip install ./offline-prep/python-packages/<wheel>`.
- HF: `hf download` CLI failed on flag usage in the CLI run; use `huggingface_hub.snapshot_download()` with `proxies={"http": PROXY, "https": PROXY}` (this worked for embeddings/Phi-3). **Set `HF_HUB_DISABLE_XET=1`** — the XET backend dies mid-transfer through the proxy (`xet_get` I/O error). See `scripts/download_models.py`.

## Local services (as of 2026-08-15, for RAG repos)

- `:8001` — embeddings (bge-small, dim 384) via `scripts/services/embed_server.py`
- `:8080` — llama.cpp OpenAI-compatible chat (`scripts/services/llama_chat_server.py`, model via `--model`)
- `:8000` — vLLM API server (`scripts/services/vllm_server.sh <model.gguf>`); vLLM requires a **single-file** GGUF (its loader reads one file; split/multi-part GGUFs are not supported)
- vLLM GGUF invocation: `--load-format gguf --quantization gguf` (verified in 0.6.1.post1 `EngineArgs`)
