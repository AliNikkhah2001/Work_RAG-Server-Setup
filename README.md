# Work RAG Server Setup — H200 Offline RAG Dev/Prod Environment

Setup and staging of a **RAG development + production system** on an NVIDIA H200 box behind a corporate Squid proxy. The repo contains the orchestration scripts, service definitions, model/download tooling, and a maintained execution history (`docs/`).

> Status: **P0 done, P1 in progress, P2 partially live, P3–P5 pending.** See [Plan & Progress](#plan--progress).

---

## 1. Hardware & Environment

| Item | Value |
|---|---|
| Hostname | `ai-gpu1` |
| GPUs | 2 × NVIDIA H200 NVL, **143 GB** each |
| Driver | 580.173.02 |
| CUDA runtime (`nvidia-smi`) | 13.0 |
| Host compiler (`nvcc`) | 12.0 |
| Master Python | 3.12.3 (`offline-prep/venv`) |
| Proxy (Squid) | `http://192.168.203.2:3128` |
| Data root | `/splunk-data/v1/Work_RAG-Server-Setup` |
| Docker data root | `/ai-gpu1/v1/docker-data` (separate mount) |
| Disk free | ~5.6 TB |

### Environment variables

All network access goes through the corporate Squid proxy. Set these in every shell/tool:

| Variable | Value |
|---|---|
| `PROXY_URL` | `http://192.168.203.2:3128` |
| `http_proxy` / `https_proxy` | `http://192.168.203.2:3128` |
| `HTTP_PROXY` / `HTTPS_PROXY` | `http://192.168.203.2:3128` |
| `no_proxy` / `NO_PROXY` | `localhost,127.0.0.1,localaddress,.localdomain.com` |

`proxy_setup.sh` configures the proxy for **shell (`~/.bashrc`), APT (`/etc/apt/apt.conf.d/99proxy`), Git (`git config --global http.proxy`) and Docker daemon** (`/etc/systemd/system/docker.service.d/http-proxy.conf`).

**HF downloader** (`scripts/download_models.py`):

| Variable | Value | Why |
|---|---|---|
| `HF_HUB_DISABLE_XET` | `1` | **Critical.** The XET CDN backend dies mid-transfer through the proxy (`xet_get: I/O error`); this forces the plain HTTPS path |
| `HF_HUB_ENABLE_HF_TRANSFER` | `0` | Keep disabled (parallel rust transfer is unreliable through the proxy) |

**`offline_prepare_cli.py` constants** (module-level, all under `BASE_DIR`):

| Constant | Path / Value |
|---|---|
| `PROXY_URL` | `http://192.168.203.2:3128` |
| `BASE_DIR` | `Path(__file__).resolve().parent / "offline-prep"` |
| `VENV_DIR` | `<BASE_DIR>/venv` |
| `STATE_FILE` | `<BASE_DIR>/.state.json` |
| `RETRY_QUEUE` | `<BASE_DIR>/.retry_queue.json` |
| `REPORT_FILE` | `<BASE_DIR>/COMPREHENSIVE_REPORT.md` |
| `LOG_DIR` | `<BASE_DIR>/logs` |
| `PIP_CACHE_DIR` | `<BASE_DIR>/pip_cache` |
| `HF_XET_HIGH_PERFORMANCE` | `1` |
| `UV_HTTP_TIMEOUT` | `600` |
| `PYTHONUNBUFFERED` | `1` |

---

## 2. Architecture / Components

### Docker data plane (running containers)

| Container | Image | Host port | Notes |
|---|---|---|---|
| `webui-test` | `ghcr.io/open-webui/open-webui:main` | `13000→8080` | `WEBUI_AUTH=false`, CPU image, MiniLM embeddings |
| `milvus-test` | `milvusdb/milvus:latest` | `19530`, `19091→9091` | Standalone; embedded etcd + MinIO |
| `pgvector-test` | `pgvector/pgvector:pg16` | `15432→5432` | `POSTGRES_PASSWORD=testpass` |
| `qdrant-test` | `qdrant/qdrant:latest` | `16333→6333`, `16334→6334` | — |
| `redis-test` | `redis:7-alpine` | `16379→6379` | — |

Compose reference: [`deploy/docker-compose.yml`](deploy/docker-compose.yml) (verified against `docker inspect`).

### Local OpenAI-compatible services (Python)

| Service | Port | Script | Purpose |
|---|---|---|---|
| Embeddings | `8001` | [`scripts/services/embed_server.py`](scripts/services/embed_server.py) | `bge-small-en-v1.5`, dim **384**, `/v1/embeddings` |
| LLM (llama.cpp) | `8080` | [`scripts/services/llama_chat_server.py`](scripts/services/llama_chat_server.py) | Serves a GGUF file; `/v1/chat/completions`, `/v1/completions` |
| LLM (vLLM) | `8000` | [`scripts/services/vllm_server.sh`](scripts/services/vllm_server.sh) | vLLM OpenAI API server; **requires a single-file GGUF** |

vLLM GGUF invocation flags: `--load-format gguf --quantization gguf` (verified on vLLM `0.6.1.post1`).

### Sample projects (cloned, to be run + tested in P4)

`dify`, `anything-llm`, `ragflow`, `lightrag` → `offline-prep/sample-projects/` (clones; not part of this git repo).

---

## 3. What was done

### Phase 0 — Offline preparation (2026-08-10/11)
- First automated run of `offline_prepare_cli.py`: pulled & saved 5 Docker images (`.tar`), downloaded ~30 wheels (`python-packages/`, `python-packages-cu124/`), downloaded embedding models, cloned 4 sample repos.
- Manual installs into the master venv: **vLLM 0.6.1.post1, flash-attn 2.6.3, llama-cpp-python 0.3.34, sglang 0.3.0** — plus a CUDA wheel set (torch 2.4.0+cu124, torchvision 0.19.0+cu124, torchaudio 2.4.0+cu124, faiss-gpu-cu12).
- Loaded the saved `.tar` images into Docker; started + healthchecked all 5 containers.

### Phase 1 — Environment stabilization (2026-08-15, P0)
- Fixed stale path bug: `offline_prepare_cli.py` `BASE_DIR` was hardcoded to the old mount `/ai-gpu1/v1/...` (no longer exists) → now derived from `__file__`.
- Repaired the venv: every entry-point shebang and the `activate` scripts pointed at the dead `/ai-gpu1/...` path ("required file not found") → rewritten to `/splunk-data/v1/...`.
- Fixed a package conflict: **scipy 1.18.0 → 1.13.1** (1.18.0 requires numpy≥2 but vLLM pins numpy 1.26.4; 1.18.0 crashed `sentence_transformers`).

### Phase 2 — Models & inference (2026-08-15, P1/P2)
- Downloaded **Qwen2.5-7B Q4_K_M** (4.68 GB, single-file, from `bartowski/Qwen2.5-7B-Instruct-GGUF`) — completed across 8 flaky-proxy retries; validated by a llama.cpp load test. *(Llama-3.2-3B and Mistral Q4_K_M still downloading in the background.)*
- Brought up live services: embeddings (`:8001`) and llama.cpp chat (`:8080`, smoke-tested against Mistral IQ2 quant).
- Prepared vLLM GGUF launcher, RAG test harness, and lightrag dedicated venv.

---

## 4. Models inventory

All under `offline-prep/models/huggingface/` (git-ignored):

| Model | Size | Status |
|---|---|---|
| `bartowski/Qwen2.5-7B-Instruct-GGUF` (Q4_K_M) | 4.7 GB | ✅ downloaded & validated (primary) |
| `bartowski/Llama-3.2-3B-Instruct-GGUF` (Q4_K_M) | ~2 GB | ⏳ downloading |
| `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | ~60 GB (IQ1–IQ5/Q2/Q3 quants) | ✅ IQ quants present; Q4_K_M ⏳ pending |
| `microsoft/Phi-3-mini-4k-instruct-gguf` | 9.4 GB | ✅ q4 + fp16 |
| `BAAI/bge-small-en-v1.5` | 383 MB | ✅ embeddings (dim 384) |
| `sentence-transformers/all-MiniLM-L6-v2` | 932 MB | ✅ embeddings |

**Master venv key packages:** torch 2.4.0+cu124 · vllm 0.6.1.post1 (+flash-attn 2.6.1) · flash-attn 2.6.3 · llama-cpp-python 0.3.34 · sglang 0.3.0 · transformers 4.44.0 · faiss-gpu-cu12 1.14.1.post1 · bitsandbytes 0.50.0 · numpy 1.26.4 · scipy 1.13.1 · sentence-transformers 3.0.1 · ragas 0.4.3 · deepeval 4.1.7

---

## 5. Plan & Progress

| # | Sub-plan | Status | Exit criteria |
|---|---|---|---|
| P0 | Stabilize environment | ✅ | CLI runs against real data; venv usable; docs updated |
| P1 | Complete model set (Qwen primary) | 🔄 in progress | Qwen/Llama/Mistral GGUF present & loadable |
| P2 | Inference engines (llama.cpp **and** vLLM) + embeddings | 🔄 partial | both engines answer a prompt; numbers logged |
| P3 | RAG data plane (vector DBs + Open WebUI + ingestion) | ⏳ | ingest → retrieve works end-to-end |
| P4 | Run + test sample repos (lightrag → anything-llm → ragflow → dify, in parallel) | ⏳ | each passes the RAG test harness |
| P5 | Production hardening + runbook | ⏳ | stack cold-restarts cleanly |

---

## 6. Commands

```bash
# Launch the offline-prep CLI (bootstraps env, runs in tmux "offline_prep")
bash start.sh
tmux attach -t offline_prep

# Set proxy for current shell (shell/apt/git/docker)
source proxy_setup.sh

# Venv tools (always via python3.12 if entry points are ever broken again)
offline-prep/venv/bin/python3.12 -m pip install <pkg> \
    --index-url https://download.pytorch.org/whl/cu124 \
    --extra-index-url https://pypi.org/simple

# Proxy-resilient model download (XET disabled, retries, resume)
offline-prep/venv/bin/python3.12 scripts/download_models.py

# Start local services
offline-prep/venv/bin/python3.12 scripts/services/embed_server.py \
    --model offline-prep/models/huggingface/BAAI_bge-small-en-v1.5 --port 8001
offline-prep/venv/bin/python3.12 scripts/services/llama_chat_server.py \
    --model offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf --port 8080
bash scripts/services/vllm_server.sh \
    offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf 8000

# RAG smoke test against any OpenAI-compatible stack
offline-prep/venv/bin/python3.12 scripts/rag_test_harness.py \
    --llm-url http://localhost:8080 --embed-url http://localhost:8001 --label smoke
```

---

## 7. Known issues / gotchas

- **Proxy drops large transfers** (docker pulls >~2 GB, HF files >~1 GB, pip tunnel 503/500). Mitigation: retry+resume everywhere. vLLM/CUDA docker images have **never** pulled successfully.
- **vLLM requires a single-file GGUF** — its loader reads one file; split/multi-part GGUFs are not supported (that's why `bartowski` single-file Q4_K_M was chosen over the official 2-part `Qwen/Qwen2.5-7B-Instruct-GGUF`).
- **numpy 1.26.4 is pinned by vLLM** — do not upgrade; keep scipy ≤ 1.13.x (see P0 fix).
- **`.state.json`/`.retry_queue.json` are stale** (mark installed packages as failed). Trust `docs/history/`, not the state files.
- **Docker data-root lives at `/ai-gpu1/v1/docker-data`** (a real separate mount) — volume paths in `docker inspect` show `/ai-gpu1/...`; that is expected and correct.

---

## 8. Documentation

- [`docs/history/`](docs/history/) — dated, detailed execution history (append per session; summarize files >~300 lines).
- [`docs/findings.md`](docs/findings.md) — verified environment facts, gotchas, and service inventory.
- [`AGENTS.md`](AGENTS.md) — instructions for agents working in this repo.
- [`deploy/docker-compose.yml`](deploy/docker-compose.yml) — reference compose for the data plane.

Generated artifacts (reports/logs/state) live under `offline-prep/` and are **not** tracked in git.
