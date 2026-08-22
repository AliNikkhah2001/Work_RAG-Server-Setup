#!/bin/bash
set -e
BASE="/splunk-data/v1/Work_RAG-Server-Setup"
MODEL="$BASE/offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf"
PY="$BASE/offline-prep/venv/bin/python3.12"
SVC="$BASE/scripts/services/llama_chat_server.py"
LOGDIR="$BASE/logs"
mkdir -p "$LOGDIR"
for i in 1 2 3 4 5; do
  port=$((8079+i))
  gpu=$(( (i-1)%2 ))
  (
    while true; do
      echo "$(date -Is) start gemma-4-31b-$i port $port gpu $gpu" >> "$LOGDIR/gemma_supervisor.log"
      env CUDA_VISIBLE_DEVICES=$gpu $PY "$SVC" --model "$MODEL" --port $port --model-id gemma-4-31b-$i --n-ctx 8192 >> "$LOGDIR/llama_server_${port}.log" 2>&1
      echo "$(date -Is) exit gemma-4-31b-$i code $?" >> "$LOGDIR/gemma_supervisor.log"
      sleep 3
    done
  ) &
done
wait
