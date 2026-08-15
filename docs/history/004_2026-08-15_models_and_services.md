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
