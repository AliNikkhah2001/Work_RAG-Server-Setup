#!/usr/bin/env bash
set -euo pipefail
# Hourly self-reporting daemon: download progress + Triton status -> README + git push to main
ROOT="/splunk-data/v1/Work_RAG-Server-Setup"
LOG="$ROOT/logs/triton_progress.log"
mkdir -p "$ROOT/logs"

# ensure git config
cd "$ROOT"
if ! git config user.email >/dev/null 2>&1; then
  git config user.email "triton-daemon@ai-gpu1.local"
  git config user.name "triton-daemon"
fi

# helper: size of HF dir (GB)
hf_size() {
  local dir="$1"
  if [ -d "$dir" ]; then du -sh "$dir" 2>/dev/null | cut -f1; else echo "0"; fi
}

# helper: triton health
triton_health() {
  curl -s http://127.0.0.1:8104/health 2>&1 | head -c 200 || echo "down"
  echo -n " | triton 8004: "
  curl -s http://127.0.0.1:8004/v2/health/ready 2>&1 | head -c 80 || echo "down"
}

while true; do
  TS=$(date -Is)
  echo "[$TS] hourly report start" | tee -a "$LOG"

  # 1. gather sizes
  GGUF_SIZE=$(du -sh offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF 2>/dev/null | cut -f1 || echo "0")
  HF_GEMMA4=$(hf_size "$ROOT/offline-prep/models/huggingface/google_gemma-4-31b-it")
  HF_GEMMA3=$(hf_size "$ROOT/offline-prep/models/huggingface/google_gemma-3-27b-it")
  ENGINE_SIZE=$(hf_size "$ROOT/offline-prep/models/trt_engines/gemma-4-31b_fp8")
  BENCH=$(ls -t logs/bench_compare*.json 2>/dev/null | head -n1 || echo "none")
  MANAGER_HEALTH=$(curl -s http://127.0.0.1:9000/health 2>&1 | head -c 300 || echo "manager down")
  VLLM_HEALTH=$(curl -s http://127.0.0.1:8104/v1/models 2>&1 | head -c 300 || echo "vllm down")
  TRITON_HEALTH=$(triton_health 2>&1 | head -c 400)

  # 2. write status file for dashboard
  cat > "$ROOT/logs/triton_hourly_status.json" <<JSONEOF
{
  "ts": "$TS",
  "gguf": "$GGUF_SIZE",
  "hf_gemma4": "$HF_GEMMA4",
  "hf_gemma3": "$HF_GEMMA3",
  "engine": "$ENGINE_SIZE",
  "bench": "$BENCH",
  "manager": $(echo "$MANAGER_HEALTH" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()[:400]))"),
  "vllm": $(echo "$VLLM_HEALTH" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()[:400]))"),
  "triton": $(echo "$TRITON_HEALTH" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()[:400]))")
}
JSONEOF

  # 3. patch README.md Triton section (idempotent)
  MARKER="<!-- TRITON-HOURLY-STATUS -->"
  STATUS_LINE="> **Triton hourly $TS** — GGUF $GGUF_SIZE | HF gemma-4 $HF_GEMMA4 | HF gemma-3 $HF_GEMMA3 | Engine $ENGINE_SIZE | Manager $MANAGER_HEALTH | VLLM $VLLM_HEALTH | Triton $TRITON_HEALTH | Bench $BENCH"
  if grep -q "$MARKER" "$ROOT/README.md" 2>/dev/null; then
    # replace line after marker
    awk -v line="$STATUS_LINE" -v m="$MARKER" 'index($0,m){print; print line; skip=1; next} skip && /^> \*\*Triton hourly/{next} {print}' "$ROOT/README.md" > /tmp/readme.tmp && mv /tmp/readme.tmp "$ROOT/README.md"
  else
    echo -e "\n$MARKER\n$STATUS_LINE\n" >> "$ROOT/README.md"
  fi

  # 4. git commit + push to main (rebase-safe, stashes dirty working tree)
  cd "$ROOT"
  # preserve dirty working tree (e.g. monitoring compose) across rebase - keep untracked logs out of stash
  DIRTY=0
  if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    DIRTY=1
    git stash push -m "daemon-stash $TS" 2>&1 | tee -a "$LOG" || true
  fi
  git fetch origin main 2>&1 | tee -a "$LOG" || true
  git add README.md logs/triton_hourly_status.json logs/bench_compare*.json 2>/dev/null || true
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "triton hourly $TS GGUF=$GGUF_SIZE HF4=$HF_GEMMA4 engine=$ENGINE_SIZE [auto]" 2>&1 | tee -a "$LOG" || true
  fi
  timeout 60 git pull --rebase origin main 2>&1 | tee -a "$LOG" || echo "[$TS] rebase failed, will retry" | tee -a "$LOG"
  timeout 60 git push origin main 2>&1 | tee -a "$LOG" || echo "[$TS] push failed (proxy), will retry next hour" | tee -a "$LOG"
  if [ "$DIRTY" = "1" ]; then
    git stash pop 2>&1 | tee -a "$LOG" || true
  fi
  if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
    echo "[$TS] no changes to push" | tee -a "$LOG"
  fi

  echo "[$TS] hourly report done" | tee -a "$LOG"
  sleep 3600
done
