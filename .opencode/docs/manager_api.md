# Manager API — cached research (verified 2026-08-23 LIVE on ai-gpu1)

Source: `llm_inference_manager/app.py` 580L FastAPI :9000, proxy `192.168.203.2:3128` bypass `trust_env=False`

## Architecture
- Entry: `llm_inference_manager/app.py` — MODEL_REGISTRY 11 models (line 26), rr_counters round-robin (198), spawned_processes (201), gpu_info parses nvidia-smi, pick_backend 293, proxy_chat 305-321
- DB: SQLite `manager.db` 5 tables `models, api_tokens, chat_sessions, messages, metrics` init_db 214
- Auth: `verify_token` Header Bearer `sk-local-dev`, allows anonymous local
- Startup: spawns gemma 5x via `gemma_supervisor.sh` 8080-8084 GPU split, qwen 8090, manager 9000

## Critical Fix
```python
# app.py:321
async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
```
Bypasses Squid proxy for localhost backends. Without => `ConnectError All attempts failed` via 192.168.203.2:3128.

## Endpoints (8)

| Method | Path | Auth | Request | Response | Code |
|--------|------|------|---------|----------|------|
| GET | /health | no | - | `{status, manager, version, gpus:[{index,used_mib,total_mib,free_mib,util}], models_loaded}` | `models_loaded=2` live |
| GET | /v1/models | no | - | `{object:list, data:[{id, object, owned_by, meta:{name,family,params,size_gb,quant,path,context,benchmark_mean,status,backends}}]}` 11 models | 200 |
| GET | /v1/models/{id} | no | - | single + gpus | 200 or 404 hint |
| POST | /v1/chat/completions | Bearer sk-local-dev (optional local) | `{model, messages:[{role,content}], max_tokens, temperature, session_id, stream:false}` | `{id:chatcmpl-local, object:chat.completion, model:gemma-4-31b-1, choices:[{message:{role,content}, finish_reason}]}` + `X-Manager-Latency-ms` | 200 round-robin |
| POST | /v1/completions | Bearer | `{model, prompt, max_tokens}` legacy => chat | same | 200 |
| GET | /admin/status | no | - | `{gpus, registry:{id:{status,backends,size_gb}}, spawned:[...]}` | 200 |
| POST | /admin/models/load?model_id= | no | `model_id=gemma-3-27b` | finds next port 8085..8100 via `find_next_port`, picks GPU lowest used_mib, spawns `llama_chat_server.py --port` | 200 |
| POST | /admin/models/unload?model_id= | no | `model_id` | pops `spawned_processes`, terminate | 200 |
| GET | /metrics | no | - | prometheus | 200 |

## MODEL_REGISTRY 11

| id | name | params | size_gb | quant | context | mean | status | backends |
|----|------|--------|---------|-------|---------|------|--------|----------|
| gemma-4-31b | Gemma-4 31B Instruct | 31B | 19.6 | Q4_K_M | 8192 | 0.663 | loaded | 8080,8081,8082,8083,8084 |
| gemma-3-27b | Gemma-3 27B | 27B | 16.5 | Q4_K_M | 8192 | 0.600 | available | - |
| qwen3.8-27b | Qwen3.8 27B | 27B | 17.8 | Q4_K_M | 8192 | 0.477 | available | - |
| qwen3-30b-a3b | Qwen3-30B-A3B MoE 3B active | 30B/3B | 18.6 | Q4_K_M | 8192 | 0.283 | available | `Qwen3-30B-A3B-Q4_K_M.gguf` fixed case 2026-08-23 |
| nemotron-49b | Nemotron-Super 49B v1 | 49B | 30.2 | Q4_K_M | 8192 | 0.494 | available | - |
| qwen2.5-7b | Qwen2.5 7B Instruct | 7B | 4.4 | Q4_K_M | 8192 | 0.42 | loading | 8090 |
| llama-3.2-3b | Llama 3.2 3B | 3B | 1.9 | Q4_K_M | 8192 | 0.326 | available | - |
| mistral-7b | Mistral 7B v0.3 | 7B | 4.1 | Q4_K_M | 8192 | 0.186 | available | - |
| phi-3-mini | Phi-3 Mini 4K | 3.8B | 2.4 | q4 | 4096 | 0.143 | available | - |
| deepseek-v4-flash | DeepSeek V4 Flash | 685B MoE | 148.7 | FP8 | 8192 | - | available needs vLLM | - |
| qwen2.5-72b | Qwen2.5 72B | 72B | 73 | Q4_K_M | 8192 | - | partial | - |

Paths: `offline-prep/models/huggingface/<repo_with_/_→_>/` e.g. `bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf`

## Live Verification 2026-08-23

```bash
curl -s http://127.0.0.1:9000/health | jq
# {status:ok, manager:llm_inference_manager, gpus:[{index:0,used_mib:88759,total:143771,free:55012}], models_loaded:2}

curl -s http://127.0.0.1:9000/v1/models | jq '.data[].id'
# 11 lines

curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":20}' | jq
# {model:gemma-4-31b-1, content:Hello} 200 X-Manager-Latency-ms

curl -s http://127.0.0.1:9000/v1/chat/completions -d '{"model":"qwen2.5-7b","messages":[{"role":"user","content":"salam"}]}' | jq
# {model:qwen2.5-7b, content:سلام} 200

curl -s "http://127.0.0.1:9000/admin/status" | jq
# registry + spawned
```

See `logs/manager_test_*.json` 3 runs, `docs/manager_openapi_curls.md` per-model curl table.

## Port & GPU Logic
- `find_next_port(start=8085)` scans 8085..8100 avoiding used backends (8080-8084,8090 taken => 8085 free)
- GPU pick: `gpu_info()` parses `nvidia-smi` free_mib => lowest used (gpu1 61G vs g0 88G => gpu1)
- `pick_backend(mid)` => `backs[n % len(backs)]` with `rr_counters[mid]+=1` round-robin 5 gemma

## Troubleshooting
- 404 `Model not loaded` => `POST /admin/models/load?model_id=gemma-3-27b`
- 500 ConnectError via proxy => ensure trust_env=False present line 321
- Port conflict host uvicorn 1032494 on 8080 => kill + supervisor restart (documented)

Evidence: `.opencode/docs/evidence_T1.4_T1.5_services.md` S1.5.4-5.5, `llm_inference_manager/app.py` 580L
