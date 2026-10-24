# Fix: Make real client IP visible behind WAF/VAF (X-Forwarded-For)

**Date:** 2026-10-12
**Host:** ai-gpu1 (192.168.96.82) / 192.168.177.10
**Issue:** Chatbot (Open WebUI :13000) was `0.0.0.0:13000->8080` - public via VAF/WAF but backend only saw WAF internal IP (192.168.50.x, 192.168.53.x). Security team asked to enable `X-Forwarded-For` on Apache.

## What was done on this host (already applied)

### 1. Nginx gateway (`/etc/nginx/sites-available/rag-gateway:1`, symlink `/etc/nginx/sites-enabled/rag-gateway`)
Added to every `location /webui/, /vllm/, /llama/, /embeddings/, /grafana/, /prometheus/, /qdrant/`:
```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Real-IP $remote_addr;  # already existed
```
Same fixed in `/etc/nginx/sites-enabled/rag-public` (127.0.0.1:8089 Cloudflare tunnel).

Verified: `nginx -t` ok, `kill -HUP 3055289` reloaded. Test:
```bash
curl -H "X-Forwarded-For: 203.0.113.45" http://127.0.0.1:8088/webui/ -o /dev/null
tail /splunk-data/v1/Work_RAG-Server-Setup/deploy/gateway/logs/access.log
# now shows: "203.0.113.45 - 127.0.0.1 ..." instead of "127.0.0.1 ..."
```

### 2. Nginx access log (`/etc/nginx/nginx.conf:40`)
Changed from default `combined` to:
```nginx
log_format  main_ext  '$http_x_forwarded_for - $remote_addr - $remote_user [$time_local] '
                      '"$request" $status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';
access_log /splunk-data/v1/Work_RAG-Server-Setup/deploy/gateway/logs/access.log main_ext;
```
Now first field is real client IP (from WAF), second is WAF IP.

### 3. Open WebUI (`webui-test` container, `deploy/docker-compose.yml:33`, `deploy/recreate_webui.sh:14`)
- Changed port publish from `0.0.0.0:13000->8080` to `127.0.0.1:13000->8080` (no longer directly public)
- Added `FORWARDED_ALLOW_IPS="*"` + `ENABLE_FORWARDED_ALLOW_IPS=true` so uvicorn trusts `X-Forwarded-For`

Verified:
```bash
ss -tlnp | grep 13000  # now 127.0.0.1:13000 only
docker inspect webui-test --format '{{json .HostConfig.PortBindings}}' # 127.0.0.1
curl -H "X-Forwarded-For: 203.0.113.99" http://127.0.0.1:8088/webui/ ; docker logs webui-test | tail
# logs now: "203.0.113.99:0 - GET / HTTP/1.1 200" instead of "127.0.0.1:0"
curl http://192.168.96.82:13000/  # now fails (000) - expected, must use Nginx
curl --noproxy "*" http://192.168.96.82:8088/webui/ # 200 via Nginx
```

Same fixed in `deploy/docker-compose.vast.yml` and `Work_Credit-RAG_Phase1/deploy/docker/docker-compose.yml:311` for next deploys. Removed stale `rag-webui` :13002.

## What the WAF/VAF team (Apache) must do

If the public WAF is Apache `mod_proxy` (your "VAF"):

```apache
# Enable mod_remoteip (Debian: a2enmod remoteip headers)
RemoteIPHeader X-Forwarded-For
RemoteIPTrustedProxy 192.168.50.0/24 192.168.53.0/24 192.168.96.82
# optional: also trust WAF self
RemoteIPInternalProxy 127.0.0.1

# Preserve Host and protocol
ProxyPreserveHost On
RequestHeader set X-Forwarded-Proto "https" env=HTTPS
RequestHeader set X-Forwarded-Proto "http" env=!HTTPS
# mod_proxy already appends X-Forwarded-For if ProxyAddHeaders On

# Log real IP not proxy IP
LogFormat "%a %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined_real
CustomLog ${APACHE_LOG_DIR}/access.log combined_real
```

**Important:** Change WAF upstream from `http://192.168.96.82:13000/` to `http://192.168.96.82:8088/webui/` (Nginx gateway). If WAF must hit 13000 directly, change this host's publish back to `192.168.96.82:13000:8080` (LAN-only) instead of `127.0.0.1`.

Test from outside:
```bash
# from public internet via WAF
curl -I https://<public-waf-host>/webui/
# on this host check:
tail /splunk-data/v1/Work_RAG-Server-Setup/deploy/gateway/logs/access.log  # first field = your public IP
docker logs webui-test | tail  # same public IP
```

## Security hardening still recommended
- Keep `WEBUI_AUTH=false` only if WAF does auth; otherwise set `true` in `deploy/docker-compose.yml:37`
- WAF should rate-limit and filter `X-Forwarded-For` spoofing (only trust `RemoteIPTrustedProxy`)
- Do not re-expose 13000 to 0.0.0.0; keep Nginx as single entry (8088)

