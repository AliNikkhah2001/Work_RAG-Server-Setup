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
| `deepseek-ai/DeepSeek-V4-Flash` (safetensors) | ~88 GB | ⏳ 25/46 shards (~54%), proxy-limited |
| `BAAI/bge-small-en-v1.5` | 383 MB | ✅ embeddings (dim 384) |
| `sentence-transformers/all-MiniLM-L6-v2` | 932 MB | ✅ embeddings |
| `intfloat/multilingual-e5-small` | 1.2 GB | ✅ Persian-capable embeddings (dim 384) |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 912 MB | ✅ Persian-capable embeddings (dim 384) |
| `BAAI/bge-m3` | 2.2 GB | ✅ multilingual embeddings (dim 1024) |

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

- [`docs/reports/persian_mean.png`](docs/reports/persian_mean.png) — ranked mean accuracy
- [`docs/reports/persian_by_task.png`](docs/reports/persian_by_task.png) — per-task accuracy by model
- [`docs/reports/persian_scatter.png`](docs/reports/persian_scatter.png) — **model size (disk GB) vs mean accuracy**, bubble area = parameter count
- [`docs/reports/persian_radar.png`](docs/reports/persian_radar.png) — **ability-group radar profile** for all models
- [`docs/reports/persian_radar_family.png`](docs/reports/persian_radar_family.png) — **per-family radar profiles** (Gemma / Qwen / Nemotron / Llama / Mistral / Phi)
- [`docs/reports/persian_speed.png`](docs/reports/persian_speed.png) — **tokens/sec + latency per task** per model
- [`docs/reports/persian_spider.png`](docs/reports/persian_spider.png) — **per-task 7-axis spider** per model
- [`docs/reports/persian_eval_report.md`](docs/reports/persian_eval_report.md) — full report with per-example input/output samples + **same-question cross-model comparison**

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

## 4c. Embedding model comparison (Persian retrieval)

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
| P1 | Complete model set (Qwen primary) | 🔄 in progress | Qwen/Llama/Mistral GGUF present & loadable |
| P2 | Inference engines (llama.cpp **and** vLLM) + embeddings | 🔄 partial | both engines answer a prompt; numbers logged |
| P3 | RAG data plane (vector DBs + Open WebUI + ingestion) | ⏳ | ingest → retrieve works end-to-end |
| P4 | Run + test sample repos (lightrag → anything-llm → ragflow → dify, in parallel) | ⏳ | each passes the RAG test harness |
| P5 | Production hardening + runbook | ⏳ | stack cold-restarts cleanly |

### Model download status (live daemons, 2026-08-17)

Downloads run as **systemd `rag-dl`** plus a dedicated Qwen3.8-27B daemon; both never stop — failures trigger an **exponential backoff brake** (`BACKOFF_BASE=90s`, ×2, cap 3600s, ±30% jitter) and resume from the partial file.

| Target | Size | Progress | Note |
|---|---|---|---|
| **DeepSeek-V4-Flash** (safetensors) | ~88 GB | **25/46 shards (~54%)** | main daemon currently retrying; proxy resets >1 GB transfers |
| Qwen2.5-72B Q8_0 / Nemotron-Ultra-253B | — | removed from queue | partials left on disk (73 GB / 3.6 GB), not deleted |
| MiniMax-M3 / Kimi-K3 / GLM-5.2 | — | queued | not started |

Completed & verified this round: **Gemma-4-31B**, **Gemma-3-27B**, **Qwen3.8-27B**, **Nemotron-49B**, **Qwen3-30B-A3B**, Qwen2.5-7B, Llama-3.2-3B, Mistral Q4_K_M, Phi-3 q4. Complete log trail: `offline-prep/logs/dl_models_*.log`.

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
