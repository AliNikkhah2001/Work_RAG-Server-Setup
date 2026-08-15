# RAG Server — System Report & Runbook

> **Date:** 2026-08-15. Machine: `ai-gpu1`. Working dir: `/splunk-data/v1/Work_RAG-Server-Setup`
>
> **Multi-page guide:** see [`docs/README.md`](README.md) (index) and [`docs/guides/`](guides/)
> for deep-dives on hardware, engines, models, the download daemon, sample projects and the
> reboot runbook.

## 1. Environment

- Hostname `ai-gpu1`; OS Ubuntu 24.04; Google-host 2x **NVIDIA H200 NVL** (143 GiB each), driver **580.173.02**.
- `nvcc` (host): CUDA 12.0. PyTorch wheels are **cu124**. Runtime/driver reports CUDA 13.0.
- Network interfaces: `192.168.96.82` and `192.168.177.10` (docker bridges `172.17.0.1`, `172.18.0.1`).
- Squid proxy (outbound): `http://192.168.203.2:3128` (configured for shell/apt/git/docker/pip/HF via `proxy_setup.sh`).
- Firewall: ufw/iptables **inactive** (all ports open). Services bind `0.0.0.0` → reachable externally on both interface IPs.
- ✅ **Root disk `/` freed — now 22G/48G used (49%, 24G free)** (was 100%, ~90M free). Docker data-root relocated off root onto `/splunk-data/v1/docker-data`; containerd data-root moved to `/splunk-data/v1/containerd-data` (was the 13G symlink target `/ai-gpu1/v1/containerd-data` on root; stale dirs deleted). `/var/lib/containerd` is a symlink → `/splunk-data/v1/containerd-data`. All 9 containers now have `restart=unless-stopped`.

## 2. Every service & endpoint

