# OpenCode Integration — cached (verified 2026-08-23 LIVE)

## Config Files
- Primary: `/splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc` (copy to `/root/.config/opencode/opencode.jsonc` for root)
- Sync: `cp /splunk-data/home/a.nikkhah/.config/opencode/opencode.jsonc /root/.config/opencode/opencode.jsonc`

## Schema (fixed 2026-08-23)
```json
{
  "provider": {
    "type": "openai",
    "options": {
      "baseURL": "http://localhost:9000/v1",
      "apiKey": "sk-local-dev"
    }
  },
  "models": {
    "h200-manager/gemma-4-31b": { "limit": {"context":8192,"output":8192} },
    "h200-manager/gemma-3-27b": {},
    "h200-manager/qwen2.5-7b": {},
    "h200-manager/qwen3.8-27b": {},
    "h200-manager/qwen3-30b-a3b": {},
    "h200-manager/nemotron-49b": {},
    "h200-manager/llama-3.2-3b": {},
    "h200-manager/mistral-7b": {},
    "h200-manager/phi-3-mini": {},
    "h200-manager/deepseek-v4-flash": {},
    "h200-manager/qwen2.5-72b": {},
    "gemma-4-31b-local/gemma-4-31b-1": { "options":{"baseURL":"http://localhost:8080/v1"} },
    "gemma-4-31b-local/gemma-4-31b-2": {},
    "gemma-4-31b-local/gemma-4-31b-3": {},
    "gemma-4-31b-local/gemma-4-31b-4": {},
    "gemma-4-31b-local/gemma-4-31b-5": {}
  },
  "mcp": {}
}
```
Notes:
- Old bug: `baseURL` top-level, `limit` missing, `mcp.servers` wrapper => fixed to `options.baseURL`, `limit:{context:8192,output:8192}`, `mcp` without wrapper
- Each h200-manager model maps to manager :9000 which rounds-robin to backends (8080-84 gemma, 8090 qwen)
- Local gemma provider directly hits 8080 (single shard) for comparison

## Verification LIVE
```bash
opencode models 2>&1 | grep h200-manager
# 11 lines: h200-manager/gemma-4-31b ... qwen2.5-72b

opencode models 2>&1 | grep gemma-4-31b-local
# 5 lines

curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"say hello one word"}]}' | jq
# 200 Hello - canonical (always works)

timeout 25 opencode run --model h200-manager/gemma-4-31b --format json "say hello one word, no tools"
# Now WORKS: manager logs show 20+ POST /v1/chat/completions 200 OK with JSON events step_start/finish + text parts
# Previously: UnknownError err_94 fixed via trust_env=False + supervisor restart + kill uvicorn 1032494
# Hang cause: agentic compaction_continue loop, not API error => wrap with timeout 25/60, fallback to curl canonical
# Same for qwen: opencode run --model h200-manager/qwen2.5-7b => routes to 8090

opencode run --model h200-manager/gemma-4-31b --format json "my name is Ali" --session Ali
# session memory: second turn "what is my name?" => Ali via manager session_id
```

## Files
- `scripts/opencode_test_session.sh` 4.2K +x wrapper timeout 60/30 + curl canonical + opencode run --format json + tail logs => `logs/opencode_session_*.log` (2 logs)
- `logs/manager_test_*.json` 3 logs, `logs/opencode_session_*.log`
- `docs/manager_openapi_curls.md` 7.8K

## Troubleshooting
- `opencode models` missing h200-manager => cp config from a.nikkhah to root
- `opencode run` hanging compaction_continue => use `timeout 25` + document as not API failure
- Proxy localhost failure => ensure manager trust_env=False + no_proxy

Evidence: `evidence_T1.4_T1.5_services.md` S1.5.5, manager logs stream events
