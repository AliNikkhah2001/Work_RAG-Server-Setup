#!/usr/bin/env bash
# =============================================================================
# gpu_spof_recover_report.sh — Single Point of Failure recovery + evidence pack
# =============================================================================
# Run ON the GPU / production host when you regain access. One script that:
#   1) Discovers host layout (compose vs Vast host-venv)
#   2) Brings app (+ best-effort model) services back up
#   3) Moves to latest healthy build (origin/main or .last_good_sha)
#   4) Dumps ingest / job history from Postgres
#   5) Collects docker + /tmp + journal logs; extracts DOWN/ERROR signatures
#   6) Curl health matrix + E2E chat QA
#   7) Headless screenshots of WebUI / health pages (if Chromium available)
#   8) Writes a self-contained report dir and pushes it to Work_RAG-Server-Setup
#
# Usage:
#   bash components/server-setup/scripts/gpu_spof_recover_report.sh
#   bash components/server-setup/scripts/gpu_spof_recover_report.sh --no-push
#   bash components/server-setup/scripts/gpu_spof_recover_report.sh --no-restart
#   DANA_HOST_REPO=/path/to/umbrella bash .../gpu_spof_recover_report.sh
#
# Never commits secrets (.env, tokens). Log redaction is applied before push.
# =============================================================================
set -uo pipefail

UMBRELLA="${DANA_HOST_REPO:-}"
if [[ -z "$UMBRELLA" ]]; then
  # script lives in components/server-setup/scripts/ → umbrella is ../../..
  UMBRELLA="$(cd "$(dirname "$0")/../../.." && pwd)"
fi
SS_REPO="${SERVER_SETUP_REPO:-$UMBRELLA/components/server-setup}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(hostname -s 2>/dev/null || echo host)"
OUT="${SPOF_OUT:-$SS_REPO/docs/ops/gpu-spof-reports/$RUN_ID}"
NO_PUSH=0
NO_RESTART=0
NO_SCREENSHOT=0
SKIP_KEEP_LATEST=0

for arg in "$@"; do
  case "$arg" in
    --no-push) NO_PUSH=1 ;;
    --no-restart) NO_RESTART=1 ;;
    --no-screenshot) NO_SCREENSHOT=1 ;;
    --skip-keep-latest) SKIP_KEEP_LATEST=1 ;;
    -h|--help) sed -n '1,35p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT"/{logs,ingest,curl,e2e,screenshots,meta,redacted}
LOG="$OUT/run.log"
exec > >(tee -a "$LOG") 2>&1

