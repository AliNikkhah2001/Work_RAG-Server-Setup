# 2026-08-15 — Models, Inference Services, Scipy Fix

## Current status

- **scipy fixed**: 1.18.0 → 1.13.1 (numpy-1.26-compatible). 1.18.0 crashed on import (`np.long` AttributeError), breaking `sentence_transformers`. Keep scipy ≤1.13.x while vllm pins numpy 1.26.4.
- **Qwen2.5-7B Q4_K_M downloaded + validated** (4.68 GB single-file from `bartowski/Qwen2.5-7B-Instruct-GGUF`). Required 8 flaky-proxy retries (each broke at ~500MB-2GB with `IncompleteRead`); final ~25 MB finished with `curl -C -` resume. Validated via llama.cpp load test.
- **Services live**: embeddings `:8001` (bge-small, dim 384), llama.cpp chat `:8080` (smoke-tested on Mistral IQ2_M). vLLM launcher script ready.
- **Still downloading in background**: `bartowski/Llama-3.2-3B-Instruct-GGUF` Q4_K_M (started), then Mistral Q4_K_M.

## Decisions & findings

- Chose **bartowski single-file** Qwen Q4_K_M over the official `Qwen/Qwen2.5-7B-Instruct-GGUF` (which ships Q4_K_M as 2 parts): **vLLM's GGUF loader reads a single file** and cannot consume split GGUFs (verified in `vllm/model_executor/model_loader/loader.py` / `weight_utils.py:gguf_quant_weights_iterator`). The single file serves both llama.cpp and vLLM.
- **HF XET is the proxy failure point**: all `hf download` failures were `OSError: I/O error` in `huggingface_hub.file_download.xet_get`. Setting `HF_HUB_DISABLE_XET=1` routes around it (used by `scripts/download_models.py`).
- vLLM 0.6.1.post1 GGUF flags verified: `--load-format gguf --quantization gguf`.

## New/changed files

- `scripts/download_models.py` — proxy-resilient downloader (XET off, retries, resume)
- `scripts/services/embed_server.py` — OpenAI-compatible `/v1/embeddings` (sentence-transformers)
- `scripts/services/llama_chat_server.py` — OpenAI-compatible chat via `llama_cpp.Llama`
- `scripts/services/vllm_server.sh` — vLLM API server launcher (single-file GGUF)
- `scripts/rag_test_harness.py` — shared RAG smoke test harness for P4
- `deploy/docker-compose.yml` — reference compose for the 5-container data plane
- `offline-prep/sample-projects/lightrag/venv` — dedicated venv created (deps not yet installed)

## Verification

- `QWEN LOAD OK` via llama.cpp (4.68 GB file, `n_gpu_layers=-1`)
- Embeddings: 2 inputs → 2×384-dim vectors, HTTP 200
- llama.cpp chat: `/health` ok, `/v1/chat/completions` answered (Mistral IQ2_M)

## Docs

- `docs/findings.md` updated: scipy fix, XET, running services, vLLM GGUF requirement, local paths fixed.
- `docs/history/003` covers the P0 path fixes.

## Session continuation — tooling, data plane, downloads (same day)

### Current status

- Background model downloads still running (`scripts/download_models.py`, pid alive): Llama-3.2-3B Q4_K_M ~58% as of last check; Mistral-7B Q4_K_M resuming from a **3.22 GB partial cached on Aug 10** (~74% already on disk), so both should finish within ~1 h total. Qwen 7B already 100%.
- Progress dashboard live: `scripts/progress_report.py` (ASCII bars for downloads + service health + plan %) — reads the largest `.incomplete` per model dir and the newest `dl_models_*.log`. Tested with `--once`.
- **Data plane provisioned**: `deploy/setup_data_plane.py` created `rag_docs` collection/table in all three stores (Milvus dim-384 IVF_FLAT/COSINE, Qdrant cosine, pgvector `vector(384)` extension+table). Installed `psycopg2-binary 2.9.12` into the master venv for pgvector.
- **Open WebUI rewired**: container recreated (stateless, no volumes) via `deploy/recreate_webui.sh` with `OPENAI_API_BASE_URL=http://host.docker.internal:8080/v1` (llama.cpp) + `--add-host host.docker.internal:host-gateway`. Health `200`, `Up (healthy)`.
- LightRAG runner written: `scripts/services/lightrag_run.sh` (env: `LLM_BINDING=openai` → `:8080/v1`, `EMBEDDING_BINDING=openai` → `:8001/v1`, model `qwen2.5:7b`, storage under `lightrag/rag_storage`, server on `:9621`). Deps not yet installed — queued until downloads finish (avoid bandwidth contention).

### New/changed files

- `scripts/progress_report.py` — dashboard (parses plan.md `[x]`/`[ ]`)
- `deploy/setup_data_plane.py` — Milvus/Qdrant/pgvector collection creation (idempotent)
- `deploy/recreate_webui.sh` — recreate webui-test bound to local OpenAI endpoints
- `scripts/services/lightrag_run.sh` — LightRAG API server launcher
- `docs/plan.md` — machine-parseable deliverable checklist (dashboard reads it)
- `.gitignore` — `deploy/data_plane_status.json`

### Committed

- `f8e3766 Add progress dashboard, data-plane setup, and lightrag/webui run scripts`

### Next

- Wait for Llama/Mistral Q4_K_M (job → Mistral after Llama, resumes the Aug 10 partial).
- Then: vLLM + llama.cpp serving Qwen on :8000/:8080, lightrag deps install + run, end-to-end ingest→retrieve test.

## Session verification round — full system audit (same day)

### Verdicts

- **Libraries**: master venv imports 20/20 (sseclient installed), all CUDA-exts import AND run on GPU (flash-attn 2.6.3 forward OK, bitsandbytes Linear4bit forward OK, vllm/sglang import OK). LightRAG venv is still empty (deps deferred until downloads finish).
- **GPU stack**: 2x H200 NVL visible; torch 2.4.0+cu124 `cuda.is_available()=True`, matmul on GPU0 correct (fp32 err 4.9e-4). Driver 580.173.02 ↔ torch cu124 match OK; no errors.
- **Docker/services**: 5 containers all up+healthy (webui :13000, milvus :19530, pgvector :15432, qdrant :16333, redis :16379). Interconnect test passed: redis ping, pgvector ext `vector 0.8.6` + `rag_docs` table, milvus/qdrant `rag_docs` collection.
- **Gaps vs. expectation**: monitoring stack (grafana/prometheus/otel) NOT present; `pghistory` extension NOT installed; `vllm/vllm-openai` and `nvidia/cuda` docker images never pulled.
- **Inference on API endpoints**:
  - llama.cpp `:8080` now serves **Qwen2.5-7B Q4_K_M** (model-id `qwen2.5:7b`); `/v1/chat/completions` + streaming + `/v1/models` verified (reply `RAG-API-OK`).
  - vLLM `:8000` serves same GGUF (model-id `qwen2.5:7b-vllm`); **53.6 tok/s** (512-token gen); needs the vocab-assert patch + pyairports stub (see findings).
  - Embeddings `:8001` dim-384 verified.
- **vLLM GGUF fixes applied to the venv** (documented in `docs/findings.md`): relaxed vocab assert in `vocab_parallel_embedding.py:381`; pyairports stub; wrapper model dir `offline-prep/models/gguf-wrappers/qwen2.5-7b-q4km/`.
