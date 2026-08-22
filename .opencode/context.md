# Project Context - RAG H200 + OpenCode Integration

## Environment
- Host ai-gpu1 2x H200 143GB, proxy 192.168.203.2:3128, work dir /splunk-data/v1/Work_RAG-Server-Setup
- Master venv offline-prep/venv py3.12.3 torch2.4+cu124 vllm0.6.1 etc
- Docker: webui 13000, milvus 19530, pgvector 15432, qdrant 16333, redis 16379
- Models: gemma-4-31b 19.6G 0.663 champion, gemma-3-27b 16.5G, qwen3.8 17.8G, qwen3-30b 18.6G, nemotron 30.2G, qwen2.5-7b 4.4G, llama3.2 1.9G, mistral 4.1G, phi3 2.4G, deepseek 148G, qwen72b partial, embeds bge-m3/e5-small etc

## LLM Inference Manager (NEW)
- Path llm_inference_manager/app.py port 9000, DB manager.db, 11 model registry, CORS, SQLite sessions/metrics
- Endpoints: /health, /v1/models + /{id}, /v1/chat/completions (round-robin, latency header), /v1/completions, /v1/sessions, /admin/status/metrics, /admin/models/load|unload
- Currently running: 5x gemma 8080-8084 + qwen2.5-7b 8090 + embeds 8001-8003 + lightrag 9621 + webui 13000
- Health verified 200 for all, chat tested via manager for gemma/qwen, sessions history inject fixed

## OpenCode Self-Hosted Integration
- User: a.nikkhah config at /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc
- Existing: provider gemma-4-31b-local with 5 models pointing directly to 8080-8084 (per-port baseURL)
- Desired: switch to manager at 9000/v1 as single provider, add ALL 11 models named with family/benchmark, test working via opencode
- Root config at /splunk-data/home/root/.config/opencode/opencode.jsonc only has plugin orchestrator
- Pending: rewrite a.nikkhah config to use manager baseURL, add 11 models (gemma-4-31b, gemma-3-27b, qwen3.8-27b, qwen3-30b-a3b, nemotron-49b, qwen2.5-7b, llama-3.2-3b, mistral-7b, phi-3-mini, deepseek-v4-flash, qwen2.5-72b) with proper names/quant/context/benchmark, ensure load-on-demand via /admin/models/load works, test each via opencode run / curl through manager

## Current Status
- DONE: gemma 5x verified, manager built/tested, qwen spawn tested, LightRAG health, corpus 11 docs ingested then pending re-ingest after restart, playwright job running
- PENDING: update opencode.jsonc to manager-based provider with all models named, test each model via opencode (run opencode command or curl through opencode's proxy), verify session/history still works, reconnect webui if needed, benchmark comparison report still pending

## Pending Tasks (M1-M8 from todo.md)
- M1 embed/llm verified, corpus done
- M2 LightRAG needs 10 Q&A queries re-run
- M3 Dify images ready 1.16.1 not started
- M4 AnythingLLM 1.15.0 not started
- M5 RAGFlow no venv
- M6 RAG benchmarks research/fetch
- M7 comparison tables + report + push branch rag-e2e-benchmark
- M8 final verification
