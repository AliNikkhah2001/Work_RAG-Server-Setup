#!/usr/bin/env bash
set -u

REPO_DIR="/splunk-data/v1/Work_RAG-Server-Setup"
INTERVAL="${AUTOGIT_INTERVAL:-1800}"
LOG_DIR="$REPO_DIR/logs"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_DIR/autogit.out"; }

log "autogit daemon started (interval=${INTERVAL}s)"

while true; do
    sleep "$INTERVAL"
    cd "$REPO_DIR" || { log "ERROR: cannot cd to $REPO_DIR"; continue; }

    git fetch origin -q 2>>"$LOG_DIR/autogit.out"

    # 1) Commit local changes first (so rebase has a clean tree)
    if git status --porcelain | grep -q .; then
        git add -A 2>>"$LOG_DIR/autogit.out"
        if git commit -m "auto: sync working state [$(date '+%Y-%m-%d %H:%M:%S')]" 2>>"$LOG_DIR/autogit.out"; then
            log "committed local changes"
        else
            log "commit failed"
        fi
    fi

    # 2) Rebase onto origin (tree is now clean)
    if git rev-list --count HEAD..origin/main 2>/dev/null | grep -q '[1-9]'; then
        if git pull --rebase origin main -q 2>>"$LOG_DIR/autogit.out"; then
            log "rebased onto origin/main"
        else
            log "rebase failed"
        fi
    fi

    # 3) Push if local is ahead
    if git rev-list --count origin/main..HEAD 2>/dev/null | grep -q '[1-9]'; then
        if git push origin main 2>>"$LOG_DIR/autogit.out"; then
            log "pushed to origin/main"
        else
            log "push failed"
        fi
    else
        log "no changes to push"
    fi
done