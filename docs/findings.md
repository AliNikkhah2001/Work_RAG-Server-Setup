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

## CRITICAL: root filesystem is 100% full + docker data-root on stale path (2026-08-15)

- `/` (48G, `ubuntu--vg`) is **100% full**: 14G `docker data-root`, 12G `/var`, 12G `/usr`, 8.1G `/swap.img`.
- **Docker data-root is `/ai-gpu1/v1/docker-data`** (`docker info` `DockerRootDir`) — the stale path from AGENTS.md, now a plain directory on the root partition. Docker named volumes (e.g. the original `grafana-data`) live there and hit `database or disk is full` (grafana sqlite). Mitigation used: **bind-mount all persistent monitoring data onto `/splunk-data`** (`deploy/monitoring/{prometheus,grafana}-data`, chmod 777 since prometheus/grafana run as non-root). Long-term: relocate docker data-root to `/splunk-data` (`dockerd --data-root` / daemon.json) or free space on `/`.

## Monitoring stack (brought up 2026-08-15)

- Images pulled through proxy (flaky, retry needed): `prom/prometheus:v2.52.0`, `grafana/grafana:11.2.0`, `prom/node-exporter:v1.8.1`, `otel/opentelemetry-collector-contrib:0.105.0`.
- **prometheus 2.53.0 SIGBUS-crashes in docker** (`promql.NewActiveQueryTracker`, O_TMPFILE mmap → `fatal error: fault`). Pin **2.52.0**.
- Running (`deploy/monitoring/docker-compose.yml`): prometheus :19090 (scrapes vllm :8000/metrics, gpu :9101, node-exporter :19100), grafana :13001 (provisioned Prometheus datasource via `grafana/provisioning/`), node-exporter :19100, otel-collector :14317/:14318 (OTLP gRPC/HTTP) + prometheus exporter :19092.
- GPU metrics come from a host-side exporter `scripts/services/gpu_metrics_exporter.py` (:9101, reads `nvidia-smi`, no container/DCGM needed).

## External exposure (2026-08-15)

- Host services bind `0.0.0.0`; ufw/iptables inactive. nginx gateway on **:8088** consolidates everything: `/vllm/`, `/llama/`, `/embeddings/`, `/webui/` (ws), `/grafana/`, `/prometheus/`, `/qdrant/`, `/milvus/` (grpc_pass), `/` index. Config `/etc/nginx/sites-available/rag-gateway`; logs moved to `deploy/gateway/logs/` (root disk).
- **Gotcha**: the shell exports `http_proxy` → `curl http://<host-ip>:8088/...` locally goes through squid and returns `503 (Server: squid/6.6)`. Use `curl --noproxy '*'` for local tests.
- Grafana sub-path via `GF_SERVER_ROOT_URL=http://192.168.96.82:8088/grafana` + `GF_SERVER_SERVE_FROM_SUB_PATH=true`; prometheus via `--web.external-url=/prometheus --web.route-prefix=/prometheus` (health now at `/prometheus/-/healthy`).
- Models: `bartowski/Qwen2.5-72B-Instruct-GGUF` huge quants are **multi-part** (subfolder + `-00001-00002`): llama.cpp handles splits; vLLM 0.6.1 does **not**. Q4_K_M (~49 GB) is single-file → use it for vLLM.

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

## vLLM + GGUF quirks (2026-08-15)

