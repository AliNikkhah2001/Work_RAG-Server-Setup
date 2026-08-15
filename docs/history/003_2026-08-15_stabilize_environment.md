# 2026-08-15 — P0: Environment Stabilization

## Current status

- **Stale paths fixed.** `offline_prepare_cli.py:19` `BASE_DIR` now resolves from `__file__` → `/splunk-data/v1/Work_RAG-Server-Setup/offline-prep` (was hardcoded `/ai-gpu1/v1/...`, which does not exist). Verified resolution.
- **Venv repaired.** All 44+ entry-point shebangs and the 3 `activate` scripts pointed at the dead `/ai-gpu1/...` path. Bulk `sed` replaced them with `/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/venv/bin/python3`. 0 remaining stale references. `pip`, `uv`, `hf`, `torchrun`, `uvicorn` now run directly (previously "required file not found").
- **Stack baseline verified:**
  - Running: `webui-test` (open-webui, healthy, :13000), `pgvector-test` (:15432), `qdrant-test` (:16333), `redis-test` (:16379)
  - `milvus-test` (milvus:latest) restarted — exited 134 previously, now `Up`, gin server responding on :19530 (embedded standalone)
- venv intact: python 3.12.3, torch 2.4.0+cu124, vllm 0.6.1.post1, llama_cpp importable.
- Proxy env active for all tools; disk 5.6T free.

## Changes made

- `offline_prepare_cli.py:19` — `BASE_DIR` → `Path(__file__).resolve().parent / "offline-prep"`
- `offline-prep/venv/bin/*` — shebang + `VIRTUAL_ENV` paths fixed (34 via bulk sed, 7 individually, 3 activate scripts)

## Known issues (still open)

- numpy conflict: vllm pins numpy 1.26.4; `scipy 1.18.0` and `faiss-gpu-cu12 1.14.1.post1` want numpy>=2. Warnings on import (transformers/metrics). Left as-is: vllm is the production path; revisit only if a scipy/faiss-dependent workload breaks.
- milvus runs but was exited (134) previously; monitored.

## Verification commands used

```
offline-prep/venv/bin/python3.12 -c "import torch,vllm,llama_cpp; print(torch.__version__)"
offline-prep/venv/bin/pip --version          # fixed
offline-prep/venv/bin/uv --version           # fixed
offline-prep/venv/bin/hf version             # fixed
docker ps                                    # 5 containers up
```
