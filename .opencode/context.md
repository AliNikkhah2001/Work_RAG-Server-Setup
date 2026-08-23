# Project Context

## Environment
- ai-gpu1 2xH200 143GB, proxy 192.168.203.2:3128, dir /splunk-data/v1/Work_RAG-Server-Setup
- Venv py3.12.3, docker webui13000/milvus19530/pgvector15432/qdrant16333/redis16379, embeds 8001-3
- Models gemma-4 19.6G 5x 8080-84, qwen2.5-7b 8090, others registered, manager :9000

## OpenCode Integration - FIXED & VERIFIED
- Config: /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc - fixed: limit {context,output}, mcp without servers wrapper, provider options.baseURL (was top-level, moved to options.baseURL with apiKey), added h200-manager 11 models named
- Models list: 16 local models visible (5 gemma-local + 11 h200-manager gemma-4-31b/gemma-3/qwen2.5-7b/nemotron/qwen3.8/llama3.2/qwen3-30b/mistral/phi3/deepseek/qwen72b)
- Manager fix: httpx AsyncClient trust_env=False added to bypass squid proxy for localhost backends (was causing ConnectError All attempts failed)
- Verification:
  - curl direct via manager: gemma 9000 chat -> Hello! qwen -> salaam OK
  - after host uvicorn 1032494 killed (conflicted 8080) + supervisor restart, all 5 gemma + manager healthy
  - opencode: `opencode models` now lists h200-manager/* correctly
  - `opencode run --model h200-manager/gemma-4-31b --format json` now WORKS: manager logs show 20+ POST /v1/chat/completions 200 OK, JSON events streaming (step_start/finish, text parts). Previous undefined error fixed. Hangs due to interactive agentic loop / compaction_continue loop, not API error - API calls succeed.
  - Same for qwen: manager routes to 8090

## Current Status
- DONE: gemma 5x, manager 9000 with proxy fix, opencode config validated, models listed, chat via opencode now hits manager successfully
- PENDING: need non-hanging simple test: use `opencode run --model h200-manager/gemma-4-31b --format json --auto "say hello one word"` or direct curl via manager is canonical; also test all 11 models via curl through manager (not opencode) to avoid agentic loop

## Pending Tasks
- Final test: curl loop for all 11 manager models via 9000, document each working/available vs needs load
- Update README/push if needed, keep manager running
