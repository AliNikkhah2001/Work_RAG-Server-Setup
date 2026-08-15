#!/usr/bin/env bash
set -euo pipefail

# Recreate webui-test pointed at the local OpenAI-compatible endpoints.
# The container is stateless (no volumes), so recreate is safe.
# LLM URL defaults to the llama.cpp server; pass 1 arg to use vLLM (:8000).
LLM_PORT="${1:-8080}"

docker rm -f webui-test >/dev/null 2>&1 || true

docker run -d \
  --name webui-test \
  --add-host host.docker.internal:host-gateway \
  -p 13000:8080 \
  -e WEBUI_AUTH=false \
  -e USE_OLLAMA_DOCKER=false \
  -e USE_CUDA_DOCKER=false \
  -e USE_EMBEDDING_MODEL_DOCKER=sentence-transformers/all-MiniLM-L6-v2 \
  -e RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
  -e SCARF_NO_ANALYTICS=true \
  -e DO_NOT_TRACK=true \
  -e OPENAI_API_BASE_URL="http://host.docker.internal:${LLM_PORT}/v1" \
  -e OPENAI_API_KEY=local \
  ghcr.io/open-webui/open-webui:main >/dev/null

sleep 12
curl -s -o /dev/null -w "open-webui HTTP %{http_code}\n" http://127.0.0.1:13000 || echo "not ready yet"
