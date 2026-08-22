# Project Context - RAG H200 + OpenCode Manager (post-fix)

## Environment
- ai-gpu1 2xH200 143GB, proxy 192.168.203.2:3128, dir /splunk-data/v1/Work_RAG-Server-Setup
- Venv offline-prep/venv py3.12.3, docker: webui 13000, milvus 19530, pgvector 15432, qdrant 16333, redis 16379
- Models: gemma-4 19.6G 0.663 (5x 8080-84), plus 10 others in registry (qwen, nemotron, etc), embeds 8001-8003
- Manager :9000 running (11 models, SQLite sessions, round-robin), health 200, chat via manager works (gemma+qwen tested via curl)

## OpenCode Integration - CURRENT FAILURE
- Config: /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc
- Fixed schema errors: limit now requires context+output (added), mcp fixed (removed servers wrapper, added enabled true)
- Result: `opencode models` now lists 16 local models correctly (5 gemma-local + 11 h200-manager with names)
- NEW FAILURE on `opencode run --model h200-manager/gemma-4-31b`: Error "undefined/chat/completions" cannot be parsed as URL
- Root cause: provider baseURL was placed at top-level `baseURL` but schema requires `options.baseURL` inside ProviderConfig.options (see ProviderConfig properties). Need to move baseURL under `provider.h200-manager.options.baseURL` and `provider.gemma-4-31b-local.options.baseURL` (and per-model baseURL under options too)
- Next fix: update opencode.jsonc to use `options: { baseURL: "http://localhost:9000/v1", apiKey: "sk-local-dev" }` pattern, re-test `opencode run`, then test all 11 models (loaded gemma+qwen first, then on-demand load others via POST /admin/models/load)

## Current Status
- DONE: gemma 5x verified, manager health+models+chat validated via curl, qwen spawn 8090 verified, opencode models listing works after schema fix
- PENDING: fix provider baseURL nesting (options.baseURL), re-test opencode run for all models, then proceed to RAG e2e (LightRAG re-ingest, Dify/AnythingLLM/RAGFlow) and benchmark report M1-M8

## Pending Tasks
- FIX opencode.jsonc provider options.baseURL
- TEST opencode run for h200-manager/gemma-4-31b and qwen2.5-7b, then remaining 9 via manager load
- RAG: LightRAG 10 Q&A, Dify compose, AnythingLLM, RAGFlow, benchmarks, comparison report branch

## Notes
- Manager docs: http://192.168.96.82:9000/docs
- Test via curl still works: curl 9000/v1/chat/completions model gemma-4-31b
- Need to set apiKey dummy for openai provider or manager will allow anonymous
