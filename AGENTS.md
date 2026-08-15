# AGENTS.md

Offline-preparation tooling for a RAG server on an NVIDIA H200 box (`ai-gpu1`: 2x H200 NVL, driver 580.173.02, CUDA 13.0 runtime). Goal: stage docker images, wheels, HF models, and sample projects so they can be deployed offline. All network traffic must go through the corporate Squid proxy `http://192.168.203.2:3128`.

Only 5 files are tracked in git (`README.md`, `offline_prepare_cli.py`, `start.sh`, `proxy_setup.sh`, `fix_env.sh`). `offline-prep/`, `dify/`, `.deepeval/`, and the `pip-*` temp dirs are untracked working data. Remote: `github.com/AliNikkhah2001/Work_RAG-Server-Setup`.

## Critical: stale `/ai-gpu1/...` paths

Everything (scripts AND the venv shebangs) was written against the old mount path `/ai-gpu1/v1/Work_RAG-Server-Setup`, which **does not exist** on this host. The live working directory is `/splunk-data/v1/Work_RAG-Server-Setup`:

- `offline_prepare_cli.py:19` hardcodes `BASE_DIR = Path("/ai-gpu1/v1/Work_RAG-Server-Setup/offline-prep")`. Running the CLI as-is would create an empty state tree at a non-existent path. Fix `BASE_DIR` to `/splunk-data/v1/Work_RAG-Server-Setup/offline-prep` (or `Path(__file__).parent / "offline-prep"`) before running it against real data.
- Every console script in `offline-prep/venv/bin/` (`pip`, `uv`, `hf`, `python3.12`, all entry points) has a shebang pointing at `/ai-gpu1/v1/.../venv/bin/python3`, so bare `venv/bin/pip` fails with "required file not found". Workaround: use `offline-prep/venv/bin/python3.12 -m pip ...` (the `python3.12` → `/usr/bin/python3` symlink resolves). Do **not** `rm -rf` the venv — it holds working installs built over days.

## Environment facts (verified)

- Proxy is required for shell, apt, git, docker daemon, pip, and HF. `proxy_setup.sh` configures all of them; `start.sh` bootstraps the OS env and launches the CLI in tmux session `offline_prep` (attach: `tmux attach -t offline_prep`).
- Master venv `offline-prep/venv` (Python 3.12.3) currently has working: torch 2.4.0+cu124, torchvision 0.19.0+cu124, torchaudio 2.4.0+cu124, vllm 0.6.1.post1, flash-attn 2.6.3, llama-cpp-python 0.3.34, sglang 0.3.0, faiss-gpu-cu12 1.14.1.post1, bitsandbytes. Host nvcc is CUDA 12.0; runtime/driver reports CUDA 13.0; wheels are cu124 builds.
- Known unresolved conflict: vllm pins numpy 1.26.4, but faiss-gpu-cu12 and scipy 1.18.0 require numpy>=2.
- Docker state: open-webui, milvus, pgvector, qdrant, redis images are pulled and running (see `logs/docker_health.log`). `vllm/vllm-openai` and `nvidia/cuda:*` pulls consistently fail with "short read ... unexpected EOF" (proxy instability).
- `.state.json` / `.retry_queue.json` in `offline-prep/` are **stale** — they mark many tasks "failed" (torch 2.4.0, vllm, etc.) that were later installed successfully by hand. Treat them as history, never as current truth. `offline-prep/import_report.txt` (Aug 10) is likewise obsolete.

## Working layout: `offline-prep/`

- `docker-images/*.tar` — pulled images saved via `docker save`
- `python-packages/*.whl`, `python-packages-cu124/*.whl` — downloaded wheels
- `models/huggingface/<repo_id with / → _>/` — HF model downloads
- `sample-projects/{dify,anything-llm,ragflow,lightrag}/` — git clones
- `logs/` — `dl_*.log`, `install_*.log`, `main.log`, `errors.log`
- `.state.json` — CLI task state machine; `COMPREHENSIVE_REPORT.md`, `failed_tasks.json`, `failed_tasks.log` — output artifacts

## Documentation convention (do this every session)

- Maintain detailed markdown history of installations and findings under `docs/history/` — one file per work day/session, with exact commands, versions, and outcomes. Seed files already exist; append new sections rather than rewriting.
- Keep a short "current status" summary at the top of each history file. When a file grows long (> ~300 lines), condense the old detail into an archive section/file and leave a pointer — do not let docs become unreadable.
- After any install or discovery, update the docs. Never rely on `.state.json` or log files alone as the record of what's installed.
- Store "things you found out" (gotchas, quirks, env facts) in `docs/findings.md`, not inside code comments.

## Commands

- Launch prep CLI: `bash start.sh` (bootstraps env, runs in tmux `offline_prep`)
- Venv interpreter: `offline-prep/venv/bin/python3.12`
- Venv pip: `offline-prep/venv/bin/python3.12 -m pip ...` (bare `venv/bin/pip` is broken)
- Set proxy for current shell: `source proxy_setup.sh`
- No tests, lint, or build tooling is configured in this repo.

## Nested repos — don't touch

`dify/` (repo root) and `offline-prep/sample-projects/*` are upstream git clones. `dify/AGENTS.md` (symlinked as `CLAUDE.md`) belongs to the upstream Dify project, not to this repo; leave it and the clones alone.
