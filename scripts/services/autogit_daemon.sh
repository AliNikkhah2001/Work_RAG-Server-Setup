#!/usr/bin/env bash
set -u

REPO_DIR="/splunk-data/v1/Work_RAG-Server-Setup"
INTERVAL="${AUTOGIT_INTERVAL:-300}"
LOG_DIR="$REPO_DIR/logs"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_DIR/autogit.out"; }

log "autogit daemon started (interval=${INTERVAL}s)"

while true; do
    sleep "$INTERVAL"
    cd "$REPO_DIR" || { log "ERROR: cannot cd to $REPO_DIR"; continue; }

    git fetch origin -q 2>>"$LOG_DIR/autogit.out"
    git pull --rebase origin main -q 2>>"$LOG_DIR/autogit.out"

    if git status --porcelain | grep -q .; then
        git add -A 2>>"$LOG_DIR/autogit.out"
        git commit -m "auto: sync working state [$(date '+%Y-%m-%d %H:%M:%S')]" 2>>"$LOG_DIR/autogit.out" && \
        git push origin main 2>>"$LOG_DIR/autogit.out" && \
        log "committed + pushed working state" || log "commit/push issue (see log)"
    else
        log "no changes to commit"
    fi
done