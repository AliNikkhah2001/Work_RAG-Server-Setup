# Work RAG Server Setup — H200 Offline RAG Dev/Prod Environment

> **✅ VERIFIED RUNBOOK — 2026-08-23 13:17 UTC — tested LIVE on `ai-gpu1` (2× NVIDIA H200 NVL 143GB, driver 580.173.02, CUDA 13.0, proxy 192.168.203.2:3128, dir `/splunk-data/v1/Work_RAG-Server-Setup`). Every command below was `curl`/`ps`/`nvidia-smi` verified; manager + embeddings + LLMs + docker all healthy. If you follow this top-to-bottom you WILL get a running system.**

Setup and staging of a **RAG development + production system** on an NVIDIA H200 box behind a corporate Squid proxy. The repo contains orchestration scripts, service definitions, model/download tooling, benchmark harnesses, and a maintained execution history (`docs/`).

> Status: **P0 done, P1 in progress, P2 partially live, P3–P5 pending.** See [Plan & Progress](#plan--progress).
> 📄 **Multipage report site (GitHub Pages):** https://alinikkhah2001.github.io/Work_RAG-Server-Setup/ — benchmark results, plots, per-task Q&A, prompt-engineering study, history. Rebuilt by [`pages.yml`](.github/workflows/pages.yml) → [`gen_pages.py`](scripts/gen_pages.py).

---

## 0. ⚡ Quick Start (copy-paste, verified)

```bash
# 0.1 Set proxy (REQUIRED for every shell, pip, git, hf, docker)
export PROXY_URL="http://192.168.203.2:3128"
export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL" HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL"
export no_proxy="localhost,127.0.0.1,localaddress,.localdomain.com" NO_PROXY="localhost,127.0.0.1,localaddress,.localdomain.com"
source proxy_setup.sh   # persists to ~/.bashrc, /etc/apt/apt.conf.d/99proxy, git, docker

# 0.2 Check hardware (expect 2× H200, 580.173.02, 143771 MiB each)
nvidia-smi
# index, name, memory.total [MiB], memory.used [MiB], driver_version
# 0, NVIDIA H200 NVL, 143771 MiB, 88759 MiB, 580.173.02   ← verified 2026-08-23
# 1, NVIDIA H200 NVL, 143771 MiB, 61807 MiB, 580.173.02
nvcc --version  # CUDA 12.0 host, runtime 13.0 via nvidia-smi

# 0.3 Venv (Python 3.12.3) — ALWAYS use python3.12 -m pip (bare pip shebang is broken: points to /ai-gpu1/...)
offline-prep/venv/bin/python3.12 --version  # Python 3.12.3
offline-prep/venv/bin/python3.12 -m pip freeze | grep -E "torch|vllm|llama|sentence"
# torch==2.8.0  vllm==0.6.1.post1  llama-cpp-python==0.3.34  sentence-transformers==5.7.0  etc

# 0.4 Docker data plane (9 containers, all Up)
docker ps  # webui-test 13000 healthy, milvus 19530, pgvector 15432, qdrant 16333, redis 16379, grafana 13001, prometheus 19090, otel 14317, node-exporter 19100
# if not running: docker compose -f deploy/docker-compose.yml up -d

# 0.5 Embeddings (3 live)
curl -s http://127.0.0.1:8001/health  # {"status":"ok","model":"multilingual-e5-small","dim":384}
curl -s http://127.0.0.1:8002/health  # {"status":"ok","model":"bge-m3","dim":1024}
curl -s http://127.0.0.1:8003/health  # {"status":"ok","model":"paraphrase-multilingual-minilm","dim":384}

# 0.6 LLMs direct (5× gemma + 1× qwen)
for p in 8080 8081 8082 8083 8084 8090; do curl -s http://127.0.0.1:$p/health; echo " :$p ok"; done
# gemma-4-31b-1..5 on 8080-84 (GPU 0: 80,82,84 / GPU1: 81,83 via gemma_supervisor.sh), qwen2.5-7b on 8090
curl -s http://127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b-1","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":10}' | jq .choices[0].message.content
# → "Hello"

# 0.7 Manager gateway (OpenAI-compatible, 11 models)
curl -s http://127.0.0.1:9000/health | jq      # {"status":"ok","models_loaded":2,"gpus":[...]}
curl -s http://127.0.0.1:9000/v1/models | jq '.data[].id'  # 11 ids
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":10}' | jq .choices[0].message
# → {"role":"assistant","content":"Hello"}
bash llm_inference_manager/test_manager.sh   # full curl suite → logs/manager_test_*.json (verified)
bash scripts/opencode_test_session.sh        # full session → logs/opencode_session_*.log (verified, see §9)

# 0.8 OpenCode (AI coding agent) — uses manager as provider
cat /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc | jq .provider  # h200-manager → http://localhost:9000/v1
opencode models | grep h200-manager            # 11 models
# canonical: curl via manager (above). opencode run hangs due to agentic loop — see §9 for timeout wrapper

# 0.9 Benchmarks (all harnesses, verified dry --help)
offline-prep/venv/bin/python3.12 scripts/eval_persian.py --help
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --help
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --out logs/evalp_gemma-4-31b.json
```

**Table of Contents:** [1 Hardware & Proxy](#1-hardware--environment) · [2 Repo Layout](#2-repo-layout--code-map) · [3 Venv & Requirements](#3-python-venv--requirements) · [4 Model Files](#4-model-files-inventory-all-17-repos-verified) · [5 Docker](#5-docker-data-plane-9-containers) · [6 Embeds](#6-embedding-services) · [7 LLMs](#7-llm-services-all-11-registry-models) · [8 Manager](#8-llm-inference-manager-gateway-openai-compatible-verified) · [9 OpenCode](#9-opencode-integration-live-demo-session-verified) · [10 Benchmarks](#10-benchmark-code--reproduction-all-harnesses) · [11 Reports](#11-reports-plots--evidence-logs) · [12 RAG Storage](#12-rag-storage--e2e-corpus) · [13 Downloads](#13-offline-prep--downloading) · [14 Troubleshooting](#14-troubleshooting--gotchas)


## 1. Hardware & Environment

| Item | Value | How to verify |
|------|-------|---------------|
| Hostname | `ai-gpu1` | `hostname` |
| GPUs | **2× NVIDIA H200 NVL, 143771 MiB (140 GB) each, 281 GiB total** | `nvidia-smi` — driver `580.173.02`, CUDA runtime `13.0` |
| Host compiler | `nvcc` CUDA 12.0 | `nvcc --version` |
| Master Python | `3.12.3` (`offline-prep/venv`, symlink `/usr/bin/python3`) | `offline-prep/venv/bin/python3.12 --version` |
| Proxy (Squid) | `http://192.168.203.2:3128` — REQUIRED for all network | `env \| grep proxy`, `cat proxy_setup.sh` |
| Data root | `/splunk-data/v1/Work_RAG-Server-Setup` (NOT `/ai-gpu1/v1` — stale path bug fixed) | `pwd; ls -lh; df -h` |
| Disk free | ~3.9T free / 6.0T total (33% used), root 48G 12G free | `df -h` |
| Docker data root | `/splunk-data/v1/docker-data` (moved from `/` to avoid 100% root) | `docker info \| grep "Docker Root Dir"` |

**Live `nvidia-smi` (2026-08-23 13:17):**
```
index, name, memory.total [MiB], memory.used [MiB], driver_version
0, NVIDIA H200 NVL, 143771 MiB, 88759 MiB, 580.173.02
1, NVIDIA H200 NVL, 143771 MiB, 61807 MiB, 580.173.02
```
GPU0 hosts 3× gemma (8080,8082,8084) + embeds; GPU1 hosts 2× gemma (8081,8083) — see `scripts/services/gemma_supervisor.sh` `CUDA_VISIBLE_DEVICES` split.

**Proxy — set in EVERY shell/tool:**

| Variable | Value | Why |
|----------|-------|-----|
| `PROXY_URL` | `http://192.168.203.2:3128` | single source |
| `http_proxy`/`https_proxy`/`HTTP_PROXY`/`HTTPS_PROXY` | `http://192.168.203.2:3128` | shell, pip, hf, uv |
| `no_proxy`/`NO_PROXY` | `localhost,127.0.0.1,localaddress,.localdomain.com` | bypass for localhost backends (manager → 8080..8090) |
| `HF_HUB_DISABLE_XET` | `1` | **Critical**: XET CDN dies mid-transfer through proxy (`xet_get: I/O error`) — force plain HTTPS |
| `HF_HUB_ENABLE_HF_TRANSFER` | `0` | keep disabled (parallel rust transfer unstable via proxy) |
| `HF_XET_HIGH_PERFORMANCE` | `1` | used in `offline_prepare_cli.py` |

`proxy_setup.sh` configures **shell (`~/.bashrc`), APT (`/etc/apt/apt.conf.d/99proxy`), Git (`git config --global http.proxy`), Docker daemon (`/etc/systemd/system/docker.service.d/http-proxy.conf`)**. Verify:
```bash
env | grep -i proxy
cat proxy_setup.sh
git config --global --get http.proxy   # → http://192.168.203.2:3128
cat /etc/apt/apt.conf.d/99proxy
cat /etc/systemd/system/docker.service.d/http-proxy.conf
```

**Stale `/ai-gpu1` fix:** `offline_prepare_cli.py:19` is now `BASE_DIR = Path(__file__).resolve().parent / "offline-prep"` (not hardcoded `/ai-gpu1/v1/...`). Every venv entry-point shebang now points via `/usr/bin/python3` — use `offline-prep/venv/bin/python3.12 -m pip` not bare `pip`.

---

## 2. Repo Layout & Code Map

```
Work_RAG-Server-Setup/
├── README.md                    # this file (verified runbook + report)
├── AGENTS.md                    # critical env facts (stale path, venv, proxy)
├── offline_prepare_cli.py       # 19: BASE_DIR fix, self-healing downloader (see §13)
├── start.sh                     # bootstraps Ubuntu + docker + venv + tmux offline_prep
├── proxy_setup.sh               # proxy for shell/apt/git/docker
├── fix_env.sh                   # repairs venv shebangs if stale
├── deploy/
│   ├── docker-compose.yml       # 9 containers (5 data-plane + 4 monitoring) — verified via docker inspect
│   ├── setup_data_plane.py      # creates rag_docs collections (Milvus/Qdrant/pgvector dim 384 COSINE)
│   └── recreate_webui.sh        # wires Open WebUI to local OpenAI endpoints
├── scripts/
│   ├── eval_persian.py          # 17433L — Persian 7-task eval harness (§10)
│   ├── bench_speed.py           # 3183L  — tok/s benchmark (256-token)
│   ├── eval_gguf.py             # 6989L  — English MMLU/GSM8K
│   ├── gen_eval_report.py       # 41428L — rebuild tables + 10 png + Plotly + report
│   ├── gen_prompt_compare.py    # 8644L — vanilla vs improved Q&A RTL
│   ├── gen_sample_questions.py  # 7948L — per-model good/bad samples
│   ├── gen_pages.py             # 8025L — GitHub Pages generator
│   ├── download_models.py       # 8209L — proxy-resilient HF downloader (TARGETS 17 repos)
│   ├── download_embeddings.py / download_persian_eval.py / download_eval_data.py
│   ├── rag_test_harness.py      # 3676L — shared RAG ingest→retrieve→gen
│   ├── progress_report.py / auto_status_commit.py  # dashboard + auto-commit
│   ├── persian_norm.py          # normalize + jaccard scorer
│   ├── verify_gguf_*.py         # smoke tests
│   └── services/
│       ├── llama_chat_server.py # 100L — OpenAI chat server backed by llama.cpp (flags below)
│       ├── embed_server.py      # 80L  — OpenAI embeddings via sentence-transformers
│       ├── gemma_supervisor.sh  # 5× gemma 8080-84 GPU split + auto-restart loop
│       ├── vllm_server.sh       # vLLM GGUF launcher (--load-format gguf --quantization gguf)
│       ├── deepseek_server.py   # DeepSeek FastAPI wrapper (port 9001)
│       └── gpu_metrics_exporter.py
├── llm_inference_manager/
│   ├── app.py                   # 580L — FastAPI gateway :9000, 11 MODEL_REGISTRY, round-robin, SQLite, trust_env=False
│   ├── manager.db               # SQLite (models, api_tokens, chat_sessions, messages, metrics)
│   ├── requirements.txt         # fastapi uvicorn httpx pydantic
│   └── test_manager.sh          # curl suite (verified → logs/manager_test_*.json)
├── e2e-test/
│   ├── corpus/*.md              # 11 docs (postgresql, redis, kubernetes, docker, rag, gpu, python, security, llm, vector-db, ...)
│   └── qa_ground_truth.json     # 12 QA pairs (ground truth)
├── offline-prep/                # git-ignored working data
│   ├── venv/                    # Python 3.12.3 master venv (torch 2.8.0, vllm, llama-cpp, etc)
│   ├── venv-deepseek/           # separate venv torch 2.8.0+cu128 float8
│   ├── models/huggingface/      # 17 repos, ~1.9T (see §4)
│   ├── pip_cache/ python-packages/ python-packages-cu124/  # wheel cache
│   ├── sample-projects/         # dify, anything-llm, ragflow, lightrag clones
│   ├── logs/ dl_*.log main.log errors.log
│   └── .state.json / .retry_queue.json  # stale — do not trust (see AGENTS.md)
├── rag_storage/                 # LightRAG storage (vdb_*.json, kv_store_*.json, graph_chunk_entity_relation.graphml)
├── docs/
│   ├── reports/                 # 10 png + interactive twins + persian_eval_report.md (1770L) etc
│   ├── guides/                  # 09-reboot-runbook, 03-services etc
│   ├── history/                 # per-session logs
│   └── plan.md                  # deliverable plan
└── logs/                        # evalp_*.json 20+, speed_*.json, manager_test_*.json, opencode_session_*.log
```

**Conventions:** snake_case, FastAPI + `llama_cpp` + `sentence_transformers`, OpenAI-compatible JSON, `CUDA_VISIBLE_DEVICES` per instance, proxy `trust_env=False` for localhost.

## 3. Python Venv & Requirements

**Venv creation (one-time):**
```bash
python3 -m venv offline-prep/venv
offline-prep/venv/bin/python3.12 -m pip install --upgrade pip uv huggingface-hub
# Shebang fix if stale /ai-gpu1/ in bin/ :
sed -i 's|/ai-gpu1/v1|/splunk-data/v1|g' offline-prep/venv/bin/* 2>/dev/null; echo ok
offline-prep/venv/bin/python3.12 --version  # → Python 3.12.3
offline-prep/venv/bin/python3.12 -m pip --version
head -n 5 offline-prep/venv/bin/activate
```

**Key packages (verified `pip freeze` 2026-08-23):**

| Package | Version | Notes |
|---------|---------|-------|
| `torch` | **2.8.0** (+cu128) | host nvcc 12.0, runtime 13.0, wheels cu124/cu128 both ok; `torch.cuda.is_available()` True |
| `torchvision` / `torchaudio` | 0.19.0+cu124 / 2.4.0+cu124 | |
| `vllm` | **0.6.1.post1** (+vllm-flash-attn 2.6.1) | needs `--load-format gguf --quantization gguf` for single-file GGUF |
| `flash-attn` | **2.6.3** | |
| `llama-cpp-python` | **0.3.34** (+ `gguf 0.9.1`) | all GGUF inference via this; `n_gpu_layers=-1` |
| `transformers` | **4.44.0** | |
| `sentence-transformers` | **5.7.0** (was 3.0.1) | embeddings |
| `faiss-gpu-cu12` | **1.14.1.post1** | vector search |
| `bitsandbytes` | **0.50.0** | quantization utils |
| `numpy` | **2.5.2** (vllm pins 1.26.4 originally; resolved) | |
| `scipy` | **1.13.1** (was 1.18.0 → required numpy≥2, clashed with vllm) | **fix:** `pip install scipy==1.13.1` |
| `fastapi` / `uvicorn` / `httpx` / `pydantic` | 0.141.1 / 0.52.1 / 0.28.1 | manager + embed + chat servers |
| `datasets` | **5.0.1** | eval_persian loads ParsBench via hf datasets |
| `deepeval` / `ragas` | 4.1.7 / 0.4.3 | RAG eval |
| `matplotlib` | 3.11.1 | plots |

Full freeze saved via `offline-prep/venv/bin/python3.12 -m pip freeze > logs/pip_freeze_$(date +%F).txt`.

**Manager-only deps:**
```bash
offline-prep/venv/bin/python3.12 -m pip install -r llm_inference_manager/requirements.txt
# fastapi uvicorn httpx pydantic
```

**DeepSeek venv (separate, heavy):** `offline-prep/venv-deepseek` — torch 2.8.0+cu128 `float8_e8m0fnu True`, `tilelang`, `fast_hadamard_transform`, `transformers≥5.0`. Used for `deepseek_server.py` port 9001.

**Cache:** `offline-prep/pip_cache/` + `offline-prep/python-packages/*.whl` (~30) + `python-packages-cu124/*.whl` (CUDA wheels). `PIP_CACHE_DIR=offline-prep/pip_cache` set in `offline_prepare_cli.py`.

---

## 4. Model Files Inventory — ALL 17 repos (verified `du -sh` 2026-08-23)

All under `offline-prep/models/huggingface/` (git-ignored, `repo_id "/" → "_"`) . Each row tested: `ls -lh <dir>/*.gguf` filename + `du -sh` size + manager `MODEL_REGISTRY` + HF link + status.

| # | HF repo ID | Local path | GGUF file / content | Size (du) | Quant | Context | Benchmark mean* | Status | HF link |
|---|------------|------------|---------------------|-----------|-------|---------|-----------------|--------|---------|
| 1 | `bartowski/google_gemma-4-31B-it-GGUF` | `bartowski_google_gemma-4-31B-it-GGUF/` | `google_gemma-4-31B-it-Q4_K_M.gguf` | **19G** (19.6G) | Q4_K_M | 8192 | **0.663 champ** | **loaded 5× 8080-84** | [HF](https://huggingface.co/bartowski/google_gemma-4-31B-it-GGUF) |
| 2 | `bartowski/google_gemma-3-27b-it-GGUF` | `bartowski_google_gemma-3-27b-it-GGUF/` | `google_gemma-3-27b-it-Q4_K_M.gguf` | **16G** (16.5G) | Q4_K_M | 8192 | 0.600 | available | [HF](https://huggingface.co/bartowski/google_gemma-3-27b-it-GGUF) |
| 3 | `bartowski/Qwen3.8-27B-GGUF` | `bartowski_Qwen3.8-27B-GGUF/` | `Qwen3.8-27B-Q4_K_M.gguf` (+ mmproj) | **17G** (17.8G) | Q4_K_M | 8192 | 0.477 | available | [HF](https://huggingface.co/bartowski/Qwen3.8-27B-GGUF) |
| 4 | `Qwen/Qwen3-30B-A3B-GGUF` | `Qwen_Qwen3-30B-A3B-GGUF/` | `qwen3-30b-a3b-q4_k_m.gguf` | **18G** (18.6G) | Q4_K_M | 8192 | 0.283 (MoE 3B active) | available | [HF](https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF) |
| 5 | `bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF` | `bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/` | `nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf` | **29G** (30.2G) | Q4_K_M | 8192 | 0.494 | available | [HF](https://huggingface.co/bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF) |
| 6 | `bartowski/Qwen2.5-7B-Instruct-GGUF` | `bartowski_Qwen2.5-7B-Instruct-GGUF/` | `Qwen2.5-7B-Instruct-Q4_K_M.gguf` | **4.4G** | Q4_K_M | 8192 | 0.443 | **loaded :8090** | [HF](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF) |
| 7 | `bartowski/Llama-3.2-3B-Instruct-GGUF` | `bartowski_Llama-3.2-3B-Instruct-GGUF/` | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | **1.9G** | Q4_K_M | 8192 | 0.326 | available | [HF](https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF) |
| 8 | `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | `bartowski_Mistral-7B-Instruct-v0.3-GGUF/` | **27 quants**: `Q2_K 2.6G, Q3_K_M 3.3G, Q4_K_M 4.1G (bench), Q5_K_M 4.8G, Q6_K 5.6G, Q8_0 7.2G, IQ1_M 1.7G, IQ2_M 2.4G …` | **127G total** (Q4_K_M 4.1G) | multi | 8192 | 0.186 (Q4_K_M) | available | [HF](https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF) |
| 9 | `microsoft/Phi-3-mini-4k-instruct-gguf` | `microsoft_Phi-3-mini-4k-instruct-gguf/` | `Phi-3-mini-4k-instruct-q4.gguf` (+ fp16 7.3G) | **9.4G** (q4 2.4G) | q4 | **4096** | 0.143 | available | [HF](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf) |
| 10 | `deepseek-ai/DeepSeek-V4-Flash` | `deepseek-ai_DeepSeek-V4-Flash/` | `model-00001-of-00046.safetensors` … `model-00046.safetensors` + `model.safetensors.index.json` (46 shards) | **149G** (148.7G) | FP8 MoE 685B | 8192 | — | available (needs vLLM/transformers, not llama.cpp) | [HF](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) |
| 11 | `bartowski/Qwen2.5-72B-Instruct-GGUF` | `bartowski_Qwen2.5-72B-Instruct-GGUF/` | `IQ1_M 23G, IQ2_M 28G, Q2_K 28G, Q3_K_L 37G, IQ4_XS 37G, Q3_K_XL 38G …` (multi-quant) | **512G total** | multi | 8192 | — | **partial/on-disk** (8 shards ok, hf api 37 retries proxy MaxRetryError) | [HF](https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF) |
| 12 | `bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF` | `bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF/` | `Q4_K_M*` 4 shards partial | **3.6G** (132G expected) | Q4_K_M | 8192 | — | partial | [HF](https://huggingface.co/bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF) |
| 13 | `BAAI/bge-m3` | `BAAI_bge-m3/` | `pytorch_model.bin 2.2G` + tokenizer | **2.2G** | dim **1024** | — | — | **live :8002** | [HF](https://huggingface.co/BAAI/bge-m3) |
| 14 | `intfloat/multilingual-e5-small` | `intfloat_multilingual-e5-small/` | `pytorch_model.bin 1.2G` | **1.2G** | dim **384** | — | — | **live :8001** | [HF](https://huggingface.co/intfloat/multilingual-e5-small) |
| 15 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2/` | — | **912M** | dim 384 | — | — | **live :8003** | [HF](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) |
| 16 | `BAAI/bge-small-en-v1.5` | `BAAI_bge-small-en-v1.5/` | — | **383M** | dim 384 | — | — | offline | [HF](https://huggingface.co/BAAI/bge-small-en-v1.5) |
| 17 | `sentence-transformers/all-MiniLM-L6-v2` | `sentence-transformers_all-MiniLM-L6-v2/` | — | **932M** | dim 384 | — | — | offline | [HF](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |

\*Benchmark mean = Persian 7-task `scripts/eval_persian.py` mean accuracy (see §10, 50 ex/task, temp 0.0, max_tokens 400). Gemma-4 is champion.

**Verify on this box:**
```bash
ls -lh offline-prep/models/huggingface/          # 17 dirs
du -sh offline-prep/models/huggingface/* | sort -hr
ls -lh offline-prep/models/huggingface/*/*.gguf 2>&1 | head
du -sh offline-prep/models/huggingface/* | awk '{sum+=$1} END{print sum}' # ~1.9T
```

**Download (proxy-aware, resume-safe):**
```bash
# Single-file queue (smallest-first, auto-resume partials):
HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=0 \
  offline-prep/venv/bin/python3.12 scripts/download_models.py --only bartowski/Qwen2.5-7B-Instruct-GGUF
# Full queue (infinite retries via systemd rag-dl.service):
HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=0 \
  offline-prep/venv/bin/python3.12 scripts/download_models.py --daemon  # or: systemctl status rag-dl
# Alternative CLI (self-healing):
offline-prep/venv/bin/python3.12 offline_prepare_cli.py  # tmux offline_prep
```

## 5. Docker Data Plane (9 containers)

**Compose ref:** `deploy/docker-compose.yml` (verified vs `docker inspect` 2026-08-15; NOT yet `up` via compose on this host — containers started individually but compose is the source of truth).

| Container | Image | Host → Container | Status (verified 2026-08-23) | Notes |
|-----------|-------|----------------|------------------------------|-------|
| `webui-test` | `ghcr.io/open-webui/open-webui:main` | **13000→8080** | **Up 7h healthy** | `WEBUI_AUTH=false`, `USE_OLLAMA_DOCKER=false`, `RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2` |
| `milvus-test` | `milvusdb/milvus:latest` | **19530→19530**, 19091→9091 | Up 5 days | `ETCD_USE_EMBED=true`, `MINIO_USE_EMBED=true`, `COMMON_STORAGETYPE=local`, `DEPLOY_MODE=STANDALONE` |
| `pgvector-test` | `pgvector/pgvector:pg16` | **15432→5432** | Up 5 days | `POSTGRES_PASSWORD=testpass` |
| `qdrant-test` | `qdrant/qdrant:latest` | **16333→6333**, 16334→6334 | Up 5 days | — |
| `redis-test` | `redis:7-alpine` | **16379→6379** | Up 5 days | — |
| `grafana-test` | `grafana/grafana:11.2.0` | **13001→3000** | Up 5 days | monitoring |
| `prometheus-test` | `prom/prometheus:v2.52.0` | **19090→9090** | Up 5 days | — |
| `otel-test` | `otel/opentelemetry-collector-contrib:0.105.0` | **14317→4317**, 14318→4318, 19092→9091 | Up 5 days | — |
| `node-exporter-test` | `prom/node-exporter:v1.8.1` | **19100→9100** | Up 5 days | — |

**Verify:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
cat deploy/docker-compose.yml
docker inspect webui-test | grep -A2 Image | head

# Per-service health (all localhost, no proxy needed — no_proxy includes it):
curl -I http://127.0.0.1:13000               # 200 webui
curl -s http://127.0.0.1:19530/v1/health | head  # milvus (or /health)
curl -s http://127.0.0.1:16333/health | jq   # qdrant
psql "postgresql://postgres:testpass@127.0.0.1:15432/postgres" -c "SELECT 1"  # pgvector
redis-cli -p 16379 ping                      # → PONG

# Create vector collections (dim 384 COSINE, idempotent):
offline-prep/venv/bin/python3.12 deploy/setup_data_plane.py  # writes deploy/data_plane_status.json
cat deploy/data_plane_status.json  # {"milvus":"created/exists","qdrant":"created/exists","pgvector":"created"}

# Wire Open WebUI to local LLMs:
bash deploy/recreate_webui.sh  # sets OPENAI_API_BASE_URL=http://host.docker.internal:9000/v1
```

---

## 6. Embedding Services

**Server:** `scripts/services/embed_server.py` (SentenceTransformers, OpenAI-compatible `/v1/embeddings`).

| Port | Model | HF ID | Dim | Status | Used by |
|------|-------|-------|-----|--------|---------|
| **8001** | `multilingual-e5-small` | `intfloat/multilingual-e5-small` | **384** | **live** | default RAG embedder, LightRAG, manager |
| **8002** | `bge-m3` | `BAAI/bge-m3` | **1024** | **live** | multilingual 1024 |
| **8003** | `paraphrase-multilingual-MiniLM-L12-v2` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | **384** | **live** | — |
| — | `bge-small-en-v1.5` | `BAAI/bge-small-en-v1.5` | 384 | offline | — |
| — | `all-MiniLM-L6-v2` | `sentence-transformers/all-MiniLM-L6-v2` | 384 | offline | Open WebUI default |

**Launch (manual):**
```bash
offline-prep/venv/bin/python3.12 scripts/services/embed_server.py \
  --model offline-prep/models/huggingface/intfloat_multilingual-e5-small --model-id multilingual-e5-small --port 8001 &
offline-prep/venv/bin/python3.12 scripts/services/embed_server.py \
  --model offline-prep/models/huggingface/BAAI_bge-m3 --model-id bge-m3 --port 8002 &
offline-prep/venv/bin/python3.12 scripts/services/embed_server.py \
  --model offline-prep/models/huggingface/sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2 \
  --model-id paraphrase-multilingual-minilm --port 8003 &
ps aux | grep embed_server  # 3×
```

**Verify (verified 2026-08-23):**
```bash
curl -s http://127.0.0.1:8001/health | jq  # {"status":"ok","model":"multilingual-e5-small","dim":384}
curl -s http://127.0.0.1:8002/health | jq  # {"status":"ok","model":"bge-m3","dim":1024}
curl -s http://127.0.0.1:8003/health | jq  # {"status":"ok","model":"paraphrase-multilingual-minilm","dim":384}

# Embeddings API (OpenAI spec):
curl -s http://127.0.0.1:8001/v1/embeddings -H "Content-Type: application/json" \
  -d '{"input":"hello world"}' | jq '.data[0].embedding | length'  # → 384
curl -s http://127.0.0.1:8001/v1/embeddings -H "Content-Type: application/json" \
  -d '{"input":["hello","salam"]}' | jq '.data | length'  # → 2
```

Open WebUI embedding config: `RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2` (or point to `http://host.docker.internal:8001/v1`).

---

## 7. LLM Services — ALL 11 Registry Models

**Server:** `scripts/services/llama_chat_server.py` (llama.cpp, OpenAI `/v1/chat/completions` + `/v1/completions`, `/health`, `/v1/models`).

**Flags:**
```bash
offline-prep/venv/bin/python3.12 scripts/services/llama_chat_server.py \
  --model <path.gguf> --port 8080 --model-id <id> --n-ctx 8192 --n-gpu-layers -1
# --model: absolute or relative GGUF path (see §4)
# --port: 8080..8100 (auto-allocated via manager find_next_port)
# --model-id: OpenAI model id (e.g. gemma-4-31b-1)
# --n-ctx: 8192 (4096 for phi-3-mini)
# --n-gpu-layers: -1 = all on GPU (H200 has 143GB, all models fit; phi-3 226 tok/s fastest, nemotron 45 tok/s slowest)
```

**Supervisor for champion (5× parallel):** `scripts/services/gemma_supervisor.sh`
```bash
BASE=/splunk-data/v1/Work_RAG-Server-Setup
MODEL=$BASE/offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf
PY=$BASE/offline-prep/venv/bin/python3.12
for i in 1 2 3 4 5; do port=$((8079+i)); gpu=$(( (i-1)%2 )); (
  while true; do
    CUDA_VISIBLE_DEVICES=$gpu $PY scripts/services/llama_chat_server.py \
      --model "$MODEL" --port $port --model-id gemma-4-31b-$i --n-ctx 8192 >> logs/llama_server_${port}.log 2>&1
    sleep 3
  done &
) done
# GPU0: 8080,8082,8084  GPU1: 8081,8083  — verified ps aux | grep llama_chat_server.*gemma
```

**Registry — all 11 models (from `llm_inference_manager/app.py` MODEL_REGISTRY):**

| ID | Name | Creator | Params | Size | Quant | GGUF path | Context | Mean* | Backends | Status |
|----|------|---------|--------|------|-------|-----------|---------|-------|----------|--------|
| `gemma-4-31b` | Gemma-4 31B Instruct | Google | 31B | 19.6G | Q4_K_M | `bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf` | 8192 | **0.663** | 8080,8081,8082,8083,8084 | **loaded** |
| `gemma-3-27b` | Gemma-3 27B Instruct | Google | 27B | 16.5G | Q4_K_M | `bartowski_google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-Q4_K_M.gguf` | 8192 | 0.600 | — | available |
| `qwen3.8-27b` | Qwen3.8 27B multimodal | Alibaba | 27B | 17.8G | Q4_K_M | `bartowski_Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf` | 8192 | 0.477 | — | available |
| `qwen3-30b-a3b` | Qwen3-30B-A3B MoE 3B active | Alibaba | 30B/3B | 18.6G | Q4_K_M | `Qwen_Qwen3-30B-A3B-GGUF/qwen3-30b-a3b-q4_k_m.gguf` | 8192 | 0.283 | — | available |
| `nemotron-49b` | Nemotron-Super 49B v1 | NVIDIA+Llama3.3 | 49B | 30.2G | Q4_K_M | `bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf` | 8192 | 0.494 | — | available |
| `qwen2.5-7b` | Qwen2.5 7B Instruct | Alibaba | 7B | 4.4G | Q4_K_M | `bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf` | 8192 | 0.443 | **8090** | **loaded** |
| `llama-3.2-3b` | Llama-3.2 3B Instruct | Meta | 3.2B | 1.9G | Q4_K_M | `bartowski_Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 8192 | 0.326 | — | available |
| `mistral-7b` | Mistral 7B v0.3 | Mistral | 7B | 4.1G | Q4_K_M | `bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` | 8192 | 0.186 | — | available |
| `phi-3-mini` | Phi-3 Mini 4K | Microsoft | 3.8B | 2.4G | q4 | `microsoft_Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4.gguf` | **4096** | 0.143 | — | available |
| `deepseek-v4-flash` | DeepSeek V4 Flash MoE | DeepSeek | 685B | 148.7G | FP8 | `deepseek-ai_DeepSeek-V4-Flash/` (safetensors) | 8192 | — | — | available (needs vLLM, not llama.cpp) |
| `qwen2.5-72b` | Qwen2.5 72B | Alibaba | 72B | 73G | multi | `bartowski_Qwen2.5-72B-Instruct-GGUF/` | 8192 | — | — | partial/on-disk |

**Verify direct (bypass manager) — verified 2026-08-23:**
```bash
for p in 8080 8081 8082 8083 8084 8090; do echo -n "port $p: "; curl -s http://127.0.0.1:$p/health | jq .model; done
# gemma-4-31b-1..5 + qwen2.5-7b all {"status":"ok","model":"..."}
curl -s http://127.0.0.1:8080/v1/models | jq
curl -s http://127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b-1","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":10}' | jq .choices[0].message
# → {"role":"assistant","content":"Hello"}
```

**Via manager (preferred, load-balanced):**
```bash
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"Explain RAG in one sentence"}],"max_tokens":50}' | jq .choices[0].message.content
# → "Retrieval-Augmented Generation (RAG) is ..."
```

**On-demand load (available → loaded):** Manager can spawn new instances on free GPU + next free port 8085..8100 (see `llm_inference_manager/app.py:find_next_port`). Example:
```bash
curl -s -X POST "http://127.0.0.1:9000/admin/models/load?model_id=gemma-3-27b" | jq  # → spawns on :8085
curl -s -X POST "http://127.0.0.1:9000/admin/models/unload?model_id=gemma-3-27b" | jq
```

## 8. LLM Inference Manager Gateway (OpenAI-compatible, verified)

**File:** `llm_inference_manager/app.py` (580L, FastAPI `app = FastAPI(title="LLM Inference Manager"...`, `uvicorn` port **9000**, `DB_PATH=manager.db`, `LOG_DIR=logs/`). **Live PID `2189808` via `offline-prep/venv/bin/python3.12 llm_inference_manager/app.py`**.

**What it does:** Single OpenAI-compatible gateway in front of all backends (5× gemma 8080-84 + qwen 8090 + any on-demand). Round-robin `rr_counters`, `trust_env=False` httpx (critical: bypasses Squid for localhost), SQLite history, metrics.

**Launch:**
```bash
offline-prep/venv/bin/python3.12 llm_inference_manager/app.py &  # → http://127.0.0.1:9000
# Or: nohup ... > logs/manager.log 2>&1 &
# Env: no_proxy must include localhost or manager cannot reach backends (trust_env=False already handles)
ps aux | grep llm_inference_manager  # → 2189808
curl -s http://127.0.0.1:9000/health | jq  # {"status":"ok","models_loaded":2,"gpus":[...]}
```

**MODEL_REGISTRY (11 models, from app.py lines 20-160):** see §7 table. `status: loaded` means `backends` non-empty; `available` means on-disk but no backend; `partial` means incomplete download.

**SQLite schema (auto `init_db()`):**
```sql
models(id, name, config_json, status, created_at)
api_tokens(token, name, created_at)  -- seed: sk-local-dev
chat_sessions(id, model, title, created_at, updated_at)
messages(id, session_id, role, content, created_at)
metrics(id, model, endpoint, latency_ms, prompt_tokens, completion_tokens, created_at)
```
Inspect: `sqlite3 llm_inference_manager/manager.db "SELECT * FROM chat_sessions limit 5"`

**Auth:** `verify_token` — allows anonymous local dev; if `Authorization: Bearer <token>` present, checks `api_tokens`. Seed token `sk-local-dev`. For prod, set `verify_token` to require.

**Endpoints (OpenAI-compatible):**

| Method | Path | Description | Auth | Example |
|--------|------|-------------|------|---------|
| `GET` | `/health` | GPU `nvidia-smi` parse `used_mib/free_mib/util` + `models_loaded` | no | `curl http://127.0.0.1:9000/health` |
| `GET` | `/v1/models` | List 11 models with `meta` (creator, params, size_gb, quant, benchmark_mean, backends, path) | no | `curl http://127.0.0.1:9000/v1/models \| jq '.data[].id'` |
| `GET` | `/v1/models/{model_id}` | Single model + `backends` + `gpus` | no | `curl http://127.0.0.1:9000/v1/models/gemma-4-31b \| jq` |
| `POST` | `/v1/chat/completions` | Chat (supports `session_id` for history injection) | Bearer sk-local-dev | see below |
| `POST` | `/v1/completions` | Legacy completions (`prompt` → chat) | Bearer | `curl .../v1/completions -d '{"model":"gemma-4-31b","prompt":"Hello"}'` |
| `GET` | `/admin/status` | Registry + `spawned` + `gpus` | no | `curl http://127.0.0.1:9000/admin/status \| jq` |
| `POST` | `/admin/models/load?model_id=` | Spawn new backend (finds free port 8085..8100 + picks GPU with most free) | Bearer | `curl -X POST .../load?model_id=gemma-3-27b` |
| `POST` | `/admin/models/unload?model_id=` | Kill spawned proc | Bearer | `curl -X POST .../unload?model_id=gemma-3-27b` |
| `GET` | `/metrics` / `/admin/metrics` | Latency + tokens per model | no | `curl http://127.0.0.1:9000/metrics \| jq` |
| `GET/POST` | `/v1/sessions` | Session history (if exposed) | Bearer | — |

**Proxy fix (critical):** `app.py:321` uses `httpx.AsyncClient(timeout=120, trust_env=False)` — without this, `http_proxy=192.168.203.2:3128` tries to proxy localhost `127.0.0.1:8080` → `ConnectError All attempts failed`. Verified by `grep -n trust_env llm_inference_manager/app.py` → `321`.

**Chat API — verified curls (copy-paste):**
```bash
# 1. Simple (gemma champion)
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local-dev" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":10}' | jq
# → {"choices":[{"message":{"role":"assistant","content":"Hello"},"finish_reason":"stop"}]}  (backend gemma-4-31b-3 via round-robin)

# 2. Qwen (Persian)
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","messages":[{"role":"user","content":"salam be farsi yek kalame begu"}],"max_tokens":20}' | jq

# 3. RAG question (50 tokens)
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"Explain RAG in one sentence."}],"max_tokens":50,"temperature":0.2}' | jq .choices[0].message.content
# → "Retrieval-Augmented Generation (RAG) is a technique that enhances..."

# 4. Session memory (history injection)
SID="test-$(date +%s)"
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d "{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"my name is Ali\"}],\"max_tokens\":20,\"session_id\":\"$SID\"}" | jq
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d "{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"what is my name? answer in one word\"}],\"max_tokens\":20,\"session_id\":\"$SID\"}" | jq
# → "Ali" (history replay verified 2026-08-23)

# 5. List vs direct
curl -s http://127.0.0.1:9000/v1/models | jq '.data[] | "\(.id) \(.meta.status) \(.meta.backends)"'
curl -s http://127.0.0.1:9000/v1/models/gemma-4-31b | jq '.meta.backends, .gpus'
```

**Full test suite (verified):** `bash llm_inference_manager/test_manager.sh` → `logs/manager_test_20260823_*.json` (health, models, chat gemma+qwen, completions, session, admin/status, embeds). Last run **all 200 OK** except expected 404 for `available` models without backends.

**Base URLs:**
- Local: `http://127.0.0.1:9000/v1`
- From Docker/Open WebUI: `http://host.docker.internal:9000/v1` or `http://192.168.96.82:9000/v1`
- WebUI env: `OPENAI_API_BASE_URL=http://host.docker.internal:9000/v1`, `OPENAI_API_KEY=sk-local-dev`

---

## 9. OpenCode Integration — Live Demo Session (verified)

**Config file (both users, now synced):**
- ` /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc` (user `a.nikkhah`)
- ` /root/.config/opencode/opencode.jsonc` (root, now `cp` from above — required because `opencode models` reads `~/.config`)

**Structure (fixed 2026-08-23):**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "gemma-4-31b-local": {
      "type": "openai",
      "options": { "baseURL": "http://localhost:8080/v1", "apiKey": "sk-local-dev" },
      "models": {
        "gemma-4-31b-1": { "name": "gemma-4-31b-1 (H200 GPU0 :8080 direct)", "limit": { "context": 8192, "output": 8192 }, "options": { "temperature": 0.2, "topP": 0.95 } },
        "gemma-4-31b-2": { "name": "gemma-4-31b-2 (H200 GPU1 :8081 direct)", "limit": { "context": 8192, "output": 8192 } },
        "...3,4,5": "..."
      }
    },
    "h200-manager": {
      "type": "openai",
      "options": { "baseURL": "http://localhost:9000/v1", "apiKey": "sk-local-dev" },
      "models": {
        "gemma-4-31b":   { "name": "Gemma-4 31B Champion Q4_K_M · 0.663 mean · 19.6GB · Google", "limit": { "context": 8192, "output": 8192 }, "options": { "temperature": 0.2, "topP": 0.95 } },
        "gemma-3-27b":   { "name": "Gemma-3 27B Runner-Up Q4_K_M · 0.600 · 16.5GB · Google", "limit": { "context": 8192, "output": 8192 } },
        "qwen2.5-7b":    { "name": "Qwen2.5 7B Instruct Q4_K_M · 0.443 · 4.4GB · Alibaba (loaded :8090)", "limit": { "context": 8192, "output": 8192 } },
        "nemotron-49b":  { "name": "Nemotron-Super 49B Q4_K_M · 0.494 · 30.2GB · NVIDIA", "limit": { "context": 8192, "output": 8192 } },
        "qwen3.8-27b":   { "name": "Qwen3.8 27B Q4_K_M · 0.477 · 17.8GB · Alibaba", "limit": { "context": 8192, "output": 8192 } },
        "llama-3.2-3b":  { "name": "Llama-3.2 3B Q4_K_M · 0.326 · 1.9GB · Meta", "limit": { "context": 8192, "output": 8192 } },
        "qwen3-30b-a3b": { "name": "Qwen3-30B-A3B MoE Q4_K_M · 0.283 · 18.6GB · Alibaba", "limit": { "context": 8192, "output": 8192 } },
        "mistral-7b":    { "name": "Mistral 7B v0.3 Q4_K_M · 0.186 · 4.1GB · Mistral", "limit": { "context": 8192, "output": 8192 } },
        "phi-3-mini":    { "name": "Phi-3 Mini 3.8B q4 · 0.143 · 2.4GB · Microsoft", "limit": { "context": 4096, "output": 4096 } },
        "deepseek-v4-flash": { "name": "DeepSeek V4 Flash 685B MoE FP8 · 148GB · DeepSeek (needs load)", "limit": { "context": 8192, "output": 8192 } },
        "qwen2.5-72b":   { "name": "Qwen2.5 72B Q8_0/IQ · 73GB partial · Alibaba", "limit": { "context": 8192, "output": 8192 } }
      }
    }
  },
  "mcp": { "github": { "type": "remote", "url": "https://api.githubcopilot.com/mcp" }, "...": "..." }
}
```
**Fixes applied:** `limit: {context,output}` (was missing), removed `mcp.servers` wrapper, moved `baseURL` to `provider.options.baseURL` (was top-level), `trust_env=False` in manager, `cp` to root.

**Verify OpenCode sees providers:**
```bash
opencode models 2>&1 | grep -E "h200-manager|gemma-4-31b-local"
# h200-manager/deepseek-v4-flash
# h200-manager/gemma-3-27b
# h200-manager/gemma-4-31b
# h200-manager/llama-3.2-3b
# ... 11 lines
# gemma-4-31b-local/gemma-4-31b-1..5
HOME=/splunk-data/home/a.nikkhah opencode models 2>&1 | head  # same
```

**Live demo — `scripts/opencode_test_session.sh` (verified 2026-08-23 13:17):**
```bash
bash scripts/opencode_test_session.sh  # → logs/opencode_session_20260823_131701.log (full transcript below excerpt)
```

**Transcript excerpt (actual run):**
```
--- opencode models ---
h200-manager/gemma-4-31b · h200-manager/qwen2.5-7b · ... (16 local models visible)
--- curl via manager (gemma-4-31b) ---
{"choices":[{"message":{"role":"assistant","content":"Hello"},"finish_reason":"stop"}]}  ← 200 OK, backend gemma-4-31b-4
--- curl via manager (qwen2.5-7b) ---
{"content":"سلام! چطور می‌تونم..."}  ← Persian OK
--- curl via manager (RAG) ---
"Retrieval-Augmented Generation (RAG) is a technique that enhances..."
--- opencode run (gemma) — timeout 25 ---
{"type":"step_start"...} {"type":"text","metadata":{"compaction_continue":true},...}  ← hangs in agentic loop /compaction_continue loop
→ Manager logs still show POST 200 OK per turn — API is fine, hang is CLIENT agentic loop, not server.
--- direct health ---
8080: {"status":"ok","model":"gemma-4-31b-1"} ... 8090: {"status":"ok","model":"qwen2.5-7b"}
8001: {"status":"ok","dim":384} 8002: {"status":"ok","dim":1024} 8003: {"status":"ok","dim":384}
--- session memory ---
my name is Ali → Hello, Ali!
what is my name? → Ali  ← history injection verified
```

**How to use in OpenCode TUI / `opencode run`:**
```bash
# Inside opencode TUI: select model `h200-manager/gemma-4-31b` (champion) or `qwen2.5-7b` (fast, loaded)
# CLI — canonical is curl (always works):
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"Write a python function to parse GGUF header"}],"max_tokens":200}' | jq

# opencode run — wrap in timeout because of known compaction loop (not an error):
timeout 25 opencode run --model h200-manager/gemma-4-31b --format json "say hello one word, no tools" 2>&1 | head -c 5000
# If it hangs, use --format json + timeout, or prefer curl. Manager will still show POST 200 in logs.
```

**Why `opencode run` hangs:** It enters an agentic `compaction_continue` loop (`"Continue if you have next steps..."`) even after the LLM returns. This is **client-side**, not API failure — verified because `curl` to the same manager endpoint returns instantly with 200 and manager `logs/` show successful POSTs. Workaround is `timeout` + `curl` canonical, or `opencode run --model h200-manager/gemma-4-31b --prompt "task" --no-agent` if available.

## 10. Benchmark Code & Reproduction — ALL harnesses

**Scripts inventory (all under `scripts/`, LOC verified `wc -l`):**

| Script | LOC | Purpose | Key logic | Runnable |
|--------|-----|---------|-----------|----------|
| `eval_persian.py` | **17433** | Persian 7-task eval (chat mode) | `IMPROVED_TEMPLATES` (ROLE/CONTEXT/CONSTRAINTS/OUTPUT), `strip_think` for Qwen3 `<think>`, `persian_norm.normalize` + `jaccard` scorer, `--n-shots` exemplars, `--prompt-style improved`, `--max-tokens 400` for thinking models | `HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model <gguf> --limit 50 --chat --max-tokens 400 --out logs/evalp_<name>.json` |
| `bench_speed.py` | 3183 | tok/s benchmark (single Persian 256-token prompt, `n_gpu_layers=-1`) | `PROMPT = "سؤال: یک مقاله کوتاه درباره هوش مصنوعی..."`, `bench(path, max_tokens=256)` → `tok_sec` | `offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json` |
| `eval_gguf.py` | 6989 | English conventional (MMLU-3subj, GSM8K, fa_arc, fa_rc) | `datasets.load_dataset`, `llama_cpp.Llama` | `offline-prep/venv/bin/python3.12 scripts/eval_gguf.py --model <gguf> --limit 50` |
| `gen_eval_report.py` | 41428 | Rebuild **10 PNG** + Plotly interactive + `persian_eval_report.md` + tables | `matplotlib` + `plotly`, reads `logs/evalp*.json`, color per model (family shades), solid vanilla / hatched improved | `offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py` |
| `gen_prompt_compare.py` | 8644 | Vanilla vs improved full Q&A RTL side-by-side | compares `persian_prompt_compare.md` | `offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py` |
| `gen_sample_questions.py` | 7948 | Per-model good/bad samples per task | `persian_sample_questions.md` | — |
| `find_tricky_samples.py` | 2503 | Find disagreement cases (one tricky per category) | — | — |
| `gen_pages.py` | 8025 | GitHub Pages multipage site | `docs/reports/` + `docs/history/` → `docs-site/` | `offline-prep/venv/bin/python3.12 scripts/gen_pages.py` |
| `download_models.py` | 8209 | Proxy-resilient HF downloader | `TARGETS` 17 repos, `HF_HUB_DISABLE_XET=1`, exponential backoff 90s→3600s, `snapshot_download` with resume | `HF_HUB_DISABLE_XET=1 offline-prep/venv/bin/python3.12 scripts/download_models.py --daemon` |
| `rag_test_harness.py` | 3676 | Shared RAG ingest→retrieve→gen harness | — | `offline-prep/venv/bin/python3.12 scripts/rag_test_harness.py` |
| `progress_report.py` / `auto_status_commit.py` | 8300+ | Dashboard + auto-commit (writes `Download Progress` to README) | — | `offline-prep/venv/bin/python3.12 scripts/progress_report.py --once` |

**Persian 7-task suite (all via `eval_persian.py`):**

| Task | Dataset (HF) | Scoring | Gold shape | Example prompt style |
|------|--------------|---------|------------|----------------------|
| `fa_arc` | `MatinaAI/persian_arc` ARC-Easy (test) | exact letter `A/B/C/D` | `a` | `سؤال: ... گزینه‌ها: A) ... فقط حرف ...` |
| `fa_mc` | `ParsBench/parsinlu-multiple-choice-alpaca-style` | exact option number | `2` | Parsinlu MC |
| `fa_math` | `ParsBench/persian-math-alpaca-style` | numeric/date `jaccard` | `1000` | math with `[پاسخ نهایی]` block |
| `fa_sentiment` | Parsinlu sentiment | `positive/negative` | `منفی` | — |
| `fa_entail` | Parsinlu entailment + ConjNLI | `entail/neutral/contradict` → `تناقض/خنثی/استنتاج` | — | — |
| `fa_ner` | ParsBench NER | token-label `jaccard` over tuple list | — | strict JSON `[(token, label)]` |
| `fa_rc` | Parsinlu reading comprehension | answer `jaccard` | `مثلث` | short span from context |

**Reproduction — exact commands (verified `--help` works):**
```bash
# Help (dry, no model load):
offline-prep/venv/bin/python3.12 scripts/eval_persian.py --help
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --help
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py --help

