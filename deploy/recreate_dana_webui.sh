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
  # Prefer CI-tagged :dana when present; :production is the pinned fallback.
  for cand in rag-webui:dana rag-webui:production rag-webui:working; do
    if docker image inspect "$cand" >/dev/null 2>&1; then IMAGE=$cand; break; fi
  done
fi
if [ -z "${IMAGE:-}" ]; then
  echo "ERROR: no rag-webui:dana|production|working image found" >&2
  exit 1
fi
echo "Using WebUI image: $IMAGE"

# Fast path: already running the requested image and healthy — skip rm/recreate
# (avoids a long durable-task wait that dies if Jenkins itself restarts mid-deploy).
if docker ps --format '{{.Names}}' | grep -qx dana-webui-prod; then
  cur=$(docker inspect -f '{{.Config.Image}}' dana-webui-prod 2>/dev/null || true)
  want_id=$(docker image inspect -f '{{.Id}}' "$IMAGE" 2>/dev/null || true)
  cur_id=$(docker inspect -f '{{.Image}}' dana-webui-prod 2>/dev/null || true)
  if [ -n "$want_id" ] && [ "$cur_id" = "$want_id" ]; then
    code=$(docker exec dana-webui-prod curl -sS --noproxy '*' --max-time 2 \
      -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/config 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then
      echo "WebUI already healthy on image $IMAGE (cur=$cur) — skip recreate"
      docker ps --filter name=dana-webui-prod --format '{{.Names}} {{.Status}} {{.Ports}}'
      exit 0
    fi
  fi
fi

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
  -e DANA_THEME_ID=ics-maroon \
  -e 'DEFAULT_INTERFACE_SETTINGS={"dana_theme_id":"ics-maroon","params":{"stream_response":true}}' \
  -e HTTP_PROXY= \
  -e HTTPS_PROXY= \
  -e http_proxy= \
  -e https_proxy= \
  -e NO_PROXY=localhost,127.0.0.1,host.docker.internal,172.17.0.0/16,192.168.0.0/16,10.0.0.0/8,.local \
  -e no_proxy=localhost,127.0.0.1,host.docker.internal,172.17.0.0/16,192.168.0.0/16,10.0.0.0/8,.local \
  "$IMAGE"

# Health probe must work from host AND from dana-jenkins-prod (no host
# loopback). Prefer docker exec into the container; fall back to LAN binds.
webui_http_code() {
  local code
  code=$(docker exec dana-webui-prod curl -sS --noproxy '*' --max-time 2 \
    -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/config 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then echo 200; return 0; fi
  for url in \
    ${DANA_WEBUI_PROBE_URL:-} \
    http://127.0.0.1:13000/api/config \
    http://192.168.96.82:13000/api/config \
    http://192.168.177.10:13000/api/config; do
    [ -n "$url" ] || continue
    code=$(curl -sS --noproxy '*' --max-time 2 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then echo 200; return 0; fi
  done
  echo 000
  return 1
}

webui_get() {
  # stdout = body; prefer in-container fetch (Jenkins-safe)
  local path="$1"
  if docker exec dana-webui-prod curl -sS --noproxy '*' --max-time 3 \
      "http://127.0.0.1:8080${path}" 2>/dev/null; then
    return 0
  fi
  for base in \
    ${DANA_WEBUI_PROBE_BASE:-} \
    http://127.0.0.1:13000 \
    http://192.168.96.82:13000 \
    http://192.168.177.10:13000; do
    [ -n "$base" ] || continue
    if curl -sS --noproxy '*' --max-time 3 "${base}${path}" 2>/dev/null; then
      return 0
    fi
  done
  return 1
}

echo "Waiting for WebUI..."
ready=0
for i in $(seq 1 40); do
  if [ "$(webui_http_code)" = "200" ]; then ready=1; break; fi
  sleep 2
done
if [ "$ready" != "1" ]; then
  echo "ERROR: WebUI did not become healthy on :13000 / in-container :8080" >&2
  docker ps --filter name=dana-webui-prod --format '{{.Names}} {{.Status}} {{.Ports}}' >&2 || true
  docker logs --tail 40 dana-webui-prod >&2 || true
  exit 1
fi

# Until the next [ci prod] WebUI image lands, force white (ics-maroon) defaults
# on the pinned production image (still ships ics-mono as the baked default).
docker exec dana-webui-prod python3 -c '
from pathlib import Path
import json
for p in Path("/app").rglob("dana/themes/index.json"):
    data = json.loads(p.read_text())
    data["default"] = "ics-maroon"
    themes = [t for t in (data.get("themes") or []) if t != "ics-maroon"]
    themes.insert(0, "ics-maroon")
    data["themes"] = themes
    p.write_text(json.dumps(data, indent=2) + "\n")
chunk = Path("/app/build/_app/immutable/chunks/dpZ0QVlb.js")
if chunk.exists():
    t = chunk.read_text()
    t = t.replace(",i=\"ics-mono\",", ",i=\"ics-maroon\",", 1)
    t = t.replace("y=\"6-force-ics-mono\"", "y=\"7-force-ics-maroon\"", 1)
    chunk.write_text(t)
print("dana theme default -> ics-maroon")
' || echo "WARN: could not patch theme defaults in container" >&2

docker ps --filter name=dana-webui-prod --format '{{.Names}} {{.Status}} {{.Ports}}'
webui_get /api/config | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name'), d.get('ui',{}).get('default_interface_settings'))"
webui_get /static/dana/themes/index.json || true
echo
docker exec dana-webui-prod printenv DANA_THEME_ID DEFAULT_INTERFACE_SETTINGS
