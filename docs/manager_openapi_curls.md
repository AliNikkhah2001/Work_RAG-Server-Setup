# Manager OpenAPI Curls — verified 2026-08-23

Base: `http://127.0.0.1:9000` (local) or `http://192.168.96.82:9000` (from Docker) or `http://host.docker.internal:9000` (inside container). Auth: `Authorization: Bearer sk-local-dev` (or anonymous for local dev).

## Health & Models
```bash
curl -s http://127.0.0.1:9000/health | jq
curl -s http://127.0.0.1:9000/v1/models | jq '.data[].id'
curl -s http://127.0.0.1:9000/v1/models/gemma-4-31b | jq
curl -s http://127.0.0.1:9000/admin/status | jq
```

## Chat
```bash
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"say hello one word"}],"max_tokens":10}' | jq
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","messages":[{"role":"user","content":"salam be farsi"}],"max_tokens":20}' | jq
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"Explain RAG in one sentence"}],"max_tokens":50}' | jq
# With session memory
SID="test-$(date +%s)"
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d "{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"my name is Ali\"}],\"max_tokens\":20,\"session_id\":\"$SID\"}" | jq
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" \
  -d "{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"what is my name?\"}],\"max_tokens\":20,\"session_id\":\"$SID\"}" | jq
```

## Embeddings (via separate ports, not manager)
```bash
curl -s http://127.0.0.1:8001/health | jq  # dim 384
curl -s http://127.0.0.1:8001/v1/embeddings -H "Content-Type: application/json" -d '{"input":"hello"}' | jq
```