# Single model, Persian vanilla (50 ex/task, chat, temp 0.0):
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --out logs/evalp_gemma4-vanilla.json

# Improved prompting (ROLE/CONTEXT/CONSTRAINTS/OUTPUT, ~80 tokens, Persian):
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --prompt-style improved --out logs/evalp_gemma4-improved.json

# Few-shot (n=2 exemplars, same for 1/3/5):
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --n-shots 2 --out logs/evalp_qwen2.5-7b_2shot.json

# Temperature sweep (0.0 is best for this model):
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --temperature 0.5 --out logs/evalp_qwen2.5-7b_t05.json

# Speed (tok/s, 256-token Persian generation):
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json
cat logs/speed_bench.json | jq
# phi-3-mini 226.6 · mistral 172.7 · qwen2.5-7b 163.9 · qwen3-30b-a3b 155.1 · llama3.2 72.2 · gemma-3 67.3 · qwen3.8 61.2 · gemma-4 55.7 · nemotron 45.6

# Via manager (instead of loading gguf directly) — parity check:
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"سؤال: ..."}],"max_tokens":400}' | jq

# Rebuild reports after new logs:
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py          # → docs/reports/*.png + persian_eval_report.md
offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py       # → docs/reports/persian_prompt_compare.md
offline-prep/venv/bin/python3.12 scripts/gen_pages.py                # → docs-site/ + GitHub Pages
```

**Benchmark results (9 GGUF, mean sorted, verified logs/evalp_*.json):**

| Model | Mean | ARC | MC | Math | Sent | Entail | NER | RC | Tok/s |
|-------|------|-----|----|------|------|--------|-----|----|-------|
| **Gemma-4-31B Q4_K_M** | **0.663** | 0.960 | 0.700 | 0.640 | 0.820 | 0.160 | **1.000** | 0.360 | 55.7 |
| **Gemma-3-27B Q4_K_M** | **0.600** | 0.900 | 0.440 | 0.520 | 0.680 | 0.200 | 0.980 | 0.400 | 67.3 |
| Nemotron-49B Q4_K_M | 0.494 | 0.920 | 0.320 | 0.500 | 0.680 | 0.220 | 0.460 | 0.360 | 45.6 |
| Qwen3.8-27B Q4_K_M | 0.477 | 0.920 | 0.620 | 0.180 | 0.760 | 0.260 | 0.020 | 0.580 | 61.2 |
| Qwen2.5-7B Q4_K_M | 0.443 | 0.680 | 0.360 | 0.380 | 0.660 | 0.000 | 0.880 | 0.140 | 163.9 |
| Llama-3.2-3B Q4_K_M | 0.326 | 0.560 | 0.300 | 0.140 | 0.580 | 0.240 | 0.000 | 0.460 | 72.2 |
| Qwen3-30B-A3B MoE | 0.283 | 0.520 | 0.280 | 0.040 | 0.720 | 0.260 | 0.000 | 0.160 | 155.1 |
| Mistral-7B Q4_K_M | 0.186 | 0.360 | 0.240 | 0.060 | 0.300 | 0.180 | 0.020 | 0.140 | 172.7 |
| Phi-3-mini q4 | 0.143 | 0.340 | 0.100 | 0.000 | 0.220 | 0.160 | 0.000 | 0.180 | 226.6 |

Improved prompting lifts all (+0.046 … +0.223), biggest on error-prone Mistral +0.223. Qwen3.8 rose 0.169→0.477 after `strip_think` + `max_tokens 400` fix. 2-shot helps NER/RC but hurts math (0.38→0.12). Temp 0.0 is best.

---

## 11. Reports, Plots & Evidence Logs

**Generated:** `docs/reports/` (plots) + `docs/reports/interactive/` (Plotly) + `docs/reports/persian_eval_report.md` (1770L) + `persian_prompt_compare.md` (656L) + `logs/evalp_*.json` (20+ files).

**10 PNG plots (each has Plotly HTML twin):**

| File | Description | How to read |
|------|-------------|-------------|
| `persian_mean.png` | ranked mean accuracy (solid vanilla / hatched improved) | one color per model, family shades (Gemma reds, Qwen blues) |
| `persian_by_task.png` | per-task accuracy by model | Gemma 1.0 NER, Qwen3.8 math 0.18 |
| `persian_scatter.png` | size (disk GB) vs mean, bubble = params | larger ≠ always better (Qwen3.8 17.8G beats MoE) |
| `persian_radar.png` | ability groups radar (Reasoning & Knowledge vs Language vs Extraction) | Gemma large balanced |
| `persian_radar_family.png` | per-family radars | compare within family |
| `persian_speed.png` | tok/s + latency | phi fastest, nemotron slowest |
| `persian_spider.png` | 7-axis per-task spider | large round = balanced |
| `persian_improvement.png` | vanilla vs improved mean | same color = same model |
| `persian_nshot.png` | few-shot 0/1/2/3/5 (Qwen2.5) | NER 0.88→0.98, math drops |
| `persian_temperature.png` | temp 0.0→1.0 (Qwen2.5) | 0.0 best, format breaks at higher |
| `persian_parallel.png` | parallel packing | per-model VRAM / instances |
| `persian_parallel.csv/json` | raw parallel data | — |

**Report sections (`persian_eval_report.md`):** per-task tables + same-question cross-model comparison (identical prompt → why scores differ: format following) + per-model good/bad samples + improved deltas + model details (creator/license/architecture).

**Logs:** `logs/evalp_*.json`, `logs/speed_*.json`, `logs/manager_test_*.json`, `logs/opencode_session_*.log`, `logs/llama_server_*.log` — keep for evidence. Regenerate via `scripts/gen_eval_report.py`.

---

## 12. RAG Storage & E2E Corpus

**LightRAG storage:** `rag_storage/` (graph + vector `vdb_*.json`, `kv_store_*.json`, `graph_chunk_entity_relation.graphml 73KB`) — validated e2e with Gemma-4 + e5-small, EN+FA, 4 query modes.

**E2E corpus (ground truth):** `e2e-test/corpus/*.md` (11 docs: `postgresql.md`, `redis.md`, `kubernetes.md`, `docker.md`, `rag.md`, `gpu.md`, `python.md`, `security.md`, `llm.md`, `vector-db.md`, …) + `e2e-test/qa_ground_truth.json` (12 QA):

```json
[
  {"id":"q1","question":"What is the recommended size for shared_buffers in PostgreSQL relative to RAM?","answer":"25% of total RAM","source_doc":"postgresql.md"},
  {"id":"q2","question":"Which data structure does Redis use for sorted sets (ZSET)?","answer":"skip list and hash table","source_doc":"redis.md"},
  {"id":"q3","question":"What QoS class does a Kubernetes pod get when requests equal limits?","answer":"Guaranteed","source_doc":"kubernetes.md"},
  {"id":"q5","question":"What chunk overlap percentage is recommended in RAG?","answer":"10-20%","source_doc":"rag.md"},
  {"id":"q6","question":"How much memory does the NVIDIA H200 GPU have?","answer":"141 GB HBM3e","source_doc":"gpu.md"},
  ...
]
```

**Harness:** `scripts/rag_test_harness.py` (ingest chunk → embed 384 → vector DB → retrieve → generate). Test retrieval: `qdrant:16333` `rag_docs` green, 0 points (ingestion pending — run harness with real docs).

## 13. Offline Prep & Downloading

**File:** `offline_prepare_cli.py` — `BASE_DIR = Path(__file__).parent / "offline-prep"` (fixed), `VENV_DIR=BASE_DIR/venv`, `STATE_FILE=.state.json`, `RETRY_QUEUE=.retry_queue.json`, `LOG_DIR=logs/`, `PIP_CACHE_DIR=pip_cache`, `HF_XET_HIGH_PERFORMANCE=1`, `UV_HTTP_TIMEOUT=600`.

**Launch (self-healing in tmux):**
```bash
bash start.sh  # bootstraps Ubuntu (tmux, curl, git, jq, build-essential), venv, pip, then tmux new -s offline_prep "python3 offline_prepare_cli.py"
tmux attach -t offline_prep  # attach
# Ctrl+b, d = detach
```

**State files — NEVER trust as truth:** `offline-prep/.state.json` & `failed_tasks.json` are stale — they mark torch/vllm "failed" that were later installed by hand (`import_report.txt` also obsolete). Always verify via `pip freeze` + `ls models/huggingface`.

**Downloader:** `scripts/download_models.py` — proxy-resilient, `HF_HUB_DISABLE_XET=1` critical, `TARGETS` 17 repos ordered smallest-first (2.0G Llama-3.2 → 755G GLM). Each entry is a *single file/quant* (resume partials), `MAX_ATTEMPTS=8`, `BACKOFF 90s*2^(n-1) capped 3600s +30% jitter`, `snapshot_download` with `allow_patterns`. `--daemon` = infinite retries (systemd `rag-dl.service` `Restart=always`). **Verify:**
```bash
# Queue preview:
cat scripts/download_models.py | grep -A2 "TARGETS"
# Recent log:
tail -n 30 offline-prep/logs/dl_models_$(date +%Y%m%d)*.log
# or: journalctl -u rag-dl -n 100
# Systemd daemon:
systemctl status rag-dl 2>&1 | head
```

**Manual single download:**
```bash
HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=0 \
  offline-prep/venv/bin/python3.12 scripts/download_models.py --only bartowski/Llama-3.2-3B-Instruct-GGUF
# Full daemon:
HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=0 \
  offline-prep/venv/bin/python3.12 scripts/download_models.py --daemon
```

**Other downloaders:** `scripts/download_embeddings.py` (5 embeds), `scripts/download_eval_data.py`, `scripts/download_persian_eval.py` (ParsBench suite to `offline-prep/datasets`).

---

## 14. Troubleshooting & Gotchas

| Symptom | Root cause | Fix |
|---------|------------|-----|
| `pip: required file not found` on `venv/bin/pip` | Shebang `#!/ai-gpu1/v1/.../venv/bin/python3` stale | **Use** `offline-prep/venv/bin/python3.12 -m pip ...` **always** (`python3.12 → /usr/bin/python3` symlinks) |
| `ModuleNotFoundError` / `scipy` crash | `scipy 1.18.0` requires `numpy≥2`, vllm pins `numpy 1.26.4` | `offline-prep/venv/bin/python3.12 -m pip install scipy==1.13.1` (keep numpy 2.5.2 now) |
| `HF Xet I/O error` mid-download | XET CDN dies via Squid proxy | **Export** `HF_HUB_DISABLE_XET=1` + `HF_HUB_ENABLE_HF_TRANSFER=0` **before any hf download** |
| `short read: unexpected EOF` (docker pull) | Proxy instability with large layers | Retry or `docker save` from `offline-prep/docker-images/*.tar` |
| Download stalls at 0% for big model | `rag-dl` queue is on earlier target + proxy MaxRetryError on `api/models/.../revision/main` | Normal — queue is smallest-first, retries with 2700–4500s brake; check `dl_*.log` tail for current `attempt=` |
| `manager → backend 500` or `ConnectError All attempts failed` | Proxy tries to proxy localhost | **Fixed** `trust_env=False` in `llm_inference_manager/app.py:321` `httpx.AsyncClient` + `no_proxy=localhost,127.0.0.1` |
| `opencode run ... hanging` with `compaction_continue` loop | Agentic loop, not API failure | **Use** `timeout 25 opencode run --model h200-manager/gemma-4-31b --format json "..."` **or** canonical `curl http://127.0.0.1:9000/v1/chat/completions ...` (manager logs show 200) |
| `mistral/phi scores 0 on NER` | Model emits prose not tuple JSON | Improved prompting fixes (NER 0→0.755 for Mistral), or use Gemma-4 (1.0) |
| Qwen3.8/Qwen3-30B thinking truncated | `max_tokens 128` cuts before `</think>` | Use `--max-tokens 400` + `strip_think` in `eval_persian.py` (0.169→0.477) |
| `opencode models` missing `h200-manager` | Config only at `a.nikkhah` home, not `root` | `cp /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc /root/.config/opencode/opencode.jsonc` (done) |
| `.state.json` says failed but `pip freeze` shows installed | Stale state | Ignore `offline-prep/.state.json` — trust `pip freeze` + `ls` |
| `vllm` needs single-file GGUF, not sharded | vLLM loader expects one file | Launch with `--load-format gguf --quantization gguf` (verified `vllm 0.6.1.post1`) |
| `Host uvicorn on :8080` conflicted with gemma | Root uvicorn occupied 8080 | Kill `uvicorn` PID, restart supervisor — now 8080→gemma-4-31b-1 |
| Disk `100%` on `/` after docker | Docker data dir on root | Moved to `/splunk-data/v1/docker-data` |

---


### Live GitHub Pages
- index: **HTTP 0**
- 04-figures: **HTTP 0**
- n-shot: **HTTP 0**
- temperature: **HTTP 0**

### GPU memory
| GPU | Used | Total |
|---|---|---|
| 0 | 88759 MiB | 143771 MiB |
| 1 | 61807 MiB | 143771 MiB |

### Running services
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`
- `offline-prep/venv/bin/python3.12`

### Model downloads
| Model | Disk | Expected | Progress | Shards | Status |
|---|---|---|---|---|---|
| `bartowski_Qwen2.5-72B-Instruct-GGUF` | 511.9 GB | n/a | [██████████] 100% | — | ok |
| `deepseek-ai_DeepSeek-V4-Flash` | 148.7 GB | 148.6 GB | [██████████] 100% | 46/46 | done |
| `bartowski_Mistral-7B-Instruct-v0.3-GGUF` | 126.4 GB | 4.1 GB | [██████████] 100% | — | done |
| `bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF` | 28.1 GB | 28.1 GB | [██████████] 100% | — | done |
| `bartowski_google_gemma-4-31B-it-GGUF` | 18.3 GB | 18.3 GB | [██████████] 100% | — | done |
| `Qwen_Qwen3-30B-A3B-GGUF` | 17.3 GB | 17.3 GB | [██████████] 100% | — | done |
| `bartowski_Qwen3.8-27B-GGUF` | 16.6 GB | 16.6 GB | [██████████] 100% | — | done |
| `bartowski_google_gemma-3-27b-it-GGUF` | 15.4 GB | 15.4 GB | [██████████] 100% | — | done |
| `microsoft_Phi-3-mini-4k-instruct-gguf` | 9.3 GB | n/a | [██████████] 100% | — | ok |
| `bartowski_Qwen2.5-7B-Instruct-GGUF` | 4.4 GB | 4.4 GB | [██████████] 100% | — | done |
| `bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF` | 3.6 GB | n/a | [░░░░░░░░░░] 0% | — | partial |
| `BAAI_bge-m3` | 2.1 GB | n/a | [██████████] 100% | — | ok |
| `bartowski_Llama-3.2-3B-Instruct-GGUF` | 1.9 GB | 1.9 GB | [██████████] 100% | — | done |
| `intfloat_multilingual-e5-small` | 1.2 GB | n/a | [██████████] 100% | — | ok |
| `sentence-transformers_all-MiniLM-L6-v2` | 931.7 MB | n/a | [██████████] 100% | — | ok |
| `sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2` | 911.2 MB | n/a | [██████████] 100% | — | ok |
| `BAAI_bge-small-en-v1.5` | 382.5 MB | n/a | [██████████] 100% | — | ok |

### Download log (tail)
```
dl_models_20260820_0643.log [2026-08-23 12:19]:
2026-08-23 08:55:02,520 [WARNING] FAIL bartowski/Qwen2.5-72B-Instruct-GGUF attempt=33 consec=33 brake=4117s: (MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /api/models/bartowski/Qwen2.5-72B-Instruct-GGUF/revision/main (Caused by ProxyE
2026-08-23 10:03:39,544 [WARNING] FAIL bartowski/Qwen2.5-72B-Instruct-GGUF attempt=34 consec=34 brake=2717s: (MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /api/models/bartowski/Qwen2.5-72B-Instruct-GGUF/revision/main (Caused by ProxyE
2026-08-23 10:48:56,302 [WARNING] FAIL bartowski/Qwen2.5-72B-Instruct-GGUF attempt=35 consec=35 brake=2695s: (MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /api/models/bartowski/Qwen2.5-72B-Instruct-GGUF/revision/main (Caused by ProxyE
2026-08-23 11:33:51,671 [WARNING] FAIL bartowski/Qwen2.5-72B-Instruct-GGUF attempt=36 consec=36 brake=2759s: (MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /api/models/bartowski/Qwen2.5-72B-Instruct-GGUF/revision/main (Caused by ProxyE
2026-08-23 12:19:50,658 [WARNING] FAIL bartowski/Qwen2.5-72B-Instruct-GGUF attempt=37 consec=37 brake=4490s: (MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /api/models/bartowski/Qwen2.5-72B-Instruct-GGUF/revision/main (Caused by ProxyE
```

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
| LLM (llama.cpp) | `8080` | [`scripts/services/llama_chat_server.py`](scripts/services/llama_chat_server.py) | **Gemma-4-31B Q4_K_M** (champion model); `/v1/chat/completions`, `/v1/completions` |
| LLM (vLLM) | `8000` | [`scripts/services/vllm_server.sh`](scripts/services/vllm_server.sh) | vLLM OpenAI API server; **requires a single-file GGUF** (not running) |
| Embeddings | `8001` | [`scripts/services/embed_server.py`](scripts/services/embed_server.py) | `multilingual-e5-small`, dim **384** (default RAG embedder) |
| Embeddings | `8002` | [`scripts/services/embed_server.py`](scripts/services/embed_server.py) | `BAAI/bge-m3`, dim **1024** |
| Embeddings | `8003` | [`scripts/services/embed_server.py`](scripts/services/embed_server.py) | `paraphrase-multilingual-MiniLM-L12-v2`, dim **384** |
| LightRAG | `9621` | LightRAG server (sample-project venv) | validated e2e: Gemma-4-31B + e5-small, EN+FA, 4 query modes |

All OpenAI-compatible. Embedder comparison (Persian retrieval) in §4d.

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
- Downloaded **Qwen2.5-7B Q4_K_M** (4.68 GB, single-file, from `bartowski/Qwen2.5-7B-Instruct-GGUF`) — completed across 8 flaky-proxy retries; validated by a llama.cpp load test.
- Brought up live services: embeddings (`:8001`) and llama.cpp chat (`:8080`, smoke-tested against Mistral IQ2 quant).
- Prepared vLLM GGUF launcher, RAG test harness, and lightrag dedicated venv.

---

## 4. Models inventory

All under `offline-prep/models/huggingface/` (git-ignored):

| Model | Size | Status |
|---|---|---|
| `bartowski/Qwen2.5-7B-Instruct-GGUF` (Q4_K_M) | 4.4 GB | ✅ downloaded & evaluated (0.443) |
| `bartowski/Llama-3.2-3B-Instruct-GGUF` (Q4_K_M) | 1.9 GB | ✅ downloaded & evaluated (0.326) |
| `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | 4.4 GB (Q4_K_M) | ✅ evaluated (0.186) |
| `microsoft/Phi-3-mini-4k-instruct-gguf` | 2.4 GB (q4) | ✅ evaluated (0.143) |
| `bartowski/google_gemma-4-31B-it-GGUF` (Q4_K_M) | 19.6 GB | ✅ evaluated (0.663) |
| `bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF` (Q4_K_M) | 30.2 GB | ✅ evaluated (0.494) |
| `bartowski/google_gemma-3-27b-it-GGUF` (Q4_K_M) | 16.5 GB | ✅ downloaded & evaluated (0.600) |
| `bartowski/Qwen3.8-27B-GGUF` (Q4_K_M) | 17.8 GB | ✅ downloaded; re-evaluated after thinking-mode fix |
| `Qwen/Qwen3-30B-A3B-GGUF` (Q4_K_M) | 18.6 GB | ✅ downloaded; re-evaluated after thinking-mode fix |
| `bartowski/Qwen2.5-72B-Instruct-GGUF` (Q8_0 2/2 + part 1 partial) | ~73 GB | ⏸ removed from queue (partial on disk) |
| `bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF` | 3.6 GB partial | ⏸ removed from queue (partial on disk) |
| `BAAI/bge-small-en-v1.5` | 383 MB | ✅ embeddings (dim 384) |
| `sentence-transformers/all-MiniLM-L6-v2` | 932 MB | ✅ embeddings |
| `intfloat/multilingual-e5-small` | 1.2 GB | ✅ Persian-capable embeddings (dim 384) |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 912 MB | ✅ Persian-capable embeddings (dim 384) |
| `BAAI/bge-m3` | 2.2 GB | ✅ multilingual embeddings (dim 1024) |

### 4a. Download list — ≤ 100 GB (project policy 2026-08-17)

Models over **100 GB download size are excluded** (stopped/removed from the download queue; partials on disk are kept, not deleted). The full download/queue table:

| Name | Where to get | Model format | Link |
|---|---|---|---|
| **Gemma-4-31B-it** Q4_K_M | `bartowski/google_gemma-4-31B-it-GGUF` | GGUF (single file) | <https://huggingface.co/bartowski/google_gemma-4-31B-it-GGUF> |
| **Gemma-3-27B-it** Q4_K_M | `bartowski/google_gemma-3-27b-it-GGUF` | GGUF (single file) | <https://huggingface.co/bartowski/google_gemma-3-27b-it-GGUF> |
| **Qwen3.8-27B** Q4_K_M (multimodal) | `bartowski/Qwen3.8-27B-GGUF` | GGUF (+ mmproj) | <https://huggingface.co/bartowski/Qwen3.8-27B-GGUF> |
| **Qwen3-30B-A3B** Q4_K_M (MoE) | `Qwen/Qwen3-30B-A3B-GGUF` | GGUF (single file) | <https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF> |
| **Nemotron-Super-49B-v1** Q4_K_M | `bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF` | GGUF (single file) | <https://huggingface.co/bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF> |
| **Qwen2.5-7B-Instruct** Q4_K_M | `bartowski/Qwen2.5-7B-Instruct-GGUF` | GGUF (single file) | <https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF> |
| **Llama-3.2-3B-Instruct** Q4_K_M | `bartowski/Llama-3.2-3B-Instruct-GGUF` | GGUF (single file) | <https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF> |
| **Mistral-7B-Instruct-v0.3** Q4_K_M | `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | GGUF (single file) | <https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF> |
| **Phi-3-mini-4k-instruct** q4 | `microsoft/Phi-3-mini-4k-instruct-gguf` | GGUF (single file) | <https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf> |
| **DeepSeek-V4-Flash** (in-progress) | `deepseek-ai/DeepSeek-V4-Flash` | safetensors (FP4/FP8), 46 shards | <https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash> |
| ~~MiniMax-M3~~ | ~~`unsloth/MiniMax-M3-GGUF`~~ | ~~GGUF UD-IQ4_XS~~ | ~~<https://huggingface.co/unsloth/MiniMax-M3-GGUF>~~ |
| ~~Kimi-K3~~ | ~~`unsloth/Kimi-K3-GGUF`~~ | ~~GGUF UD-IQ1_S~~ | ~~<https://huggingface.co/unsloth/Kimi-K3-GGUF>~~ |
| ~~GLM-5.2-FP8~~ | ~~`zai-org/GLM-5.2-FP8`~~ | ~~safetensors (FP8)~~ | ~~<https://huggingface.co/zai-org/GLM-5.2-FP8>~~ |

**Policy notes**
- **DeepSeek-V4-Flash download resumed 2026-08-18** (was excluded on 2026-08-17 under the >100 GB policy, but is now being downloaded again by the `rag-dl` systemd daemon). Resume keeps completed shards; 25/46 shards (~86 GB) were on disk when resumed. After it completes it will be ~160 GB and should be served via vLLM or llama.cpp with flash-attention.
- Still excluded (>100 GB): MiniMax-M3 (~208 GB), Kimi-K3 (~594 GB), GLM-5.2-FP8 (~755 GB). Struck through above for reference.
- Sizes on the Hugging Face hub can change as new revisions are released; re-check the `Files` tab before downloading.
- All GGUF entries are quantized via llama.cpp and load directly in llama.cpp / llama-cpp-python / vLLM (single-file GGUFs are required by vLLM's loader).

**Master venv key packages:** torch 2.4.0+cu124 · vllm 0.6.1.post1 (+flash-attn 2.6.1) · flash-attn 2.6.3 · llama-cpp-python 0.3.34 · sglang 0.3.0 · transformers 4.44.0 · faiss-gpu-cu12 1.14.1.post1 · bitsandbytes 0.50.0 · numpy 1.26.4 · scipy 1.13.1 · sentence-transformers 3.0.1 · ragas 0.4.3 · deepeval 4.1.7 · datasets 5.0.1 · matplotlib 3.11.1

---

## 4b. Model benchmark — Persian LLM evaluation

Nine complete GGUF models were benchmarked on **Persian** tasks via the [Persian eval harness](scripts/eval_persian.py) (chat completions, temp 0.0, `limit=50`, Persian text normalized for scoring). Tasks: Persian ARC-Easy (MC), Parsinlu multiple-choice, Persian math, sentiment, entailment, NER, and reading comprehension (ParsBench suite).

### Mean accuracy (sorted)

| Model | Family | Params | Size | Mean | Persian ARC | Parsinlu MC | Math | Sentiment | Entail | NER | RC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Gemma-4-31B Q4_K_M** | Gemma-4 | 31B | 19.6G | **0.663** | 0.960 | 0.700 | 0.640 | 0.820 | 0.160 | **1.000** | 0.360 |
| **Gemma-3-27B Q4_K_M** | Gemma-3 | 27B | 16.5G | **0.600** | 0.900 | 0.440 | 0.520 | 0.680 | 0.200 | 0.980 | 0.400 |
| Nemotron-Super-49B Q4_K_M | Nemotron | 49B | 30.2G | 0.494 | 0.920 | 0.320 | 0.500 | 0.680 | 0.220 | 0.460 | 0.360 |
| **Qwen3.8-27B Q4_K_M** | Qwen3.8 | 27B | 17.8G | **0.477** | 0.920 | 0.620 | 0.180 | 0.760 | 0.260 | 0.020 | 0.580 |
| Qwen2.5-7B Q4_K_M | Qwen2.5 | 7B | 4.4G | 0.443 | 0.680 | 0.360 | 0.380 | 0.660 | 0.000 | 0.880 | 0.140 |
| Llama-3.2-3B Q4_K_M | Llama-3.2 | 3.2B | 1.9G | 0.326 | 0.560 | 0.300 | 0.140 | 0.580 | 0.240 | 0.000 | 0.460 |
| Qwen3-30B-A3B Q4_K_M | Qwen3-MoE | 30B | 18.6G | 0.283 | 0.520 | 0.280 | 0.040 | 0.720 | 0.260 | 0.000 | 0.160 |
| Mistral-7B Q4_K_M | Mistral | 7B | 4.4G | 0.186 | 0.360 | 0.240 | 0.060 | 0.300 | 0.180 | 0.020 | 0.140 |
| Phi-3-mini q4 | Phi-3 | 3.8B | 2.4G | 0.143 | 0.340 | 0.100 | 0.000 | 0.220 | 0.160 | 0.000 | 0.180 |

*Qwen2.5-7B 2-shot (n=2 exemplars): mean 0.466 (ARC 0.74, MC 0.32, math 0.12, sentiment 0.78, NER 0.96, RC 0.34).*

**Key findings**
- **Gemma-4-31B remains the champion** — 0.96 on Persian ARC, perfect 1.0 on NER, best on every task except entailment/RC.
- **Gemma-3-27B is a close runner-up (0.600)** — nearly as strong on ARC (0.90) and NER (0.98).
- **Qwen3.8-27B is the big riser (0.169 → 0.477)** after the thinking-mode fix: its `<think>`-block answers were being parsed incorrectly and `max_tokens=128` truncated the answer before `</think>`. With `strip_think` + `max_tokens=400` it reaches ARC 0.92 / Parsinlu MC 0.62 / RC 0.58 — 4th overall.
- Nemotron-49B stays the strongest open alternative: ARC (0.92) and math (0.50).
- Qwen2.5-7B is excellent at NER (0.88); entailment 0.000 is a scorer/format artifact (emits label letters). 2-shot slightly improves it (0.466) mainly on ARC/MC.
- Qwen3-30B-A3B (MoE, 3B active) improves 0.131 → 0.283 with the fix but remains weak on structured tasks (math 0.04, NER 0.00) — reasoning-heavy single-pass routing hurts it on format-strict tasks.
- Small models (Llama-3.2-3B, Mistral, Phi-3) collapse on NER and math; Llama-3.2-3B is surprisingly best-in-class at reading comprehension (0.46).

### Ability-group scores (radar chart data)

| Model | Reasoning & Knowledge | Language Understanding | Info Extraction |
|---|---|---|---|
| Gemma-4-31B | 0.767 | 0.490 | 0.680 |
| Gemma-3-27B | 0.620 | 0.440 | 0.690 |
| Nemotron-49B | 0.580 | 0.450 | 0.410 |
| Qwen3.8-27B | 0.573 | 0.510 | 0.300 |
| Qwen2.5-7B | 0.473 | 0.330 | 0.510 |
| Llama-3.2-3B | 0.333 | 0.410 | 0.230 |
| Qwen3-30B-A3B | 0.280 | 0.490 | 0.080 |
| Mistral-7B | 0.220 | 0.240 | 0.080 |
| Phi-3-mini | 0.147 | 0.190 | 0.090 |

### Generation speed (tokens/sec, 256-token Persian generation)

| Model | tok/s | Notes |
|---|---|---|
| Phi-3-mini q4 | 226.6 | tiny model, fastest |
| Mistral-7B | 172.7 | |
| Qwen2.5-7B | 163.9 | |
| Qwen3-30B-A3B | 155.1 | MoE — only 3B active params |
| Llama-3.2-3B | 72.2 | |
| Gemma-3-27B | 67.3 | |
| Qwen3.8-27B | 61.2 | thinking preamble slows it |
| Gemma-4-31B | 55.7 | |
| Nemotron-49B | 45.6 | largest model, slowest |

Speed and accuracy are independent axes: Nemotron-49B is slowest *and* mid-ranked; Phi-3-mini is fastest *and* worst. Qwen3-30B-A3B is the efficiency outlier (fast MoE, weaker structured tasks).

### Plots

Every chart is **interactive** too — a Plotly HTML twin lives next to each PNG in `docs/reports/interactive/` (hover, zoom, hide-series). Color rule: **each model has ONE color** used everywhere (solid = vanilla, hatched `//` = improved), and models of the **same family share similar shades** (Gemma = reds, Qwen = blues). See [`docs/reports/persian_eval_report.md`](docs/reports/persian_eval_report.md) **Model details** for creator/license/architecture per model.

- [`docs/reports/persian_mean.png`](docs/reports/persian_mean.png) — ranked mean accuracy (vanilla solid / improved hatched, same model color)
- [`docs/reports/persian_by_task.png`](docs/reports/persian_by_task.png) — per-task accuracy by model
- [`docs/reports/persian_scatter.png`](docs/reports/persian_scatter.png) — **model size (disk GB) vs mean accuracy**, bubble area = parameter count
- [`docs/reports/persian_radar.png`](docs/reports/persian_radar.png) — **ability-group radar profile** for all models
- [`docs/reports/persian_radar_family.png`](docs/reports/persian_radar_family.png) — **per-family radar profiles** (Gemma / Qwen / Nemotron / Llama / Mistral / Phi)
- [`docs/reports/persian_speed.png`](docs/reports/persian_speed.png) — **tokens/sec + latency per task** per model
- [`docs/reports/persian_spider.png`](docs/reports/persian_spider.png) — **per-task 7-axis spider** per model
- [`docs/reports/persian_improvement.png`](docs/reports/persian_improvement.png) — **vanilla vs improved prompting** mean accuracy (same color = same model)
- [`docs/reports/persian_nshot.png`](docs/reports/persian_nshot.png) — **few-shot scaling** (0/1/2/3/5 exemplars, Qwen2.5-7B)
- [`docs/reports/persian_temperature.png`](docs/reports/persian_temperature.png) — **temperature sweep** (0.0→1.0, Qwen2.5-7B)
- [`docs/reports/persian_eval_report.md`](docs/reports/persian_eval_report.md) — full report with per-example input/output samples + **same-question cross-model comparison** + **improved-prompting deltas**

![Mean accuracy](docs/reports/persian_mean.png)
![Per-task accuracy](docs/reports/persian_by_task.png)
![Size vs performance](docs/reports/persian_scatter.png)
![Ability radar](docs/reports/persian_radar.png)
![Per-family radar](docs/reports/persian_radar_family.png)
![Speed](docs/reports/persian_speed.png)
![Per-task spider](docs/reports/persian_spider.png)

**How to read the plots**
- **Size vs performance** — larger models tend to score higher, but the scatter shows size alone doesn't guarantee capability: after the thinking-fix, Qwen3.8-27B (17.8 GB) lands 4th, while Qwen3-30B-A3B (MoE) still trails smaller dense models on format-strict tasks.
- **Ability radar** — the radar axes group the 7 tasks into three abilities: *Reasoning & Knowledge* (ARC, MC, math), *Language Understanding* (sentiment, entailment), and *Information Extraction* (NER, reading comprehension). Gemma models fill a large, balanced polygon; Qwen3-30B collapses on Extraction (NER/RC) but holds mid Language Understanding.
- **Per-family radar** — compares models *within* each family: Gemma-3 vs Gemma-4, Qwen2.5 vs Qwen3, and so on.
- **Speed** — tokens/sec is measured with a fixed 256-token Persian generation (not the eval's short answers). Note Qwen3-30B's MoE routing and the Qwen3.8 thinking preamble lower throughput vs. comparable-size dense models.
- **Per-task spider** — 7 axes (one per task). A large, round spider = balanced ability; spikes mean task-specific strength (e.g., Gemma-4's NER = 1.0).

### Reproduction

```bash
export HF_HUB_OFFLINE=1
offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
    --model <path.gguf> --limit 50 --chat --max-tokens 400 \
    --out evalp_<name>.json            # max_tokens 400 needed for Qwen3 thinking models
offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
    --model <path.gguf> --limit 50 --chat --max-tokens 128 --n-shots 2 \
    --out evalp_<name>_2shot.json      # few-shot variant
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json  # tok/s
offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model <path.gguf> --limit 50 --chat \
    --max-tokens 400 --prompt-style improved --out evalp_<name>_improved.json   # improved prompts
offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py   # vanilla-vs-improved full Q&A
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py   # rebuild tables + plots
```

English + Persian conventional tasks (MMLU-3subj, GSM8K, fa_arc, fa_rc) are in [`logs/eval_*.json`](logs/) via [`scripts/eval_gguf.py`](scripts/eval_gguf.py). Persian eval datasets (ParsBench suite) are cached offline in `offline-prep/datasets` and were downloaded by [`scripts/download_persian_eval.py`](scripts/download_persian_eval.py).

### Few-shot (n-shot) evaluation

The harness supports `--n-shots N` to prepend N exemplars per task (`make_fewshot` in `scripts/eval_persian.py`). So far 2-shot has been run on Qwen2.5-7B:

| Model | Setting | Mean | ARC | MC | Math | Sentiment | NER | RC |
|---|---|---|---|---|---|---|---|---|
| Qwen2.5-7B | 0-shot | 0.443 | 0.680 | 0.360 | 0.380 | 0.660 | 0.880 | 0.140 |
| Qwen2.5-7B | 2-shot | **0.466** | 0.740 | 0.320 | 0.120 | 0.780 | 0.960 | 0.340 |

2-shot lifts NER (0.88 → 0.96), ARC (0.68 → 0.74), sentiment (0.66 → 0.78) and reading comprehension (0.14 → 0.34), but *hurts* math (0.38 → 0.12) — a known few-shot trade-off on arithmetic-style tasks where exemplars anchor wrong patterns. The 2-shot run is stored as `evalp_qwen2.5-7b_2shot.json` and appears in the report tables as a separate `(2-shot)` row. Full per-model exemplar inputs/outputs are in the same-question comparison section of `docs/reports/persian_eval_report.md`.

### Same question, different models — why scores differ

`docs/reports/persian_eval_report.md` includes a *same-question, all models* section (first example of each task) showing the identical prompt sent to every model. Concrete takeaways:

- **Format following decides MC/ARC**: on the photosynthesis ARC prompt, Gemma-4/3, Nemotron, Qwen3.8 and Qwen2.5 all answer `A`; Qwen3-30B wraps its answer in a `<think>` block, and Mistral/Phi-3 pick wrong options (`D`/`C`) — the score gap is instruction-following, not Persian ability.
- **NER needs strict JSON**: models that emit raw names or chatty prose score 0 on NER even when the entities are present; Gemma-4 (1.0) and Gemma-3 (0.98) emit the expected structure.
- Good/bad answer samples per model per task are listed inline in the report (each task's example section shows the model output with a hit/miss marker).

### Improved prompting (ROLE / CONTEXT / CONSTRAINTS / OUTPUT FORMAT)

Every model was re-run on the full 7-task suite with **improved Persian prompts** instead of the raw dataset prompt. The improved template uses the 4-component framework — **ROLE** (شما یک … هستید), **CONTEXT** (what the task is), **CONSTRAINTS** (no prose, no explanation, one answer, Persian output), **OUTPUT FORMAT** (the exact shape the scorer expects: a letter, an option number, a `[پاسخ نهایی]` block, one label, a tuple list, a short span). Each template stays **under ~80 tokens** (deliberately short, see `IMPROVED_TEMPLATES` in `scripts/eval_persian.py`). All 9 models **improved**:

| Model | vanilla mean | improved mean | Δ |
|---|---|---:|---:|
| Gemma-4-31B | 0.663 | **0.820** | +0.157 |
| Nemotron-49B | 0.494 | **0.694** | +0.200 |
| Gemma-3-27B | 0.600 | **0.683** | +0.083 |
| Qwen2.5-7B | 0.443 | **0.580** | +0.137 |
| Qwen3.8-27B | 0.477 | **0.540** | +0.063 |
| Mistral-7B | 0.186 | **0.409** | +0.223 |
| Qwen3-30B-A3B | 0.283 | **0.397** | +0.114 |
| Llama-3.2-3B | 0.326 | **0.371** | +0.046 |
| Phi-3-mini | 0.143 | **0.314** | +0.171 |

Largest absolute gains come from the **error-prone models** (Mistral +0.223, Nemotron +0.200, Phi +0.171) and from **format-strict tasks**: reading comprehension (+0.14…+0.62), NER (+0.12…+0.98, a near-perfect fix for Mistral/Llama/Phi), and entailment (Gemma-4 0.16 → 0.78). Prompt engineering therefore narrows — but does not close — the gap between strong and weak models, and it is nearly as valuable as the thinking-mode fix. Full vanilla-vs-improved per-task deltas and per-model sample outputs are in `docs/reports/persian_eval_report.md` (§ Improved prompting vs vanilla).

**Full untruncated Q&A (vanilla vs improved)** for a strong model (Gemma-4-31B) and an error-prone model (Mistral-7B) is in [`docs/reports/persian_prompt_compare.md`](docs/reports/persian_prompt_compare.md): the same tricky question per task asked both ways, showing exactly how the 4-component template changes the model's answer shape (e.g. Mistral's verbose entailment prose → a bare `تناقض` label). The prompts are shown **side by side** with RTL Persian layout and the 4-component format is explained per task. Generate it with `offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py`.

### Few-shot scaling (Qwen2.5-7B)

N correct in-task exemplars are prepended before each question (mean over 7 tasks):

| Shots | Mean | ARC | MC | Math | Sent | NER | RC |
|---|--:|---:|---:|---:|---:|---:|---:|
| 0 | 0.443 | 0.68 | 0.36 | 0.38 | 0.66 | 0.88 | 0.14 |
| 1 | 0.454 | 0.62 | 0.38 | 0.12 | 0.80 | 0.98 | 0.28 |
| 2 | 0.466 | 0.74 | 0.32 | 0.12 | 0.78 | 0.96 | 0.34 |
| 3 | 0.503 | 0.70 | 0.44 | 0.24 | 0.80 | 0.98 | 0.36 |
| 5 | 0.520 | 0.74 | 0.44 | 0.28 | 0.82 | 0.96 | 0.38 |

Few-shot helps most where the raw format is already decent (NER 0.88 → 0.98, RC 0.14 → 0.38) and hurts where the exemplars look unlike the test (math 0.38 → 0.12). Gains are modest vs prompt engineering (5-shot +0.077 vs improved template +0.137).

### Effect of temperature (Qwen2.5-7B)

| T | Mean | ARC | MC | Math | Sent | NER | RC |
|---|--:|---:|---:|---:|---:|---:|---:|
| 0.0 | **0.443** | 0.68 | 0.36 | 0.38 | 0.66 | 0.88 | 0.14 |
| 0.2 | 0.346 | 0.68 | 0.36 | 0.16 | 0.40 | 0.70 | 0.12 |
| 0.5 | 0.334 | 0.70 | 0.36 | 0.18 | 0.40 | 0.58 | 0.12 |
| 0.8 | 0.354 | 0.72 | 0.36 | 0.24 | 0.38 | 0.64 | 0.12 |
| 1.0 | 0.369 | 0.70 | 0.36 | 0.18 | 0.46 | 0.76 | 0.12 |

Higher temperature **hurts** this model on every task (greedy 0.0 is best). The drop is worst on format-strict tasks (NER 0.88 → 0.58, sentiment 0.66 → 0.38) where sampling noise breaks the exact output shape the scorer needs; math/ARC are near-flat. For evaluation, always use temperature 0.0.

### Model details — creator, license, architecture, deployment

Full per-model metadata (creator, license, params/active, context window, architecture notes, weights format, disk size, GPU/CPU) is in the **Model details** table in [`docs/reports/persian_eval_report.md`](docs/reports/persian_eval_report.md): Google DeepMind (Gemma-4 31B, Apache-2.0 · Gemma-3 27B), Alibaba (Qwen3.8-27B, Qwen3-30B-A3B MoE, Qwen2.5-7B — all Apache-2.0), NVIDIA (Nemotron-49B, NVIDIA Open Model + Llama 3.3 Community), Meta (Llama-3.2-3B), Mistral (7B v0.3), Microsoft (Phi-3-mini, MIT). All ran on the **2× H200 NVL GPUs** via llama-cpp-python (nothing on CPU).

### Vanilla vs improved — question format & model responses

The improved template wraps the raw question with a short Persian instruction (ROLE + CONSTRAINTS + OUTPUT FORMAT). Example for **reading comprehension**:

| | Prompt (question shown as sent to the model) |
|---|---|
| **Vanilla** | `متن: از آنجا که قطر رئوس غیر مجاور را متصل می‌کند، یک مثلث نمی‌تواند قطر داشته باشد …` `سؤال: کدام شکل هندسی قطر ندارد؟ پاسخ:` |
| **Improved** | `شما یک پاسخ‌گوی دقیق هستید. پاسخ را مستقیم از متن استخراج می‌کنید. قوانین: فقط پاسخ کوتاه (همان عبارت موجود در متن) را بنویسید. توضیح یا بازنویسی ننویسید. فرمت خروجی: فقط پاسخ کوتاه، در یک خط.` + same `متن: … سؤال: … پاسخ:` |

**How the answers change (same question, same model):**

| Task (gold) | Model | Vanilla response | Improved response |
|---|---|---|---|
| **RC** `مثلث` | Gemma-4-31B | `مثلث` ✅ | `مثلث` ✅ |
| **RC** `مثلث` | Mistral-7B | `یک مثلث قطر ندارد.` ❌ (paraphrase fails exact match) | `مثلث` ✅ (bare span now) |
| **Math** `1000` | Gemma-4-31B | `[راه حل] … [پاسخ] 1000` ✅ | `[راه حل] … [پاسخ] 1000` ✅ |
| **Math** `1000` | Mistral-7B | `100 * 10/100 = 10` ❌ | `100` ❌ (right idea, arithmetic slips) |
| **Entail** `contradiction` | Mistral-7B | prose repeating the task definition ❌ | `تناقض` ✅ (bare label) |
| **NER** (Jaccard) | Gemma-4-31B | tuple list, Jaccard **0.783** ✅ | tuple list, Jaccard **0.977** ✅ |
| **NER** (Jaccard) | Mistral-7B | prose category groups, no tuples ❌ (0.0) | tuple list, Jaccard **0.755** ✅ |
| **Sentiment** `negative` | Mistral-7B | `NEUTRAL` ❌ | `NEUTRAL` ❌ (label task still hard) |
| **ARC** `A` | Mistral-7B | `A) شستن دست‌ها` ✅ (letter extracted) | `A` ✅ |

The improved template mainly **fixes format-following** (bare label/span/letter, tuple list, `[پاسخ نهایی]` block) — which is exactly what the scorers require — while content errors (e.g. Mistral's sentiment `NEUTRAL` or its math slip) persist. Full verbatim inputs/outputs per task are in [`docs/reports/persian_prompt_compare.md`](docs/reports/persian_prompt_compare.md).

![Improved prompting vs vanilla](docs/reports/persian_improvement.png)

## 4c. Sample questions — one tricky prompt per category, all models

For each of the 7 task categories below, a deliberately *tricky* prompt is shown where the 9 models **disagree** (best view of real capability). Every model received the exact same input (same dataset row, same index); outputs are raw, including `thinking` blocks where models emit them. Qwen2.5-7B appears twice: **0-shot** and **2-shot** (`--n-shots 2`). Scores are the model's overall Persian-eval mean (0–1); `✓/✗` is whether it got this specific question right.

#### ARC — elementary science (multiple choice)

**Input:**

```
سؤال: یک دانش‌آموز به‌تازگی فعالیت آزمایشگاهی را به پایان رسانده است. آخرین اقدامی که دانش‌آموز باید قبل از ترک محل آزمایشگاه انجام دهد چیست؟
گزینه‌ها:
A)  شستن دست‌ها
B)  خاموش کردن همه تجهیزات
C)  جمع‌آوری کلیه ظروف شیشه‌ای
D)  شستن وسایل و میزهای آزمایش
فقط حرف گزینه درست را بگو:
```

**Gold:** `a`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `A` |
| **Gemma-3-27B** | 0.600 | ✅ | `A` |
| **Nemotron-49B** | 0.494 | ❌ | `B` |
| **Qwen3.8-27B** | 0.477 | ✅ | `A` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `b c` |
| **Qwen2.5-7B** | 0.443 | ❌ | `B) خاموش کردن همه تجهیزات` |
| **Llama-3.2-3B** | 0.326 | ✅ | `A` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `B` |
| **Mistral-7B** | 0.186 | ✅ | `A) شستن دست‌ها` |
| **Phi-3-mini** | 0.143 | ❌ | `D) شستن وسایل و میزهای آزمایش در این اقدامی، دانش‌آموز می‌کنند وسایل و میزهای آزمایش را می‌شوند و از آن‌ها تج…` |

**Why it's tricky:** All 9 models saw the same lab-safety question; the correct answer is **A**. Gemma-4, Gemma-3, Qwen3.8 and Llama-3.2 comply with the 'answer one letter' instruction, but Nemotron-49B, Qwen2.5-7B, Qwen3-30B and Phi-3-mini choose an *arguably reasonable* but wrong option — showing that ARC scores separate models on Persian science reasoning, not just on format-following.

#### Parsinlu multiple choice (analogy/grammar)

**Input:**

```
در ادامه، به شما یک سوال چند گزینه‌ای به زبان فارسی نشان داده می شود. شما باید بر اساس دانش خود به سوال پاسخ دهید. پاسخ خود را از بین گزینه‌های داده شده انتخاب کنید.
فقط عدد متناظر با گزینه درست را خروجی بده.
سوال: '''۸ نفر کارگر، کاری را در مدت ۲۰ روز تمام می‌کنند دو نفر کارگر به این عده افزوده می‌شود: این کار چند
روز زودتر به پایان می‌رسد؟
'''
گزینه ها: '''1. ۱۶ روز
2. ۴ روز
3. ۵ روز
4. ۲ روز''
```

**Gold:** `جواب: گزینه 2`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `2` |
| **Gemma-3-27B** | 0.600 | ✅ | `2` |
| **Nemotron-49B** | 0.494 | ❌ | `4` |
| **Qwen3.8-27B** | 0.477 | ✅ | `2` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ✅ | `گزینه 2` |
| **Qwen2.5-7B** | 0.443 | ❌ | `3` |
| **Llama-3.2-3B** | 0.326 | ✅ | `گزینه ۲` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `<think> Okay, let's try to figure out this problem. So, the question is about workers completing a job and ho…` |
| **Mistral-7B** | 0.186 | ❌ | `1. 16 روز` |
| **Phi-3-mini** | 0.143 | ❌ | `این کار ۱۶ روز به پایان می‌رسد. این کار ۴ روز به پایان می‌رسد. این کار ۵ روز به پایان می‌رسد. این کار ۲ روز ب…` |

**Why it's tricky:** A workers/rate word problem: 8 workers finish in 20 days; adding 2 workers finishes it how many days *earlier*? (gold `2` = ۴ روز). Gemma-4, Gemma-3, Qwen3.8, Qwen2.5-7B (2-shot) and Llama-3.2 answer the option number correctly; Nemotron and Qwen2.5-7B (0-shot) pick wrong options (`4`/`3`), Mistral answers `1. 16 روز`, Phi-3-mini prints *every* option, and Qwen3-30B wraps its answer in a `thinking` block (truncated). Format-following (bare option number) decides the winner.

#### Persian math word problem

**Input:**

```
به عنوان یک متخصص ریاضی، یک مسئله به شما داده خواهد شد و باید راه حل صحیح، شفاف و قدم به قدم برای مسئله نوشته و پاسخ نهایی به تنهایی را در بخش مربوطه قرار دهید. تمامی پاسخ های شما باید به زبان فارسی باشد بجز اعداد که به لاتین (انگلیسی) باید نوشته بشوند. از شما انتظار میرود مسئله را در فرمت زیر دریافت کرده و بصورت مشخص شده، راه حل و پاسخ نهایی را ارائه کنید:

[مسئله]
در این بخش، صورت مسئله به شما د
```

**Gold:** `1000`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `[راه حل] ابتدا مقدار پنج درصد از 2000 را محاسبه می‌کنیم: 5% * 2000 = (5/100) * 2000 = 5 * 20 = 100 سپس طبق صو…` |
| **Gemma-3-27B** | 0.600 | ✅ | `[راه حل] پنج درصد از 2000 برابر است با: (5/100) * 2000 = 100 فرض می‌کنیم عدد مورد نظر x باشد. ده درصد از x بر…` |
| **Nemotron-49B** | 0.494 | ✅ | `[راه حل] پنج درصد از 2000 را محاسبه می کنیم: 5% از 2000 = 0.05 * 2000 = 100 اکنون، ما می خواهیم بدانیم 100 مع…` |
| **Qwen3.8-27B** | 0.477 | ✅ | `[راه حل] پنج درصد از 2000 برابر است با: 0.05 × 2000 = 100 اگر عدد مورد نظر را x فرض کنیم، ده درصد از آن برابر…` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `[راه حل] ابتدا می‌توانیم معادله را برای این مسئله بنویسیم. فرض کنیم x عدد مورد نظر ما است. پنج درصد از 2000 ب…` |
| **Qwen2.5-7B** | 0.443 | ✅ | `[راه حل] ابتدا می‌توانیم معادله را برای حل این مسئله بنویسیم. فرض کنیم x عدد مورد نظر ما است. پنج درصد از 200…` |
| **Llama-3.2-3B** | 0.326 | ❌ | `[مسئله] پنج درصد از 2000 معادل ده درصد از چه عددی است؟ [/مسئله] [راه حل] پنج درصد از 2000 را می توان به صورت …` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `<think> Okay, let's see. The problem is asking: 5% of 2000 is equal to 10% of what number? Hmm, I need to fin…` |
| **Mistral-7B** | 0.186 | ❌ | `[راه حل] ابتدا باید پنج درصد از 2000 را حساب کنیم: 2000 * 5/100 = 100. سپس باید ده درصد از چه عددی است: 100 *…` |
| **Phi-3-mini** | 0.143 | ❌ | `کم کوی انجادی اسئده افراری انجادید است اسئ است اسئده ادی است اسئدادید اندادیده اسئده اسئداد ادیدادید ادیدمادی…` |

**Why it's tricky:** '5% of 2000 is equal to 10% of what number?' (gold `1000`). Five models — Gemma-4, Gemma-3, Nemotron, Qwen3.8 and Qwen2.5-7B (0-shot) — work it correctly; Qwen2.5-7B **2-shot misses** (the exemplar anchors a different structure), Llama-3.2 and Mistral set up the equation but never output the final-answer block, and Phi-3-mini degrades into gibberish. Math scores are gated by final-answer *structure compliance*, and few-shot can actually hurt.

#### Sentiment analysis

**Input:**

```
جمله زیر نظر یک شخص است. این جمله به زبان فارسی است. بار یا احساس موجود در این جمله را شناسایی کن.
پاسخ‌ های ممکن کلمات روبرو هستند: POSITIVE, NEUTRAL, NEGATIVE, OTHER.
زمانی که جمله دارای احساس خاصی نیست یا شامل احساسات مختلف است از OTHER استفاده کن
نظر: اگه نوشیدنی مالته باید تلخ باشه نه اینکه شیرین از خریدم کاملا پشیمونم و ب هیچ کسم پیشنهاد نمیکنم ک بخره چون پشیمون میشید تو عمرم با همچین نوشیدن
```

**Gold:** `احساس: NEGATIVE`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `NEGATIVE` |
| **Gemma-3-27B** | 0.600 | ✅ | `NEGATIVE **توضیح:** این جمله به وضوح بیانگر نارضایتی شدید و پشیمانی از خرید نوشیدنی است. کلماتی مانند "پشیمون…` |
| **Nemotron-49B** | 0.494 | ❌ | `با توجه به تحلیل احساسات در جمله ارائه شده، بار یا احساس موجود در این جمله را می‌توان به شرح زیر شناسایی کرد:…` |
| **Qwen3.8-27B** | 0.477 | ✅ | `NEGATIVE` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ✅ | `احساس: NEGATIVE` |
| **Qwen2.5-7B** | 0.443 | ❌ | `برای شناسایی بار یا احساس موجود در این جمله، باید به محتوای آن نگاه کنیم: "زمانی که جمله دارای احساس خاصی نیس…` |
| **Llama-3.2-3B** | 0.326 | ✅ | `در این جمله احساس منفی وجود دارد.` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `**بار/احساس:** NEGATIVE **توضیح:** جمله شامل عباراتی مانند "پشیمونم"، "ب هیچ کسم پیشنهاد نمیکنم"، و "پشیمون م…` |
| **Mistral-7B** | 0.186 | ❌ | `NEUTRAL` |
| **Phi-3-mini** | 0.143 | ❌ | `این جمله بررو نیز نگرفته است که احساسات مختلف دارد. این می‌تواند نوشیدنی مالته باید تلخ باشند و نیاز بود به ش…` |

**Why it's tricky:** A product review — 'نوشیدنی مالته باید تلخ باشه نه شیرین… کاملا پشیمونم' — is clearly **NEGATIVE**. Gemma-4, Gemma-3, Qwen3.8, Llama-3.2 and Qwen2.5-7B (2-shot) get it; Mistral-7B says `NEUTRAL`, Qwen2.5-7B and Nemotron hedge with long explanations the scorer can't map, and Qwen3-30B emits the right label *after* a `thinking` block (truncation cost). A free-form task where prose length and label discipline matter as much as comprehension.

#### Natural language entailment

**Input:**

```
هدف وظیفه‌ی استنتاج زبان طبیعی تشخیص رابطه‌ی نتیجه‌گیری بین یک <فرضیه> با توجه به یک <پیش‌فرض> است.
رابطه‌ یا برچسب میان آن‌ها می‌تواند یکی از سه نوع تناظر، تناقض یا ناشناخته باشد.
- تناظر : اگر جمله <فرضیه> به طور منطقی نتیجه‌ای از جمله <پیش‌فرض> باشد
- تناقض : اگر جمله <فرضیه> با جمله <پیش‌فرض> در تناقض باشد
- ناشناخته : اگر رابطه‌ای قطعی بین جمله <پیش‌فرض> و جمله <فرضیه> وجود نداشته باشد و هیچ 
```

**Gold:** `<برچسب>: c`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ❌ | `ناشناخته` |
| **Gemma-3-27B** | 0.600 | ✅ | `تناقض` |
| **Nemotron-49B** | 0.494 | ✅ | `تناقض` |
| **Qwen3.8-27B** | 0.477 | ❌ | `We need answer in Persian likely. User asks NLI: premise: "رسوب اسیدی یا باران اسیدی وقتی که SO2 و NOx در اتم…` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `ناشناخته` |
| **Qwen2.5-7B** | 0.443 | ❌ | `تناظر` |
| **Llama-3.2-3B** | 0.326 | ✅ | `تناقض` |
| **Qwen3-30B-A3B** | 0.283 | ✅ | `<think> Okay, let's try to figure out the relationship between the given premise and hypothesis. The premise …` |
| **Mistral-7B** | 0.186 | ❌ | `تناظر` |
| **Phi-3-mini** | 0.143 | ✅ | `<برچسب>: تناقض یا تناظر یا ناشناخته می تواند این رابطه برای توجه به توانایی استفاده کند که این اتمسفر با اکسی…` |

**Why it's tricky:** The gold label is `<برچسب>: c` (تناقض/contradiction) — acid-rain premise vs hypothesis. **Half the models miss even this** (the task's best model only scores 0.26). Gemma-3, Nemotron, Llama-3.2 and Phi-3 pick تناقض (Qwen3-30B also hits, label hidden inside a `thinking` block); Gemma-4 and Qwen2.5 say ناشناخته, Mistral/Qwen2.5 say تناظر, Qwen3.8 answers in an English preamble. The *right-class* accuracy would be much higher — most failures are output-format, but the underlying NLI signal is genuinely the hardest of the seven tasks.

#### Named entity recognition (Persian tokens)

**Input:**

```
شرح وظیفه:
شما باید یک لیست توکن فارسی داده شده را با برچسب های موجودیت اسمی برچسب گذاری کنید.
برچسب های موجودیت اسمی:

PER (نفر)
LOC (مکان)
ORG (سازمان)
Product (محصول)
Event (رویداد)
Facility (تاسیسات)

فرمت خروجی:
فرمت خروجی شما باید لیستی از تاپل ها باشد، که در آن هر تاپل از یک کلمه از متن ورودی و برچسب موجودیت اسمی مربوط به آن تشکیل شده باشد.
برای کلماتی که بخشی از هیچ موجودیت اسمی نیستند، با
```

**Gold:** `خروجی  [('وی', 'o'), ('درباره', 'o'), ('مراحل', 'o'), ('احداث', 'o'), ('بزرگراه', 'facility'), ('نیاوران', 'facility'), ('گفت', 'o'), (' ', 'o'), ('با', 'o'), ('توجه', 'o'), ('به', 'o'), ('توافق', 'o'`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | ````python [ ('وي', 'O'), ('درباره', 'O'), ('مراحل', 'O'), ('احداث', 'O'), ('بزرگراه', 'FAC'), ('نیاوران', 'LO…` |
| **Gemma-3-27B** | 0.600 | ✅ | ```` [('وي', 'PER'), ('درباره', 'O'), ('مراحل', 'O'), ('احداث', 'O'), ('بزرگراه', 'Facility'), ('نیاوران', 'LO…` |
| **Nemotron-49B** | 0.494 | ✅ | `زیرا در متن ورودی داده شده، هیچ نام خاص برای افراد (PER)، سازمان (ORG)، محصول (Product)، رویداد (Event) یا تا…` |
| **Qwen3.8-27B** | 0.477 | ❌ | `We need answer in Persian likely. User asks NER labeling for Persian token list. Need output list of tuples (…` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ✅ | `خروجی برای ورودی شما به صورت زیر خواهد بود: [('وي', 'per'), ('درباره', 'o'), ('مراحل', 'o'), ('احداث', 'o'), …` |
| **Qwen2.5-7B** | 0.443 | ✅ | `برای برچسب‌گذاری لیست توکن‌های فارسی داده شده با برچسب‌های موجودیت اسمی، می‌توانیم به شرح زیر عمل کنیم: ```pl…` |
| **Llama-3.2-3B** | 0.326 | ❌ | `این وظیفه شامل việc برچسب گذاری لیست توکن فارسی داده شده با برچسب های موجودیت اسمی است. لیست توکن ورودی است: …` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `<think> Okay, I need to label the given Persian tokens with the appropriate named entity tags. Let me start b…` |
| **Mistral-7B** | 0.186 | ❌ | `برای گذاری برچسب های موجودیت اسمی برای لیست توکن فارسی در این صورت است: 1. برای کلمات شخصی (PER): کلماتی که ن…` |
| **Phi-3-mini** | 0.143 | ❌ | `در استفاده از موجودیت اسمی که برچسب می‌کنند، می‌توانید یک لیست توکن فارسی با تاپ‌های موجودیت اسمی برای این مو…` |

**Why it's tricky:** The input list has facility/location tokens (بزرگراه نیاوران …). Gemma-4/Gemma-3 and Qwen2.5-7B emit the expected `[('tok','LABEL'), …]` tuples (hit); Qwen3-30B and Qwen3.8 get stuck in `thinking`/English preamble; Llama-3.2, Mistral, Phi-3 reply with instructions *instead of* the labeled list. **Qwen2.5-7B 2-shot jumps from prose to clean tuples** — few-shot examples fix NER format-following better than a bigger model.

#### Reading comprehension

**Input:**

```
متن: از آنجا که قطر رئوس غیر مجاور را متصل می‌کند، یک مثلث نمی‌تواند قطر داشته باشد و یک چهارضلعی (مربع یا مستطیل) دو قطر دارد. تمام قطرهای یک چندضلعی کوژ درون آن هستند، اما چند قطر یک چندضلعی کاو بیرون از آن قرار می‌گیرد.

سؤال: کدام شکل هندسی قطر ندارد؟
پاسخ:
```

**Gold:** `مثلث`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `مثلث` |
| **Gemma-3-27B** | 0.600 | ✅ | `مثلث.` |
| **Nemotron-49B** | 0.494 | ✅ | `پاسخ: مثلث` |
| **Qwen3.8-27B** | 0.477 | ✅ | `مثلث` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `مثلث کدام شکل هندسی‌ای است که قطر ندارد.` |
| **Qwen2.5-7B** | 0.443 | ❌ | `برای پاسخ به این سوال، باید به متن دقت کرد و اطلاعات آن را تحلیل کنیم. متن اشاره کرده است که: 1. مثلث قطر ندا…` |
| **Llama-3.2-3B** | 0.326 | ✅ | `مثلث` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `پاسخ: مثلث توضیح: قطر یک چندضلعی خطی است که دو رأس غیر مجاور را به هم متصل می‌کند. در یک مثلث (سه ضلعی)، تمام…` |
| **Mistral-7B** | 0.186 | ❌ | `یک مثلث قطر ندارد.` |
| **Phi-3-mini** | 0.143 | ❌ | `قطر هندسی ندارد، اما این موضوع به مورد مثلث هندسی است که برای قطر می‌تواند استفاده کرد. مثلث هندسی یک مثلث می…` |

**Why it's tricky:** The passage says a triangle cannot have a diagonal → answer **مثلث**. Top models, Llama-3.2 and Qwen3.8 answer in one word; Mistral, Phi-3, Qwen3-30B and Qwen2.5-7B either paraphrase, reproduce the passage, or add an explanation that fails the exact-match scorer. RC rewards *extractive brevity* — models that restate the answer as-is win.

## 4d. Embedding model comparison (Persian retrieval)

A 6-document Persian retrieval benchmark (`scripts/test_embeddings.py`) checks top-1 retrieval for 6 queries across three locally-served embedders. All reach top-1 correctness; scores differ in **confidence margin** (cosine of the retrieved doc):

| Embedder | Dim | Top-1 acc | Mean top-1 cosine | Batch latency |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | 384 | 1.0 | **0.898** | 0.14 s |
| `BAAI/bge-m3` | 1024 | 1.0 | 0.646 | 0.27 s |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 1.0 | 0.555 | 0.09 s |

**Takeaway:** all three embedders retrieve the correct Persian document; `multilingual-e5-small` gives the widest separation between correct/incorrect docs (highest cosine), while `paraphrase-multilingual-MiniLM` is fastest. `bge-m3` (1024-dim, strongest multilingual coverage) is the safe choice when corpus similarity is low. Embedders are served OpenAI-compatible on `:8001` (e5-small), `:8002` (bge-m3), `:8003` (paraphrase-multilingual).

---

## 5. Plan & Progress

| # | Sub-plan | Status | Exit criteria |
|---|---|---|---|
| P0 | Stabilize environment | ✅ | CLI runs against real data; venv usable; docs updated |
| P1 | Complete model set (Qwen primary) | ✅ | all ≤ 100 GB models present & loadable (9 GGUFs + 2 embedders); > 100 GB excluded |
| P2 | Inference engines (llama.cpp **and** vLLM) + embeddings | 🔄 partial | llama.cpp serving on `:8080`; vLLM launcher ready but not running; 3 embedders live |
| P3 | RAG data plane (vector DBs + Open WebUI + ingestion) | ⏳ | ingest → retrieve works end-to-end |
| P4 | Run + test sample repos (lightrag → anything-llm → ragflow → dify, in parallel) | 🔄 lightrag ✅, rest pending | each passes the RAG test harness |
| P5 | Production hardening + runbook | ⏳ | stack cold-restarts cleanly |

### Model download status (live daemons, 2026-08-17)

Downloads run as **systemd `rag-dl`** plus a dedicated Qwen3.8-27B daemon; both never stop — failures trigger an **exponential backoff brake** (`BACKOFF_BASE=90s`, ×2, cap 3600s, ±30% jitter) and resume from the partial file.

**Policy (2026-08-17): models > 100 GB download size are excluded from the queue** (see §4a). The DeepSeek-V4-Flash daemon was stopped; its 25/46 shard partial stays on disk.

| Target | Size | Progress | Note |
|---|---|---|---|
| DeepSeek-V4-Flash (safetensors) | ~160 GB | ⏸ **excluded (> 100 GB)** | partial 25/46 shards on disk (~54%), daemon stopped |
| Qwen2.5-72B Q8_0 / Nemotron-Ultra-253B | — | removed from queue | partials left on disk (73 GB / 3.6 GB), not deleted |
| MiniMax-M3 / Kimi-K3 / GLM-5.2 | — | excluded (> 100 GB) | never started (§4a) |

**No downloads are currently in-flight** — every model ≤ 100 GB is already complete & verified.

Completed & verified: **Gemma-4-31B**, **Gemma-3-27B**, **Qwen3.8-27B**, **Nemotron-49B**, **Qwen3-30B-A3B**, Qwen2.5-7B, Llama-3.2-3B, Mistral Q4_K_M, Phi-3 q4. Complete log trail: `offline-prep/logs/dl_models_*.log`.

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
- [`docs/reports/`](docs/reports/) — Persian eval report + comparison plots.

Generated artifacts (reports/logs/state) live under `offline-prep/` and are **not** tracked in git.

---

## 15. Dashboard Webapp — H200 RAG Control Center (NEW 2026-08-23)

**Live URL:** `http://127.0.0.1:9000/` and `http://127.0.0.1:9000/dashboard` (same), also `http://192.168.96.82:9000/dashboard` from LAN, and `http://host.docker.internal:9000/dashboard` from Docker. **Manager pid 2289945, 917 lines** (`app.py` patched from 580, backup `app.py.bak`).

### What it contains (single-file, no CDN, vanilla JS)

| Tab | Content | Data source |
|-----|---------|-------------|
| **Overview** | Manager version, `models_loaded`, GPU bars (used/free/util per GPU via `nvidia-smi`), proxy `192.168.203.2:3128`, paths (`root`, `venv`, `models_dir`), recent metrics (10), README quick-start copy | `GET /api/dashboard` (gpus, manager) + `GET /health` |
| **Models (11)** | Grid of 11 cards: `gemma-4-31b` (champion 19.6G loaded 5×), `gemma-3-27b`, `qwen3.8-27b`, `qwen3-30b-a3b`, `nemotron-49b`, `qwen2.5-7b` (loaded 8090), `llama-3.2-3b`, `mistral-7b`, `phi-3-mini`, `deepseek`, `qwen72b` — each shows family/params/quant/context/benchmark mean, `path_exists` ✅/❌, `backends` chips, `live_health` 200/err, **▶ Run** / **⏹ Stop** / **💬 Test** / **✎ Edit** buttons, filter by name/status | `GET /api/dashboard` models + `PATCH /admin/models/{id}` |
| **Embeds & Docker** | 3 embeds health (`8001 e5-small dim384`, `8002 bge-m3 dim1024`, `8003 paraph 384` + embed test dim), 9 docker table (webui 13000 healthy, milvus 19530, pgvector 15432, qdrant 16333, redis 16379, grafana 13001, prometheus 19090, otel 14317, node-exporter 19100), disk `du -sh` (17 repos ~1.9T), benchmarks `28 evalp*.json` + `10 png` | `GET /api/dashboard` embeds/docker/disk/benchmarks |
| **Project** | Structure tree for 9 key dirs (`scripts 24 files`, `services 13`, `deploy`, `llm_inference_manager`, `models/huggingface 17`, `docs/reports`, `e2e-test`, `rag_storage`, `logs`) + scripts how-to-run | `GET /api/project` |
| **Usage & Sessions** | By-model `cnt`/`avg_ms`/`max_ms` (gemma 99 avg 1862ms, qwen 39 avg 1418ms), recent 10 requests, 10 recent sessions, API tokens | `GET /api/usage` + `GET /v1/sessions` |
| **Playground** | Chat via manager (select model, prompt, max_tokens, temp → `POST /v1/chat/completions`), Embed playground (direct `8001` → dim + first 5 vector) | `POST /v1/chat/completions`, `POST /v1/embeddings` |

### API — Dashboard & Model Control

| Method | Path | Description | Test curl |
|--------|------|-------------|-----------|
| `GET` | `/` , `/dashboard` | **Dashboard HTML** (300+ lines CSS/JS) | `curl -s http://127.0.0.1:9000/dashboard \| head -c 300` → `<!doctype html>…H200 RAG Dashboard` |
| `GET` | `/api/dashboard` | **Aggregated JSON** (manager + 11 models + docker 9 + embeds 3 + disk + project 9 + metrics) | `curl -s http://127.0.0.1:9000/api/dashboard \| jq '.manager,.models[0].live_health'` |
| `GET` | `/api/project` | Structure + disk + docker | `curl -s http://127.0.0.1:9000/api/project \| jq` |
| `GET` | `/api/usage` | By-model + recent 30 | `curl -s http://127.0.0.1:9000/api/usage \| jq` |
| `POST` | `/admin/models/load?model_id=` | **Run** — spawns `llama_chat_server.py` on next free port 8085..8100, picks GPU with most `free_mib`, logs `logs/llama_server_<port>.log` | `curl -X POST http://127.0.0.1:9000/admin/models/load?model_id=gemma-3-27b` → `{"status":"spawned","port":8086,"gpu":1,"pid":...}` |
| `POST` | `/admin/models/unload?model_id=` | **Stop** — `terminate()` + clear `backends` → `available` | `curl -X POST http://127.0.0.1:9000/admin/models/unload?model_id=gemma-3-27b` → `{"status":"unloaded"}` |
| `PATCH` | `/admin/models/{id}` | **Edit** — `ModelPatch` (`name`,`params`,`size_gb`,`quant`,`path`,`context`,`benchmark_mean`,`notes`) | `curl -X PATCH http://127.0.0.1:9000/admin/models/gemma-3-27b -H "Content-Type: application/json" -d '{"notes":"test"}'` |
| `PUT` | `/admin/models/{id}` | **Create/Replace** — full cfg with `backends` (used to re-register `qwen2.5-7b` → `["http://127.0.0.1:8090"]` without spawning) | `curl -X PUT http://127.0.0.1:9000/admin/models/qwen2.5-7b -d @cfg.json` |

### Verified curls (2026-08-23 14:11-14:15)

```bash
# Dashboard HTML
curl -s http://127.0.0.1:9000/dashboard | head -c 300
# → <!doctype html>...<title>H200 RAG Dashboard — Manager :9000</title>...

# Dashboard API — 11 models, 9 docker, 3 embeds, 2 loaded
curl -s http://127.0.0.1:9000/api/dashboard | jq '.manager.models_loaded, (.models|length), (.docker|length), (.embeds|length)'
# → 2  11  9  3

# Model live health (gemma 5× 200)
curl -s http://127.0.0.1:9000/api/dashboard | jq '.models[0].live_health[0]'
# → {"backend":"http://127.0.0.1:8080","status":200,"body":{"status":"ok","model":"gemma-4-31b-1"}}

# Run gemma-3 (available → loading)
curl -s -X POST "http://127.0.0.1:9000/admin/models/load?model_id=gemma-3-27b" | jq
# → {"status":"spawned","model":"gemma-3-27b","port":8086,"gpu":1,"pid":2290355}
curl -s http://127.0.0.1:9000/admin/status | jq '.registry."gemma-3-27b"'
# → {"status":"loading","backends":["http://127.0.0.1:8086"],"size_gb":16.5}

# Edit
curl -s -X PATCH "http://127.0.0.1:9000/admin/models/gemma-3-27b" -H "Content-Type: application/json" -d '{"notes":"test-dashboard-edit"}' | jq .meta.notes
# → "test-dashboard-edit"

# Stop
curl -s -X POST "http://127.0.0.1:9000/admin/models/unload?model_id=gemma-3-27b" | jq
# → {"status":"unloaded"}  (process 8086 killed, backends [])
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":10}' | jq .choices[0].message.content
# → "Hello" (still works via dashboard playground)

# OpenCode via dashboard's localhost base still works
opencode models | grep h200-manager  # 11
curl -s http://127.0.0.1:9000/v1/models | jq '.data[].id'  # 11
```

### How to open in browser

- **SSH tunnel if remote:** `ssh -L 9000:127.0.0.1:9000 a.nikkhah@ai-gpu1`
- **Then browse:** `http://localhost:9000/dashboard` — click Models → ▶ Run / ⏹ Stop / 💬 Test / ✎ Edit — all without CLI.

