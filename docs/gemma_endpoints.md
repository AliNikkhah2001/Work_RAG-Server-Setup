# Gemma 4 31B — 5 Local Instances (OpenAI Compatible)

**Model:** `bartowski/google_gemma-4-31B-it-GGUF` Q4_K_M (19G) — 5 instances, 2× H200 (75G GPU0 / 46G GPU1), n_ctx 4096, auto-reviving supervisor.

| # | Model ID | Port | GPU | Base URL | Reasoning |
|---|----------|------|-----|----------|-----------|
| 1 | `gemma-4-31b-1` | 8080 | 0 | http://localhost:8080/v1 | high |
| 2 | `gemma-4-31b-2` | 8081 | 1 | http://localhost:8081/v1 | high |
| 3 | `gemma-4-31b-3` | 8082 | 0 | http://localhost:8082/v1 | high |
| 4 | `gemma-4-31b-4` | 8083 | 1 | http://localhost:8083/v1 | high |
| 5 | `gemma-4-31b-5` | 8084 | 0 | http://localhost:8084/v1 | high |

**Opencode config:** `~/.config/opencode/opencode.jsonc` → provider `gemma-4-31b-local` with `reasoningEffort: high` for all 5.

**Endpoints (OpenAI format):**
- `GET http://localhost:8080/v1/models` → `{"data":[{"id":"gemma-4-31b-1"}]}`
- `GET http://localhost:8080/health` → `{"status":"ok"}`
- `POST http://localhost:8080/v1/chat/completions` with `{"model":"gemma-4-31b-1","messages":[{"role":"user","content":"..."}],"max_tokens":256,"temperature":0.2}`

**Curl test (Farsi, as verified 11:32 UTC):**
```bash
curl -s http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b-1","messages":[{"role":"user","content":"Say hello in Farsi"}],"max_tokens":32,"temperature":0.2}' | jq .
# → {"choices":[{"message":{"content":"سلام ... Salām"}}]}

# All 5 health
for p in 8080 8081 8082 8083 8084; do curl -s http://localhost:$p/health; echo; done
```

**Supervisor:** `scripts/services/gemma_supervisor.sh` — infinite loop per port, `env CUDA_VISIBLE_DEVICES=$gpu` (staggered start, auto-restart on crash). Logs: `logs/llama_server_808*.log`, `logs/gemma_supervisor.log`.

**Start manually:**
```bash
for i in 1 2 3 4 5; do port=$((8079+i)); gpu=$(( (i-1)%2 )); nohup env CUDA_VISIBLE_DEVICES=$gpu offline-prep/venv/bin/python3.12 scripts/services/llama_chat_server.py --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf --port $port --model-id gemma-4-31b-$i --n-ctx 4096 > logs/llama_server_${port}.log 2>&1 & sleep 15; done
```
