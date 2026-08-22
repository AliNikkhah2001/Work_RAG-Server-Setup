# Project Context - RAG H200 + OpenCode Manager

## Environment
- ai-gpu1 2xH200 143GB, proxy 192.168.203.2:3128, dir /splunk-data/v1/Work_RAG-Server-Setup
- Venv offline-prep/venv py3.12.3, docker: webui 13000, milvus 19530, pgvector 15432, qdrant 16333, redis 16379
- Models: gemma-4 19.6G champion 5x 8080-84, plus 10 others registered in manager (qwen, nemotron etc), embeds 8001-8003
- Manager :9000 running, 11 model registry, health 200, chat works via curl (gemma/qwen verified)

## OpenCode Integration - ONLY TASK
- Config: /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc
- Previous step: added provider h200-manager with 11 named models + kept gemma-4-31b-local 5 models; fixed limit context+output and mcp servers wrapper; `opencode models` now lists 16 local models + remote
- New fix just applied: moved `baseURL` from provider top-level to `options.baseURL` (schema requires ProviderConfig.options.baseURL) for both providers, added apiKey sk-local-dev
- Pending: test `OPENCODE_CONFIG=... opencode run --model h200-manager/gemma-4-31b "hello"` and same for qwen2.5-7b, verify manager proxy works via opencode (was failing with undefined/chat/completions, should now resolve to http://localhost:9000/v1/chat/completions)
- After test: verify all 11 models visible and at least 2 loaded ones respond, document curl vs opencode

## Current Status
- DONE: gemma 5x verified, manager built+health+models+chat via curl ok, qwen spawn 8090 ok, opencode models listing ok after schema fix, baseURL nesting fixed
- PENDING: run opencode integration tests (2 models first), ensure manager session/history still 200

## Pending Tasks
- TEST opencode run h200-manager/gemma-4-31b and qwen2.5-7b via fixed config
- OPTIONAL: on-demand load for remaining 9 models via POST /admin/models/load if requested

## Notes
- Test cmd: OPENCODE_CONFIG=/splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc /root/.opencode/bin/opencode run --model h200-manager/gemma-4-31b "Reply one word: Hello"
- Manager logs logs/manager.log, curl test still: curl 9000/v1/chat/completions