`GATEWAY = http://192.168.96.82:8088` (nginx, also on 192.168.177.10:8088). Firewall open, but run `curl --noproxy '*'` when testing locally (the shell's `http_proxy` env would route through squid).

| Service | Direct & Gateway path | Notes |
|---|---|---|
| nginx gateway | `:8088` ; `/` = index page | `/etc/nginx/sites-available/rag-gateway`, index at `deploy/gateway/index.html` |
| vLLM OpenAI API | `:8000` ; `/vllm/` | model `qwen2.5:7b-vllm` (Qwen2.5-7B Q4_K_M, 53.6 tok/s), `--enforce-eager` |
| llama.cpp OpenAI API | `:8080` ; `/llama/` | model `qwen2.5:7b` (Qwen2.5-7B Q4_K_M), chat+stream+`/v1/models` |
| Embeddings API | `:8001` ; `/embeddings/` | `local-embed`, bge-small, dim 384 |
| Open WebUI (chatbot UI) | `:13000` ; `/webui/` | wired to llama.cpp `:8080`, `WEBUI_AUTH=false` |
| Grafana | `:13001` ; `/grafana/` | admin/admin (anon view on), datasource `Prometheus` provisioned |
| Prometheus | `:19090` ; `/prometheus/` | scrapes vllm `:8000/metrics`, gpu `:9101`, node `:19100` |
| otel-collector | `:14317` gRPC / `:14318` HTTP / `:19092` prom-exporter | OTLP intake, batch → debug+prometheus |
| GPU metrics exporter | `:9101/metrics` | host-side `nvidia-smi` → prometheus format (`gpu_utilization_percent` etc.) |
| Milvus | `:19530` gRPC / `:19091` metrics ; `/milvus/` (grpc_pass) | collection `rag_docs` (dim 384, IVF_FLAT/COSINE) |
| Qdrant | `:16333` ; `/qdrant/` | collection `rag_docs` (dim 384, cosine) |
| pgvector | `:15432` | ext `vector 0.8.6`, table `rag_docs` (embedding vector(384)) |
| Redis | `:16379` | key/value cache (interconnect test passed) |

## 3. Docker images & containers

Present images: `ghcr.io/open-webui/open-webui:main`, `milvusdb/milvus:latest`, `pgvector/pgvector:pg16`, `qdrant/qdrant:latest`, `redis:7-alpine`, `prom/prometheus:v2.52.0`, `grafana/grafana:11.2.0`, `prom/node-exporter:v1.8.1`, `otel/opentelemetry-collector-contrib:0.105.0`. Saved tars of the 5 core images in `offline-prep/docker-images/`.

Running containers: `webui-test`, `milvus-test`, `pgvector-test`, `qdrant-test`, `redis-test`, `prometheus-test`, `grafana-test`, `node-exporter-test`, `otel-test`.

**Not present (documented gaps):** `vllm/vllm-openai:latest`, `nvidia/cuda:12.8.0-runtime-ubuntu22.04` (both listed in the install script; pulls never succeeded through the proxy, and can't fit on the full root disk — vLLM runs natively so the image is optional). `pghistory` postgres extension not installed.

## 4. Environments (venvs) & library status

- Master venv: `offline-prep/venv` (Python 3.12.3). **All 35 CUDA/std packages from `offline_prepare_cli.py` import OK** → torch 2.4.0+cu124, torchvision/audio, xformers, flash-attn 2.6.3, vllm 0.6.1.post1, triton, faiss, bitsandbytes, transformers, accelerate, sentence-transformers, langchain, llama-index, pymilvus, qdrant-client, redis, chromadb, docling, ragas, deepeval, litellm, openai, etc. Use `offline-prep/venv/bin/python3.12 -m pip` (bare `pip` shebang fixed but use python -m to be safe).
- LightRAG venv: `offline-prep/sample-projects/lightrag/venv` — **empty** (deps pending until big downloads finish; bandwidth).
- Known pin: numpy 1.26.4 (vLLM), scipy 1.13.1 (do not upgrade either).
- vLLM venv patches (survive until vLLM upgrade, see `docs/findings.md`): relaxed vocab assert in `vocab_parallel_embedding.py:381`; pyairports stub; GGUF wrapper dir `offline-prep/models/gguf-wrappers/qwen2.5-7b-q4km/`.

## 5. Models (files)

Directory: `offline-prep/models/huggingface/<repo with / → _>/` and `.cache/huggingface/download/*.incomplete` for partials.

- Done: Qwen2.5-7B Q4_K_M (4.68 GB), Llama-3.2-3B Q4_K_M (2.02 GB). Embeddings: bge-small, MiniLM. Phi-3 GGUFs present.
- Downloading: Mistral-7B v0.3 Q4_K_M (~78%, resuming Aug-10 partial).
- New big (background, tmux `dl_big`): **Qwen2.5-72B-Instruct Q4_K_M (~49 GB single-file, both engines)** + Q8_0 (~93 GB, 2-part, llama.cpp) — strong Persian/multilingual. Target ≈ 142 GB total.

## 6. Monitoring stack

`deploy/monitoring/docker-compose.yml` (prometheus 2.52.0 — **2.53.0 SIGBUS-crashes in docker**, do not upgrade to 2.53.x; grafana 11.2.0 provisioned via `deploy/monitoring/grafana/provisioning/`; data bind-mounted to `deploy/monitoring/{prometheus,grafana}-data` on `/splunk-data` chmod 777). TLS-follow-up: grafana root_url `http://192.168.96.82:8088/grafana`, prometheus `--web.external-url=/prometheus`.

## 7. Key file locations

- Scripts: `scripts/` (download_models.py, progress_report.py, rag_test_harness.py), `scripts/services/` (llama_chat_server.py, embed_server.py, vllm_server.sh, gpu_metrics_exporter.py, lightrag_run.sh)
- Deploy: `deploy/` (setup_data_plane.py, recreate_webui.sh, monitoring/, gateway/)
- Models: `offline-prep/models/`, wheels: `offline-prep/python-packages[-cu124]/`, images: `offline-prep/docker-images/`
- Logs: `offline-prep/logs/` (dl_*, install_*, llama_qwen.log, vllm_qwen.log)
- Docs: `docs/` (findings.md, plan.md, history/001-004, this report)
- nginx config: `/etc/nginx/sites-available/rag-gateway`; gateway logs `deploy/gateway/logs/` (moved off root disk)

## 8. Management commands

- Dashboard: `offline-prep/venv/bin/python3.12 scripts/progress_report.py --watch` (or `--once`)
- tmux sessions: `work` (models dl), `dl_big` (72B dl), `llama`, `vllm`, `gpuexp`, `opencode`. Attach: `tmux attach -t <name>`.
- Restart monitoring: `docker compose -f deploy/monitoring/docker-compose.yml up -d`
- Expose gateway: `nginx -s reload` (config in `/etc/nginx/sites-available/rag-gateway`)

## 9. Known issues

1. ~~Root disk 100%~~ **DONE**: docker+containerd data-root relocated to `/splunk-data/v1`, root freed to 49% (~24G free).
2. vLLM `pghistory`, `vllm/vllm-openai` & `nvidia/cuda` images, otel-collector OTLP instrumented apps: not present/needed yet.
3. Shell `http_proxy` env makes local curl to host IP return squid 503 (use `--noproxy '*'`).