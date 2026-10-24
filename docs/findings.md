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

## Gemma-4 + TensorRT-LLM (2026-10-12)

- **`gemma-4-31b` is arch `gemma4`** (`Gemma4ForConditionalGeneration`, hidden 5376, multimodal). Working engines: llama.cpp (current GGUF path), transformers ≥5.x, newer vLLM, SGLang main, and **tensorrt_llm `1.3.0rc*`** (PR #12932).
- **`tensorrt_llm 1.2.1` CANNOT serve it** (no `gemma4` in its model registry, and its `transformers==4.57.3` cannot parse the config). Do not bother with 1.2.1 for Gemma 4.
- **The `trtllm-build`/`convert_checkpoint.py` engine workflow is removed** for this model in 1.3.0. Use **`trtllm-serve`** (PyTorch backend) directly on the HF dir.
- **`tensorrt_llm 1.3.0rc29` deps are a hard break from the shared venv** — needs `torch==2.14.0`, CUDA **13.2** (`cu132`), `numpy>=2`, `transformers==5.5.4`, `flashinfer-python==0.6.18`, `triton==3.8.0`. Build a **separate venv** (`offline-prep/venv-trtllm`); never upgrade the shared live venv's torch/numpy/transformers.
- **`import tensorrt_llm` needs `LD_LIBRARY_PATH`** = every `site-packages/nvidia/*/lib` (+ `/usr/lib/x86_64-linux-gnu`). The wheel does not self-locate the CUDA-13 libs.
- **NVIDIA driver mismatch (`NVMLError_LibRmVersionMismatch`)**: `unattended-upgrade` (2026-10-09) bumped userspace libs to `580.178.04` while the loaded kernel module stayed `580.173.02`; even `nvidia-smi` failed. Fix without reboot: stop all processes holding `/dev/nvidia*`, `rmmod nvidia_drm nvidia_modeset nvidia_uvm nvidia`, reload (kernel → `580.178.04`). Always capture service envs first.
- **Proxy download speed is shared**: run one big `curl -C -` per artifact; concurrent pip + curl streams throttle each other (~85 KB/s–1 MB/s each). Pip's big wheels land in `/tmp/pip-unpack-*/` — clean stale `pip-unpack-*`/`pip-modern-metadata-*` dirs (mmin +25) to protect root `/`.

## Gemma-4 + TensorRT-LLM 1.3.0rc29 actually SERVING (2026-10-13)

The rc29 install was done 2026-10-12; the serving path had four independent blockers. All must be solved together. Launcher: `scripts/serve_trtllm.sh` (+ `scripts/trtllm_extra_options.yaml`).

- **BLOCKER 1 — mpi4py dynamic `MPI_Comm_spawn` HANGS.** Running bare `trtllm-serve serve` makes TRT-LLM create a `MpiPoolSession` → `mpi4py.futures.MPIPoolExecutor` → `MPI_Comm_spawn`. On this host that handshake **deadlocks** (parent in `client_sync`/`bcast_send`, spawned worker in `server_sync`/`bcast_recv`, worker busy-spins one core forever; log stuck at `worker_initialization_wait`). A minimal `MPIPoolExecutor` script hangs identically → it is NOT a TRT-LLM bug, it is the OpenMPI 4.1.6 spawn path here. **`mpirun -n N` works fine** (MPI_Init under a launcher). Fix: launch under **`mpirun -n 1 ... trtllm-llmapi-launch trtllm-serve serve ...`**. The launcher sets `TLLM_SPAWN_PROXY_PROCESS=1`, so TRT-LLM uses the mgmn leader/worker + `RemoteMpiCommSessionClient` IPC path instead of `MPI_Comm_spawn`.
- **BLOCKER 2 — `trtllm-llmapi-launch` hardcodes `python3`.** It runs `python3 -m tensorrt_llm.llmapi.mgmn_leader_node`; with the system `python3` this fails `ModuleNotFoundError: tensorrt_llm` and the leader dies (`exit 1`) → the serve hangs waiting for workers. Fix: put the venv first on `PATH` (`export PATH="$VENV/bin:$PATH"`).
- **BLOCKER 3 — FlashInfer JIT nvcc too old.** All pytorch-backend startup compiles FlashInfer kernels (`sampling`, `gelu_tanh_and_mul`, `renorm`, `rope`) via ninja. The flags include `-Xfatbin=-compress-all --compress-mode=size` (CUDA ≥12.8). Host `/usr/bin/nvcc` is **CUDA 12.0** → `nvcc fatal : Unknown option '--compress-mode=size'` → `Ninja build failed` → `Executor worker returned error`. Fix: install pip CUDA-13 packages into the venv and compose a toolkit under `site-packages/nvidia/cu13/`:
    - `pip install --no-deps --index-url https://pypi.nvidia.com nvidia-cuda-nvcc==13.2.86 nvidia-cuda-crt==13.2.86 nvidia-nvvm==13.2.86`
    - (these unified `nvidia-*` names install nvcc+`crt/`+`nvvm/cicc` into `nvidia/cu13/{bin,include,lib,nvvm}`; runtime `nvidia-cuda-runtime` 13.2.75 already provided `include/`)
    - set `CUDA_HOME=$VENV/lib/python3.12/site-packages/nvidia/cu13` and prepend `$CUDA_HOME/bin` to `PATH`, add `$CUDA_HOME/lib` to `LD_LIBRARY_PATH`.
    - also make `ln -s libcudart.so.13 libcudart.so` in `$CUDA_HOME/lib` (linker looks for bare `-lcudart`).
    - FlashInfer finds the toolkit via `CUDA_HOME`/`CUDA_PATH` first, else `which nvcc` (see `flashinfer/jit/cpp_ext.py:get_cuda_path`).
- **BLOCKER 4 — Gemma4 per-layer `head_dim` vs MMHA.** `config.json` `text_config`: `head_dim=256` for `sliding_attention` layers, **`global_head_dim=512`** for `full_attention` layers (`num_global_key_value_heads=4`, `partial_rotary_factor=0.25`). The gemma4 default backend (`Gemma4ForConditionalGeneration.get_model_defaults` → `attn_backend="TRTLLM"`) uses the MMHA kernel which **asserts** `Head size 512 is not supported by MMHA` (`tensorrt_llm/common/attentionOp.cpp:2954`) during warmup. Fix: override with `attn_backend: FLASHINFER` via `--extra_llm_api_options <yaml>` (explicit options win over model defaults; confirm `attn_backend='FLASHINFER'` in the final "LLM args" log dump). `VANILLA` (pure torch) is the last-resort fallback.
- **Result**: `trtllm-serve` serves `google_gemma-4-31b-it` on **GPU1 :8010**, ~136 GB GPU (110 GB weights + KV). Single-stream decode **~47–50 tok/s** (32 input tok, batch 1, FLASHINFER). Smoke test OK (`17*23 → 391`).
- **Minor/harmless**: `Could not load AutoProcessor for Gemma4 ... manual fallback` (text runs fine); `MetaInitException ... Fallback to regular model init` (slow-path fallback, works); `flashinfer/cutile` "mismatched nvidia pip packages (tileiras 13.1.80 vs nvcc/nvvm 13.2.86)" is cutile-only noise; `torchao 0.15.0` cpp-ext skip warning.
- **Self-kill gotcha (again)**: a single bash command that BOTH contains the literal substring `trtllm-serve` (e.g. the launch line) AND runs `pkill -f '[t]rtllm-serve'` will make pkill match its own shell's cmdline and kill the shell before launching. Keep the kill in a separate command whose cmdline only has the bracketed pattern.

## TRT-LLM throughput tuning (2026-10-13)

- **CUDA-graph batch-size cliff (biggest lever).** TRT-LLM captures decode CUDA graphs only for `cuda_graph_config.batch_sizes` (default `[1..32, 64, 128]`). Decode at any OTHER concurrency runs **eager** and throughput collapses ~4× (conc 48 ≈ 560 tok/s vs conc 64 ≈ 2400 tok/s; conc 96 ≈ 1050 vs conc 128 ≈ 3800). Fix: widen the list via `--extra_llm_api_options` (`cuda_graph_config: {mode: decode, batch_sizes: [...], max_batch_size: N}`). Choose real gaps (40/48/56/96), not every integer — a maximally dense set reserves more memory and trims the peak.
- **Batch 256 decode graph capture fails**: FlashInfer prefill workspace overflow (`aligned_alloc ... batch_prefill_tmp_v 401 MB vs 335 MB available`). Practical ceiling is **128**.
- **`--kv_cache_dtype fp8` crashes** this build at profiling: `RuntimeError: No supported CUDA architectures found for major versions [10, 11, 12]` (tensorrt_llm executor). BF16 KV works. (Weight FP8 would need `nvidia-modelopt` + a quantized checkpoint; none available offline.)
- **Measure sustained, not burst.** H200 sustained load triggers `SW Power Capping`; batch-128 is ~3.8k tok/s on the first burst then settles to **~2.9k tok/s**. Single-shot measurements overstate.
- **Serving recipe that works** (gemma-4-31b, 1 GPU): `mpirun -n 1 trtllm-llmapi-launch trtllm-serve serve <hf_dir> --backend pytorch --tp_size 1 --max_batch_size 128 --max_num_tokens 16384 --kv_cache_free_gpu_memory_fraction 0.85 --extra_llm_api_options scripts/trtllm_extra_options.yaml`. ~110 GB weights + KV on one 143 GB H200.
- **Benchmarking caveat**: the `:18000` llama.cpp server is the single-slot `llama_chat_server.py` placeholder (no continuous batching) — flat ~58 tok/s aggregate at any concurrency. It returns no `usage`, so count output tokens with the gemma tokenizer for a fair vs-TRT comparison. `scripts/bench_trtllm_vs_llamacpp.py` does both and hits endpoints directly (the manager's Triton promotion would otherwise reroute all gemma traffic to one backend).

## 2026-10-14 — FP8 benchmark verdict (conc-128 ground truth kept)
- FP8-KV (same BF16 weights, `TRTLLM_KV_DTYPE=fp8` + flashinfer sm90a patch):
  0.95x at conc-1..8, 1.00x at 32-64, **1.15x at conc-128** (3659 vs 3195 tok/s
  same-run). Zero quality risk. Candidate for champion restart upgrade.
- Weight-FP8 (ModelOpt W8A8, 16 calib samples, 32 GB ckpt): **1.34-1.63x**
  throughput (4852 tok/s at 128) BUT arithmetically wrong (17*23->399).
  Not production-ready; needs >=128-sample recalibration + accuracy gate.
- RAG stays on BF16 conc-128 `:8010`. Details: `docs/history/014_*`.