section() { printf '\n======== %s ========\n' "$*"; }
ok()   { printf '[OK]   %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

section "0. meta"
date -u +"utc=%Y-%m-%dT%H:%M:%SZ"
echo "hostname=$(hostname -f 2>/dev/null || hostname)"
echo "umbrella=$UMBRELLA"
echo "server_setup=$SS_REPO"
echo "out=$OUT"
uname -a | tee "$OUT/meta/uname.txt"
{ have nvidia-smi && nvidia-smi || echo "nvidia-smi missing"; } | tee "$OUT/meta/nvidia-smi.txt"
{ have docker && docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' || echo "docker missing"; } | tee "$OUT/meta/docker-ps.txt"
df -h | tee "$OUT/meta/df.txt"
free -h 2>/dev/null | tee "$OUT/meta/free.txt" || true
{
  echo "git_umbrella=$(git -C "$UMBRELLA" rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "git_ss=$(git -C "$SS_REPO" rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "last_good=$(cat "$UMBRELLA/deploy/compose/.last_good_sha" 2>/dev/null || echo none)"
  echo "deployed=$(cat "$UMBRELLA/deploy/compose/.deployed_sha" 2>/dev/null || echo none)"
} | tee "$OUT/meta/git.txt"

# Detect stack mode
MODE=unknown
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE 'dana-prod|rag-'; then
  MODE=compose
elif [[ -f /tmp/kb.log ]] || [[ -x /tmp/kb-venv/bin/python ]]; then
  MODE=host_venv
elif [[ -f "$UMBRELLA/deploy/compose/compose.gpu.yml" ]]; then
  MODE=compose
fi
echo "detected_mode=$MODE" | tee -a "$OUT/meta/git.txt"

# -----------------------------------------------------------------------------
section "1. bring services up (best effort)"
if [[ "$NO_RESTART" == "1" ]]; then
  warn "skipping restart (--no-restart)"
else
  if [[ "$MODE" == "compose" || -f "$UMBRELLA/deploy/compose/compose.gpu.yml" ]]; then
    ENVF="$UMBRELLA/deploy/compose/.env.prod"
    [[ -f "$ENVF" ]] || ENVF="$UMBRELLA/deploy/compose/.env"
    if [[ -f "$ENVF" ]]; then
      ok "compose up dana-prod with $ENVF"
      docker compose -p dana-prod \
        -f "$UMBRELLA/deploy/compose/compose.base.yml" \
        -f "$UMBRELLA/deploy/compose/compose.gpu.yml" \
        --env-file "$ENVF" \
        up -d 2>&1 | tee "$OUT/meta/compose-up.txt" || warn "compose up returned non-zero"
    else
      warn "no .env.prod/.env — cannot compose up apps"
    fi
    # Jenkins prod controller (optional)
    if [[ -f "$UMBRELLA/deploy/jenkins/docker-compose.gpu.yml" ]]; then
      docker compose -f "$UMBRELLA/deploy/jenkins/docker-compose.yml" \
        -f "$UMBRELLA/deploy/jenkins/docker-compose.gpu.yml" \
        up -d 2>&1 | tee -a "$OUT/meta/compose-up.txt" || true
    fi
  fi
  # Manager if present
  if have curl; then
    if ! curl -sf --max-time 3 http://127.0.0.1:9000/health >/dev/null; then
      if [[ -x "$SS_REPO/scripts/start_manager_public.sh" ]]; then
        warn "manager :9000 down — trying start_manager_public.sh"
        bash "$SS_REPO/scripts/start_manager_public.sh" 2>&1 | tee "$OUT/meta/manager-start.txt" || true
      fi
    fi
  fi
fi

# -----------------------------------------------------------------------------
section "2. latest working build"
if [[ "$SKIP_KEEP_LATEST" == "1" ]]; then
  warn "skip keep-latest"
elif [[ -x "$UMBRELLA/scripts/gpu_keep_latest.sh" ]]; then
  ok "running gpu_keep_latest.sh"
  DANA_HOST_REPO="$UMBRELLA" DANA_HOST=gpu DANA_ROLE=prod \
    bash "$UMBRELLA/scripts/gpu_keep_latest.sh" 2>&1 | tee "$OUT/meta/keep-latest.txt" || warn "keep-latest non-zero"
elif [[ -x "$UMBRELLA/scripts/ci_rollback.sh" && -f "$UMBRELLA/deploy/compose/.last_good_sha" ]]; then
  ok "no keep-latest — ensuring last_good is checked out"
  SHA="$(tr -d '[:space:]' <"$UMBRELLA/deploy/compose/.last_good_sha")"
  echo "last_good=$SHA" | tee -a "$OUT/meta/keep-latest.txt"
  git -C "$UMBRELLA" fetch origin main 2>&1 | tee -a "$OUT/meta/keep-latest.txt" || true
else
  warn "no keep-latest / last_good tooling found"
fi
{
  echo "HEAD=$(git -C "$UMBRELLA" rev-parse HEAD 2>/dev/null || echo n/a)"
  git -C "$UMBRELLA" log -1 --oneline 2>/dev/null || true
  git -C "$UMBRELLA" submodule status 2>/dev/null | head -20 || true
} | tee "$OUT/meta/post-deploy-git.txt"

# -----------------------------------------------------------------------------
section "3. ingest / DB history"
ING="$OUT/ingest"
mkdir -p "$ING"
dump_sql() {
  local name="$1" sql="$2"
  if have docker && docker ps --format '{{.Names}}' | grep -qE 'postgres|dana-prod'; then
    # try common container names
    local c
    for c in dana-prod-postgres-1 dana-local-postgres-1 postgres; do
      if docker ps --format '{{.Names}}' | grep -qx "$c"; then
        docker exec "$c" psql -U postgres -d kb_manager -c "$sql" >"$ING/$name.txt" 2>&1 && return 0
      fi
    done
  fi
  if have psql; then
    PGPASSWORD="${POSTGRES_PASSWORD:-postgres}" psql -h 127.0.0.1 -U postgres -d kb_manager -c "$sql" \
      >"$ING/$name.txt" 2>&1 && return 0
  fi
  echo "unavailable" >"$ING/$name.txt"
  return 1
}
dump_sql counts "SELECT
  (SELECT count(*) FROM documents) AS docs,
  (SELECT count(*) FROM chunks) AS chunks;"
dump_sql recent_docs "SELECT id, title, created_at FROM documents ORDER BY created_at DESC NULLS LAST LIMIT 30;"
dump_sql ingest_jobs "SELECT id, status, created_at, completed_at, left(coalesce(error,''),200) AS err
  FROM ingestion_jobs ORDER BY created_at DESC NULLS LAST LIMIT 40;" 2>/dev/null \
  || dump_sql ingest_jobs "SELECT * FROM ingestion_job ORDER BY id DESC LIMIT 40;" 2>/dev/null \
  || echo "ingestion_jobs table not found" | tee "$ING/ingest_jobs.txt"
dump_sql chunk_sample "SELECT id, left(content,80) FROM chunks ORDER BY created_at DESC NULLS LAST LIMIT 5;"
ok "ingest dumps → $ING"

# -----------------------------------------------------------------------------
section "4. collect raw logs"
LOGDIR="$OUT/logs"
# docker logs
if have docker; then
  docker ps -a --format '{{.Names}}' | while read -r c; do
    case "$c" in
      *kb*|*guard*|*orch*|*webui*|*litellm*|*jenkins*|*postgres*|*tracing*|*manager*|*gemma*|*dana*)
        docker logs --tail 400 "$c" >"$LOGDIR/docker-${c}.log" 2>&1 || true
        ;;
    esac
  done
fi
# host /tmp logs (Vast path)
for f in /tmp/kb.log /tmp/guard.log /tmp/orch.log /tmp/webui.log /tmp/llama-server.log \
         /tmp/langfuse.log /tmp/manager.log /tmp/embed*.log; do
  for g in $f; do
    [[ -f "$g" ]] || continue
    base="$(basename "$g")"
    tail -n 500 "$g" >"$LOGDIR/host-$base" 2>&1 || true
  done
done
# journal (if any)
if have journalctl; then
  journalctl -u dana-keep-latest.service -n 200 --no-pager >"$LOGDIR/journal-keep-latest.txt" 2>&1 || true
  journalctl -u docker -n 100 --no-pager >"$LOGDIR/journal-docker.txt" 2>&1 || true
fi
ok "raw logs collected"

# -----------------------------------------------------------------------------
section "5. DOWN / ERROR signature scan"
SIG="$OUT/redacted/down-signatures.txt"
: >"$SIG"
PATTERN='(?i)(error|exception|traceback|fatal|oom|killed|connection refused|not our ref|nameerror|empty reply|unhealthy|crash|segfault|cannot connect|timeout|read timed out|no space|disk full|CUDA out of memory|failed to|ECONNREFUSED|address already in use)'
if have rg; then
  rg -n -i -e 'error|exception|traceback|fatal|oom|killed|connection refused|not our ref|nameerror|empty reply|unhealthy|crash|CUDA out of memory|ECONNREFUSED|no space|disk full' \
    "$LOGDIR" 2>/dev/null | head -n 400 | tee "$SIG" || true
else
  grep -RniE 'error|exception|traceback|fatal|oom|killed|connection refused|unhealthy|CUDA out of memory' "$LOGDIR" 2>/dev/null \
    | head -n 400 | tee "$SIG" || true
fi
# redact secrets in signature file
if [[ -f "$SIG" ]]; then
  sed -E -i.bak \
    -e 's/sk-[a-zA-Z0-9_-]+/sk-REDACTED/g' \
    -e 's/OPENROUTER_API_KEY=[^[:space:]]+/OPENROUTER_API_KEY=REDACTED/g' \
    -e 's/postgres:[^:@/]+@/postgres:REDACTED@/g' \
    "$SIG" 2>/dev/null || true
  rm -f "$SIG.bak"
fi
HIT_COUNT="$(wc -l <"$SIG" | tr -d ' ')"
echo "signature_hits=$HIT_COUNT" | tee "$OUT/meta/signature_count.txt"

# -----------------------------------------------------------------------------
section "6. curl health matrix"
CURLDIR="$OUT/curl"
PORTS=(18000 9000 8000 8200 8100 3000 3001 13000 8085 8010 8001 8002 8003)
: >"$CURLDIR/matrix.tsv"
echo -e "port\thttp\tbody_preview" >>"$CURLDIR/matrix.tsv"
HEALTH_FAIL=0
for p in "${PORTS[@]}"; do
  body="$(curl -sS --max-time 8 "http://127.0.0.1:$p/health" 2>/dev/null || true)"
  code="000"
  if [[ -n "$body" ]]; then
    code="200"
  else
    body="$(curl -sS --max-time 8 "http://127.0.0.1:$p/health/liveliness" 2>/dev/null || true)"
    [[ -n "$body" ]] && code="200"
  fi
  if [[ "$code" != "200" ]]; then
    # login pages / models
    code="$(curl -sS -o /tmp/spof_curl_body.txt -w '%{http_code}' --max-time 5 "http://127.0.0.1:$p/" 2>/dev/null || echo 000)"
    body="$(head -c 120 /tmp/spof_curl_body.txt 2>/dev/null || true)"
  fi
  preview="$(printf '%s' "$body" | tr '\n' ' ' | head -c 160)"
  echo -e "${p}\t${code}\t${preview}" | tee -a "$CURLDIR/matrix.tsv"
  printf '%s\n' "$body" >"$CURLDIR/port-${p}.txt"
  # critical app ports
  case "$p" in
    8000|8100|8200)
      if [[ "$code" != "200" ]]; then HEALTH_FAIL=1; fail "critical :$p down"; else ok ":$p up"; fi
      ;;
  esac
done

# ready endpoints
for url in http://127.0.0.1:8100/ready http://127.0.0.1:8200/ready; do
  curl -sS --max-time 10 "$url" | tee "$CURLDIR/$(echo "$url" | tr '/:' '__').txt" | head -c 300; echo
done

# -----------------------------------------------------------------------------
section "7. E2E chat QA"
E2E="$OUT/e2e"
QA_PASS=0
QA_TOTAL=0
run_chat() {
  local name="$1" payload="$2" url="${3:-http://127.0.0.1:8100/v1/chat/completions}"
  QA_TOTAL=$((QA_TOTAL + 1))
  local outf="$E2E/${name}.json"
  local code
  code="$(curl -sS -o "$outf" -w '%{http_code}' --max-time 120 \
    -H 'Content-Type: application/json' \
    -d "$payload" "$url" 2>/dev/null || echo 000)"
  echo "chat_$name http=$code" | tee -a "$E2E/summary.txt"
  if [[ "$code" == "200" ]] && grep -q '"content"' "$outf" 2>/dev/null; then
    QA_PASS=$((QA_PASS + 1))
    ok "E2E $name pass"
  else
    fail "E2E $name fail (http=$code)"
    head -c 400 "$outf"; echo
  fi
}
mkdir -p "$E2E"
: >"$E2E/summary.txt"
run_chat greeting '{"model":"gemma-4-31b","messages":[{"role":"user","content":"سلام"}]}'
run_chat credit_qa '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}'
# KB search direct
curl -sS --max-time 60 -o "$E2E/kb_search.json" -w 'kb_search http=%{http_code}\n' \
  -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":3}' \
  http://127.0.0.1:8000/search/api | tee -a "$E2E/summary.txt" || true
if grep -q 'final_results\|content_preview' "$E2E/kb_search.json" 2>/dev/null; then
  ok "KB search returned results"
else
  fail "KB search empty/failed"
fi
echo "qa_pass=$QA_PASS/$QA_TOTAL" | tee "$E2E/score.txt"

# -----------------------------------------------------------------------------
section "8. screenshots"
SHOT="$OUT/screenshots"
mkdir -p "$SHOT"
if [[ "$NO_SCREENSHOT" == "1" ]]; then
  warn "screenshots skipped"
else
  CHROME=""
  for c in chromium chromium-browser google-chrome google-chrome-stable; do
    if have "$c"; then CHROME="$c"; break; fi
  done
  shoot() {
    local url="$1" name="$2"
    if [[ -n "$CHROME" ]]; then
      "$CHROME" --headless --disable-gpu --window-size=1400,900 \
        --screenshot="$SHOT/${name}.png" "$url" 2>"$SHOT/${name}.chrome.log" && ok "shot $name" && return 0
    fi
    if have python3; then
      python3 - <<PY 2>"$SHOT/${name}.py.log" && ok "shot $name (playwright/selenium fallback attempted)" && return 0
import sys
url="$url"; out="$SHOT/${name}.png"
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b=p.chromium.launch()
        page=b.new_page(viewport={"width":1400,"height":900})
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.screenshot(path=out, full_page=True)
        b.close()
    sys.exit(0)
except Exception as e:
    open("$SHOT/${name}.py.log","a").write(str(e))
    sys.exit(1)
PY
    fi
    warn "no browser for screenshot $name — wrote URL stub"
    echo "$url" >"$SHOT/${name}.url.txt"
  }
  shoot "http://127.0.0.1:8100/health" "orch-health"
  shoot "http://127.0.0.1:8000/health" "kb-health"
  shoot "http://127.0.0.1:13000/" "webui-home"
  # If WebUI needs a path after load:
  shoot "http://127.0.0.1:8085/login" "jenkins-login"
fi
ls -la "$SHOT" | tee "$SHOT/listing.txt"

# -----------------------------------------------------------------------------
section "9. write REPORT.md"
REPORT="$OUT/REPORT.md"
STATUS="DEGRADED"
if [[ "$HEALTH_FAIL" == "0" && "$QA_PASS" -ge 1 ]]; then STATUS="HEALTHY"; fi
if [[ "$HEALTH_FAIL" == "1" && "$QA_PASS" -eq 0 ]]; then STATUS="DOWN"; fi

cat >"$REPORT" <<EOF
# GPU SPOF recovery report — \`$RUN_ID\`

| Field | Value |
|------|------|
| UTC | $(date -u +%Y-%m-%dT%H:%M:%SZ) |
| Host | $(hostname -f 2>/dev/null \|\| hostname) |
| Status | **$STATUS** |
| Mode | \`$MODE\` |
| Umbrella HEAD | $(git -C "$UMBRELLA" rev-parse --short HEAD 2>/dev/null \|\| n/a) |
| last_good | $(cat "$UMBRELLA/deploy/compose/.last_good_sha" 2>/dev/null \|\| none) |
| QA | $QA_PASS / $QA_TOTAL chat passes |
| Log signature hits | $HIT_COUNT |

## What this run did
1. Best-effort service bring-up (compose gpu)
2. Keep-latest / last-good alignment
3. Postgres ingest history dump
4. Docker + /tmp log harvest + DOWN/ERROR scan
5. Curl health matrix
6. E2E chat + KB search
7. Headless screenshots (if browser present)

## Health matrix
\`\`\`
$(column -t -s $'\t' "$CURLDIR/matrix.tsv" 2>/dev/null || cat "$CURLDIR/matrix.tsv")
\`\`\`

## Top DOWN/ERROR signatures (redacted)
\`\`\`
$(head -n 80 "$SIG" 2>/dev/null || echo none)
\`\`\`

## Ingest counts
\`\`\`
$(cat "$ING/counts.txt" 2>/dev/null || echo n/a)
\`\`\`

## E2E summary
\`\`\`
$(cat "$E2E/summary.txt" 2>/dev/null)
$(cat "$E2E/score.txt" 2>/dev/null)
\`\`\`

## Screenshots
$(ls "$SHOT"/*.png 2>/dev/null | while read -r f; do echo "- ![]($(basename "$f"))"; done || echo "_none_")

## How to re-run
\`\`\`bash
DANA_HOST_REPO=$UMBRELLA bash $SS_REPO/scripts/gpu_spof_recover_report.sh
\`\`\`

Artifacts live under \`docs/ops/gpu-spof-reports/$RUN_ID/\` in Work_RAG-Server-Setup.
EOF
ok "wrote $REPORT"

# Redact all text artifacts before push
section "10. redact + push to Work_RAG-Server-Setup"
find "$OUT" -type f \( -name '*.txt' -o -name '*.log' -o -name '*.json' -o -name '*.md' -o -name '*.tsv' \) -print0 \
  | while IFS= read -r -d '' f; do
      sed -E -i.bak \
        -e 's/sk-[a-zA-Z0-9_-]{10,}/sk-REDACTED/g' \
        -e 's/(API_KEY|SECRET|PASSWORD|TOKEN)=[^[:space:]]+/\1=REDACTED/g' \
        -e 's#postgresql(\+asyncpg)?://[^[:space:]]+#postgresql://REDACTED#g' \
        "$f" 2>/dev/null || true
      rm -f "$f.bak"
    done

# Index file for easy browsing
INDEX="$SS_REPO/docs/ops/gpu-spof-reports/README.md"
mkdir -p "$(dirname "$INDEX")"
if [[ ! -f "$INDEX" ]]; then
  cat >"$INDEX" <<'EOF'
# GPU SPOF recovery reports

Generated by `scripts/gpu_spof_recover_report.sh` on the production GPU host.
Each subdirectory is one run (`UTC timestamp + hostname`).

Open `REPORT.md` inside a run for the summary; screenshots and curl/e2e dumps are alongside.
EOF
fi
{
  echo "- [$RUN_ID](./$RUN_ID/REPORT.md) — **$STATUS** — QA $QA_PASS/$QA_TOTAL — sigs $HIT_COUNT"
} >>"$INDEX"

if [[ "$NO_PUSH" == "1" ]]; then
  warn "skipping git push (--no-push). Report at $OUT"
  echo "REPORT_DIR=$OUT"
  echo "STATUS=$STATUS"
  exit 0
fi

if [[ ! -d "$SS_REPO/.git" ]]; then
  fail "server-setup is not a git checkout at $SS_REPO — cannot push"
  echo "REPORT_DIR=$OUT"
  exit 1
fi

BRANCH="ops/gpu-spof-$RUN_ID"
cd "$SS_REPO"
git fetch origin 2>&1 | tee -a "$OUT/meta/git-push.log" || true
git checkout -B "$BRANCH" 2>&1 | tee -a "$OUT/meta/git-push.log" || git checkout -B "$BRANCH" origin/main
git add "docs/ops/gpu-spof-reports/$RUN_ID" docs/ops/gpu-spof-reports/README.md
git status --short | tee -a "$OUT/meta/git-push.log"
if git diff --cached --quiet; then
  warn "nothing to commit"
else
  git commit -m "$(cat <<EOF
docs(ops): GPU SPOF report $RUN_ID ($STATUS)

Automated recover+evidence pack: health, ingest, logs, E2E QA, screenshots.
EOF
)" 2>&1 | tee -a "$OUT/meta/git-push.log"
fi
if git push -u origin "$BRANCH" 2>&1 | tee -a "$OUT/meta/git-push.log"; then
  ok "pushed origin/$BRANCH"
  if have gh; then
    gh pr create --base main --head "$BRANCH" \
      --title "docs(ops): GPU SPOF report $RUN_ID ($STATUS)" \
      --body "Automated evidence pack from \`gpu_spof_recover_report.sh\` on $(hostname). Status: **$STATUS**." \
      2>&1 | tee -a "$OUT/meta/git-push.log" || warn "gh pr create failed (branch still pushed)"
  fi
else
  fail "git push failed — report remains at $OUT"
fi

echo
echo "REPORT_DIR=$OUT"
echo "STATUS=$STATUS"
echo "BRANCH=$BRANCH"
[[ "$STATUS" == "HEALTHY" ]] && exit 0 || exit 1
