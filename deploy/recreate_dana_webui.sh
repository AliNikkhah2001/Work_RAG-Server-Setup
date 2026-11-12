#!/usr/bin/env bash
set -euo pipefail

# Recreate production Dana WebUI on :13000.
# Prefers pinned tags from deploy/PRODUCTION.md:
#   rag-webui:production  (sha256:4e76b1243fabb207a25937387a43c0999cb9e00b99b0a4508092f5471c44b40e)
# falls back to rag-webui:dana / rag-webui:working.
# ALWAYS uses volume `dana-webui-data` — never the deprecated v1 `webui-test`
# volume (that mix of old Open WebUI DB + Dana image caused the hybrid UI).
#
# Binds: 127.0.0.1 (nginx) + LAN IPs WAF uses.
# Image must already exist: bash components/webui/scripts/dana-local-image.sh
IMAGE="${DANA_WEBUI_IMAGE:-}"
if [ -z "$IMAGE" ]; then
  for cand in rag-webui:production rag-webui:working rag-webui:dana; do
    if docker image inspect "$cand" >/dev/null 2>&1; then IMAGE=$cand; break; fi
  done
fi
if [ -z "${IMAGE:-}" ]; then
  echo "ERROR: no rag-webui:production|working|dana image found" >&2
  exit 1
fi
echo "Using WebUI image: $IMAGE"

SECRET_ENV=/root/.config/rag/webui.env
if [ ! -s "$SECRET_ENV" ]; then
  mkdir -p /root/.config/rag && chmod 700 /root/.config/rag
  head -c 32 /dev/urandom | base64 | tr -d '\n=' > /root/.config/rag/webui_secret_key
  chmod 600 /root/.config/rag/webui_secret_key
  printf 'WEBUI_SECRET_KEY=%s\n' "$(cat /root/.config/rag/webui_secret_key)" > "$SECRET_ENV"
  chmod 600 "$SECRET_ENV"
fi

docker volume create dana-webui-data >/dev/null
docker rm -f dana-webui-prod >/dev/null 2>&1 || true

docker run -d --name dana-webui-prod --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -p 127.0.0.1:13000:8080 \
  -p 192.168.96.82:13000:8080 \
  -p 192.168.177.10:13000:8080 \
  -v dana-webui-data:/app/backend/data \
  --env-file "$SECRET_ENV" \
  -e WEBUI_AUTH=false \
  -e WEBUI_NAME=دانا \
  -e USE_OLLAMA_DOCKER=false \
  -e FORWARDED_ALLOW_IPS='*' \
  -e ENABLE_FORWARDED_ALLOW_IPS=true \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:8100/v1 \
  -e OPENAI_API_KEY=sk-local-dev \
  -e ENABLE_OPENAI_API=true \
  -e DANA_THEME_ID=ics-mono \
  -e 'DEFAULT_INTERFACE_SETTINGS={"dana_theme_id":"ics-mono","params":{"stream_response":true}}' \
  -e HTTP_PROXY= \
  -e HTTPS_PROXY= \
  -e http_proxy= \
  -e https_proxy= \
  -e NO_PROXY=localhost,127.0.0.1,host.docker.internal,172.17.0.0/16,192.168.0.0/16,10.0.0.0/8,.local \
  -e no_proxy=localhost,127.0.0.1,host.docker.internal,172.17.0.0/16,192.168.0.0/16,10.0.0.0/8,.local \
  "$IMAGE"

echo "Waiting for WebUI..."
for i in $(seq 1 40); do
  code=$(curl -sS --noproxy '*' --max-time 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:13000/api/config || echo 000)
  [ "$code" = "200" ] && break
  sleep 2
done
docker ps --filter name=dana-webui-prod --format '{{.Names}} {{.Status}} {{.Ports}}'
curl -sS --noproxy '*' --max-time 3 http://127.0.0.1:13000/api/config | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name'), d.get('ui',{}).get('default_interface_settings'))"
