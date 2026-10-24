#!/usr/bin/env bash
# Public Manager launcher — exposes :9000 directly + via nginx :8088/manager/
# Uses PUBLIC_DASHBOARD=1 so / and /dashboard require ?token= or Authorization.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/offline-prep/venv/bin/python"
if [ ! -x "$VENV" ]; then VENV="$ROOT/offline-prep/venv/bin/python3.12"; fi
if [ ! -x "$VENV" ]; then VENV="python3"; fi
export PUBLIC_DASHBOARD="${PUBLIC_DASHBOARD:-1}"
export PUBLIC_REQUIRE_AUTH="${PUBLIC_REQUIRE_AUTH:-0}"
export PUBLIC_CORS_ORIGINS="${PUBLIC_CORS_ORIGINS:-*}"
# Load litellm master key if exists (single key for all panels)
if [ -f "$ROOT/litellm.env" ]; then set -a; source "$ROOT/litellm.env"; set +a; fi
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-litellm-local-dev-change-me}"
export LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:4000}"
# Panel upstreams (local)
export PANEL_KB_URL="${PANEL_KB_URL:-http://127.0.0.1:8000}"
export PANEL_GUARD_URL="${PANEL_GUARD_URL:-http://127.0.0.1:8200}"
export PANEL_TRACE_URL="${PANEL_TRACE_URL:-http://127.0.0.1:3000}"
export HTTP_PROXY="${HTTP_PROXY:-http://192.168.203.2:3128}"
export HTTPS_PROXY="${HTTPS_PROXY:-http://192.168.203.2:3128}"
export NO_PROXY="localhost,127.0.0.1,host.docker.internal,192.168.96.82,192.168.177.10,192.168.96.0/29,192.168.177.0/29"
export no_proxy="$NO_PROXY"
echo "[manager-public] PUBLIC_DASHBOARD=$PUBLIC_DASHBOARD PUBLIC_REQUIRE_AUTH=$PUBLIC_REQUIRE_AUTH LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY:0:8}... "
echo "[manager-public] Starting on 0.0.0.0:9000 (public via 192.168.96.82:9000 and 192.168.96.82:8088/manager/)"
exec "$VENV" -m uvicorn llm_inference_manager.app:app --host 0.0.0.0 --port 9000 --app-dir "$ROOT"
