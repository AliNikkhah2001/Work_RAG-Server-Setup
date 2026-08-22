# Project Context

## Environment
- Host: ai-gpu1, 2x H200 NVL 143GB, Driver 580.173.02, CUDA 13.0 runtime, NVCC 12.0
- Work dir: /splunk-data/v1/Work_RAG-Server-Setup (old /ai-gpu1 path stale)
- Proxy: http://192.168.203.2:3128 required for all net
- Python: 3.12.3 offline-prep/venv (torch2.4+cu124, vllm0.6.1, flash-attn2.6.3, llama-cpp0.3.34, etc)
- Docker data plane: webui-test 13000->8080, milvus 19530, pgvector 15432, qdrant 16333, redis 16379, grafana 13001

## Project Type
- RAG dev/prod env, offline prep for HF models, wheels, docker images, 4 sample RAG projects (dify, anything-llm, ragflow, lightrag)
- Reports: docs/reports (Persian eval), Pages site, docs/history per-session logs

## Models Inventory (verified 2026-08-22)
- GGUF LLMs (offline-prep/models/huggingface):
  - gemma-4-31b Q4_K_M 19.6GB 0.663 champion - LOADED x5 on 8080-8084 via gemma_supervisor.sh
  - gemma-3-27b Q4_K_M 16.5GB 0.600
  - qwen3.8-27b Q4_K_M 17.8GB 0.477
  - qwen3-30b-a3b Q4_K_M 18.6GB 0.283
  - nemotron-49b Q4_K_M 30.2GB 0.494
  - qwen2.5-7b Q4_K_M 4.4GB - SPAWNED on 8090 via manager
  - llama-3.2-3b Q4_K_M 1.9GB
  - mistral-7b Q4_K_M 4.1GB
  - phi-3-mini q4 2.4GB
  - qwen2.5-72b variants partial 73GB
  - deepseek-v4-flash 148.7GB 46 shards (converted to mp2 safetensors in models/deepseek-v4-converted)
  - embeddings: bge-m3 2.1GB dim1024 (8002), bge-small-en 382MB dim384, e5-small 1.2GB dim384 (8001 default), paraphrase-multilingual 912MB dim384 (8003), all-MiniLM 932MB
- Services running: llama 8080-8084 (gemma), 8090 (qwen7b), embed 8001-8003, lightrag 9621 healthy, open-webui 13000 healthy

## LLM Inference Manager (new, 2026-08-22)
- Location: llm_inference_manager/app.py, DB manager.db, port 9000
- FastAPI gateway, CORS *, SQLite tables: models, api_tokens, chat_sessions, messages, metrics
- Registry: 11 models with metadata (creator, family, params, size, quant, path, context, benchmark_mean, status, backends)
- Features:
  - GET /health, /v1/models, /v1/models/{id}
  - POST /v1/chat/completions (proxy with round-robin, latency header, metrics log, session history inject)
  - POST /v1/completions
  - Sessions: POST/GET/DELETE /v1/sessions, /v1/sessions/{id}
  - Admin: /admin/status (gpu), /admin/metrics, /admin/models/load?model_id=&port=, /admin/models/unload
  - Auth: Bearer sk-local-dev (allow anonymous in dev)
  - Frontend: GET / (manager UI), docs at /docs
- Current state: running PID via nohup logs/manager.log, 1 loaded gemma pool + qwen dynamically loaded 8090, history injection fixed
- Needs: fix memory for session injection, recreate open-webui with OPENAI_API_BASE_URLS=http://172.17.0.1:9000/v1 for full frontend connection (webui-test currently points to nothing, needs restart with env)

## Current Status
- Completed: repo clone verified, models downloaded, gemma 5x instances verified via curl /v1/models and /v1/chat/completions, manager built and tested (models list, chat, model info, session create), qwen spawn tested, frontend webui reachable 13000
- Pending: open-webui -> manager wiring (set env and restart container), spawn more models on demand, full e2e RAG tests for 4 sample projects (dify, anything-llm, ragflow, lightrag already ingested example corpus to 9621), benchmark datasets fetch, comparison report + push to dedicated branch rag-e2e-benchmark
- Recent test: session memory fix applied, restarted manager, re-tested gemma and qwen, verified log truncated at compaction event
- GPU: free 67GB gpu0 + 96GB gpu1 after gemma pool + qwen

## Pending Tasks (from .opencode/todo.md M1-M8)
- M1: LLM+embed verify done, corpus 11 docs + qa_ground_truth.json created, playwright install background (job_5d554d3d running)
- M2: LightRAG ingest batch inserted 11 docs (analyzing->processing->done), pipeline 9621 healthy, need query test 10 Q&A
- M3: Dify docker images present (dify-api/web/sandbox etc), not yet started compose, needs configure local LLM/embed
- M4: AnythingLLM node_modules present 1.15.0, not yet started
- M5: RAGFlow no venv, feasibility pending
- M6: RAG benchmarks research/fetch (Persian fa_arc, Parsinlu etc already cached offline-prep/datasets)
- M7: Comparison tables + README report + push branch
- M8: Final verification

## Conventions
- Use offline-prep/venv/bin/python3.12 -m pip, not bare venv/bin/pip (shebang broken)
- HF vars: HF_HUB_DISABLE_XET=1, HF_HUB_ENABLE_HF_TRANSFER=0
- Docs: maintain docs/history per session, findings in docs/findings.md

## Notes
- GEMMA supervisor script: scripts/services/gemma_supervisor.sh loops 5 instances on 8080-8084 with CUDA_VISIBLE_DEVICES round-robin
- lightrag_run.sh uses LLM 8080 gemma + embed 8001 e5-small, storage rag_storage
- open gateway index at deploy/gateway/index.html maps /vllm /llama /webui etc but not manager yet
