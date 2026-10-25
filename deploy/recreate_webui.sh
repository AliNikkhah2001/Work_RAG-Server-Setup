#!/usr/bin/env bash
set -euo pipefail

# Recreate webui-test pointed at the local OpenAI-compatible endpoints.
# IMPORTANT: mounts the named volume `webui-test` at /app/backend/data so
# users, chats, settings, uploads and the vector DB are PRESERVED across
# recreates. Auth is enabled: username/password login only (no signup).
# LLM URL defaults to the Orchestrator agent (:8100); pass 8080 for llama.cpp, 8000 for vLLM.
LLM_PORT="${1:-8100}"

# Stable session/API-key secret: keeps logins valid across recreates.
# Stored outside git, root-only readable.
SECRET_ENV=/root/.config/rag/webui.env
if [ ! -s "$SECRET_ENV" ]; then
  mkdir -p /root/.config/rag && chmod 700 /root/.config/rag
  head -c 32 /dev/urandom | base64 | tr -d '\n=' > /root/.config/rag/webui_secret_key
  chmod 600 /root/.config/rag/webui_secret_key
  printf 'WEBUI_SECRET_KEY=%s\n' "$(cat /root/.config/rag/webui_secret_key)" > "$SECRET_ENV"
  chmod 600 "$SECRET_ENV"
fi

docker rm -f webui-test >/dev/null 2>&1 || true

docker run -d \
  --restart unless-stopped \
  --name webui-test \
  --add-host host.docker.internal:host-gateway \
  -p 13000:8080 \
  -v webui-test:/app/backend/data \
  --env-file /root/.config/rag/webui.env \
  -e WEBUI_AUTH=true \
  -e ENABLE_SIGNUP=true \
  -e DEFAULT_USER_ROLE=user \
  -e USE_OLLAMA_DOCKER=false \
  -e USE_CUDA_DOCKER=false \
  -e USE_EMBEDDING_MODEL_DOCKER=sentence-transformers/all-MiniLM-L6-v2 \
  -e RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
  -e SCARF_NO_ANALYTICS=true \
  -e DO_NOT_TRACK=true \
  -e FORWARDED_ALLOW_IPS="*" \
  -e ENABLE_FORWARDED_ALLOW_IPS=true \
  -e OPENAI_API_BASE_URL="http://host.docker.internal:${LLM_PORT}/v1" \
  -e OPENAI_API_KEY=local \
  ghcr.io/open-webui/open-webui:main >/dev/null

sleep 12
curl -s -o /dev/null -w "open-webui HTTP %{http_code}\n" http://127.0.0.1:13000 || echo "not ready yet"
