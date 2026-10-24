#!/bin/bash
# Start Guardrails (:8200) with the TensorRT-LLM gemma-4-31b server as the
# upstream LLM (the conc-128 champion on :8010). Replaces the old llama.cpp
# GGUF upstream (:18000). Run from anywhere; safe to re-run after a kill.
set -u

REPO=/splunk-data/v1/Work_RAG-Server-Setup
VENV="$REPO/offline-prep/venv"
COMPONENT=/splunk-data/v1/Work_Credit-RAG_Phase1
LOGD=/tmp/reload_backup
mkdir -p "$LOGD"

cd "$COMPONENT"
export PYTHONPATH="$COMPONENT/components/guardrails/src"
export GUARDRAILS_HOST=0.0.0.0
export GUARDRAILS_PORT=8200
# Upstream = TensorRT-LLM champion (ground truth). TRT-LLM ignores the model id,
# but we send its advertised name. To route via the manager instead, use
# http://127.0.0.1:9000/v1 + model gemma-4-31b.
export UPSTREAM_LLM_BASE_URL=http://127.0.0.1:8010/v1
export UPSTREAM_LLM_MODEL=google_gemma-4-31b-it
export no_proxy=localhost,127.0.0.1,.local
export NO_PROXY=localhost,127.0.0.1,.local

nohup "$VENV/bin/python" -m uvicorn work_rag_guardrails.api:create_app \
  --factory --host 0.0.0.0 --port 8200 >> "$LOGD/guardrails_8200.log" 2>&1 &
echo "started guardrails 8200 -> $UPSTREAM_LLM_BASE_URL pid $!"