- **Vocab-size assert in GGUF load (`vocab_parallel_embedding` AssertionError)**: bartowski Qwen2.5 GGUF files embed a **padded vocab** (`token_embd.weight` rows = 152064) while the config that vLLM derives (from GGUF metadata via transformers' `gguf_file` kwarg — a local `config.json` next to the GGUF is *ignored*) says `vocab_size = 151936`. Fix applied: relaxed the assert to `>=` in the venv at `vllm/model_executor/layers/vocab_parallel_embedding.py:381`; the existing `narrow()` truncates the trailing pad rows. Verify if vLLM is upgraded.
- **GGUF model path must be a file, and its parent dir is searched for `config.json`** — but that config is only a fallback; transformers reads the config *from the GGUF* when `gguf_file` is passed. Working wrapper pattern: a dir containing `config.json` (Qwen2.5-7B arch, `vocab_size: 152064`) + a symlink `model.gguf` → the real file (`offline-prep/models/gguf-wrappers/qwen2.5-7b-q4km/`). Symlink must resolve correctly or `check_gguf_file` returns False → "Repo id must be in the form..." error.
- **Guided-decoding backend (`outlines`) breaks on requests** unless a working `pyairports` is importable. The mirror only offers the empty stub `pyairports==0.0.1` (no `airports.py`), so it was replaced by a manual stub `site-packages/pyairports/airports.py` with `AIRPORT_LIST = []`. Symptoms: HTTP 500 `ModuleNotFoundError: No module named 'pyairports'`.
- vLLM GGUF Q4_K_M 7B throughput on H200: **~54 tok/s** (`--enforce-eager`, `--gpu-memory-utilization 0.5`). GGUF path is not fully optimized in 0.6.1 (slower than fp16); CUDA graphs are disabled by `--enforce-eager`.
- **Docker/containerd live under a separate containerd socket; data-root lives in TWO places**: `/var/lib/docker` (image/container metadata) AND `/var/lib/containerd` (bulk `overlayfs` snapshots + `content` store). On this host containerd was the heavy one (~13G vs 60M docker). Backing both up requires moving containerd FIRST (its symlink target), then docker's data-root.
- **`rsync -aH` on containerd overlay-disks trees hangs** in the hardlink-fixup phase (`O_TMPFILE`/hardlink trees) and effectively never finishes → restarts with incomplete images (`milvus` exit 127 missing `libmilvus-storage.so`, pgvector/redis exit 1 `find: invalid user`). Use plain `rsync -a` (no `-H`): containerd/image layers work fine as unlinked copies on a big disk; source file count 109044 matched exactly.
- **Gotcha: `pkill -f "rsync -aH /src"` matches the running shell too** when the shell's own command line contains that substring → it kills its own terminal. Match on an unambiguous pattern (e.g. `pgrep -x rsync`) or exclude self.
- **Rerun of a full `rsync` after `rm -rf` of an aborted destination inflated the on-disk copy to 23G** (abort artifact). Dest size for plain `rsync -a` of the overlay tree ≈ 14G for 13G source — expected (hardlinks flattened).
- Completed relocation: `/etc/docker/daemon.json` `data-root=/splunk-data/v1/docker-data`; `/var/lib/containerd` symlink → `/splunk-data/v1/containerd-data`. Root freed 45G→22G (49%). Re-verify a clean-ish reboot if it ever powers off (`systemctl start containerd` before `docker`).
- **Frontier-MoE runnability gate is ENGINE not memory**: 2xH200 (281GB) + 1TB RAM fits EVERYTHING we download; the constraint is arch support in vllm 0.6.1 / llama-cpp-python 0.3.34. MiniMax-M3 → llama.cpp PR #24523; Kimi K3 → unsloth llama.cpp fork (kimi-k3); GLM-5.2 → vllm>=0.23 or SGLang>=0.5.13; DeepSeek-V4-Flash → new vllm + deep_gemm FP4 kernels. dl the weights now, build engines in parallel.
- **Go-to download supervisor**: `systemctl status rag-dl` (systemd, Restart=always) replacing tmux loops; add repos via TARGETS in `scripts/download_models.py`; gated repos (gemma-3-27b) need `HF_TOKEN` → logged as AUTH-BLOCKED and skipped, never daemon-infinite-loop.
- **HF_TOKEN is now configured** (2026-08-15): read from `offline-prep/.hf_token` via systemd drop-in `/etc/systemd/system/rag-dl.service.d/override.conf` (`EnvironmentFile=`). Gated gems (Gemma-3-27B, Gemma-4-31B) download normally; no more AUTH-BLOCKED.
- **Egress is allowlisted, not open**: most outbound = `Network unreachable`/`ENETUNREACH` (pinggy, localhost.run, localtunnel edge `193.34.76.44:12091`, random hosts). Reachable directly: HuggingFace, Cloudflare edge/anycast, github, google, pypi, npm.
- **Internet proxy = Squid `192.168.203.2:3128` with upstream Kerio Control** MITM. Kerio 400s absolute-form `GET https://…` — HTTPS-only HTTP clients MUST use CONNECT+TLS (node/axios via `https-proxy-agent` @7; `global-agent` bootstrap does NOT reliably force CONNECT). Relay *back* to this box's IPs is ACL-blocked (`503/502`).
- **Public tunnels so far impossible** from this box: cloudflared quick-tunnel registry POST stalls (ignores env proxy; direct unroutable); localtunnel registers fine (control HTTPS) but its **raw-TCP data plane** is `ENETUNREACH`. Staged fallback gateways (auth'd `127.0.0.1:8089`, `/samples/` `/docs/` on 8088) wait on a working relay.vormer
- **Disk note**: Mistral repo dir is 34G (multi-quant downloads Q3/Q4/Q5 from an earlier job); stale `*.incomplete` chunks accumulate across retries — clear `.cache/huggingface/download` of 0-byte files occasionally to reclaim a few GB.
- **GPU 0 is half-reserved**: vllm `--gpu-memory-utilization 0.5` holds ~71GB of H200-0 for a 7B GGUF. Raise to 0.9 when serving bigger models; llama.cpp (GPU 1) uses ~4GB only.
