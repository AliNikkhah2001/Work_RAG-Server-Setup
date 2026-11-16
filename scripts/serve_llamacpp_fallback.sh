#!/usr/bin/env bash
# GPU0 llama.cpp Q4 fallback for Gemma-4-31B (stable secondary behind TRT :8010).
#
# Why llama.cpp (not a second TRT):
#   - Idle GPU0 has ~140GiB free; Q4 GGUF ~20GiB loads reliably
#   - No TensorRT rebuild / FlashInfer / CUDA-toolkit coupling
#   - n_ctx=16384 covers prompts that overflow TRT max_seq_len=8192
#   - Manager fails over here on TRT 400/timeout (context overflow, not classic OOM)
#
# Usage:
#   bash scripts/serve_llamacpp_fallback.sh
#   bash scripts/serve_llamacpp_fallback.sh --fg          # foreground
#   CUDA_VISIBLE_DEVICES=0 PORT=8080 N_CTX=16384 bash scripts/serve_llamacpp_fallback.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Prefer production umbrella clone offline-prep; fall back to legacy v1 tree.
CANDIDATE_BASES=(
  "${LLAMA_BASE:-}"
  "/splunk-data/v1/Work_RAG-Server-Setup"
  "/splunk-data/v1/Work_RAG-Server-Setup.__DEPRECATED_DO_NOT_USE_FOR_WEBUI__"
  "$ROOT"
)
BASE=""
for b in "${CANDIDATE_BASES[@]}"; do
  [ -n "$b" ] || continue
  if [ -f "$b/offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf" ]; then
    BASE="$b"
    break
  fi
done
if [ -z "$BASE" ]; then
  echo "serve_llamacpp_fallback: GGUF not found under known bases" >&2
  exit 1
fi

MODEL="${MODEL:-$BASE/offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf}"
PY="${PY:-$BASE/offline-prep/venv/bin/python3.12}"
[ -x "$PY" ] || PY="$BASE/offline-prep/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
SVC="${SVC:-$ROOT/scripts/services/llama_chat_server.py}"
# Prefer this repo's server; sync copy under BASE if missing features.
if [ ! -f "$SVC" ]; then
  SVC="$BASE/scripts/services/llama_chat_server.py"
fi

PORT="${PORT:-8080}"
N_CTX="${N_CTX:-16384}"
GPU="${CUDA_VISIBLE_DEVICES:-0}"
LOGDIR="${LOGDIR:-$BASE/logs}"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/llamacpp_fallback_${PORT}.log"
PIDFILE="$LOGDIR/llamacpp_fallback_${PORT}.pid"

FG=0
for a in "$@"; do
  case "$a" in
    --fg|--foreground) FG=1 ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
  esac
done

if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "serve_llamacpp_fallback: already healthy on :${PORT}"
  curl -sS "http://127.0.0.1:${PORT}/health"; echo
  exit 0
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "serve_llamacpp_fallback: pid $(cat "$PIDFILE") still running but /health failed — check $LOG" >&2
  exit 1
fi

echo "serve_llamacpp_fallback: GPU=$GPU port=$PORT n_ctx=$N_CTX model=$MODEL"
echo "serve_llamacpp_fallback: log=$LOG"

export CUDA_VISIBLE_DEVICES="$GPU"
CMD=( "$PY" "$SVC" --model "$MODEL" --port "$PORT" --n-ctx "$N_CTX" --model-id gemma-4-31b --n-gpu-layers -1 )

if [ "$FG" = "1" ]; then
  exec "${CMD[@]}"
fi

nohup "${CMD[@]}" >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "serve_llamacpp_fallback: started pid=$(cat "$PIDFILE")"

# Wait up to ~3 minutes for load
for i in $(seq 1 60); do
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "serve_llamacpp_fallback: healthy"
    curl -sS "http://127.0.0.1:${PORT}/health"; echo
    exit 0
  fi
  sleep 3
done
echo "serve_llamacpp_fallback: timeout waiting for /health — see $LOG" >&2
tail -40 "$LOG" >&2 || true
exit 1
