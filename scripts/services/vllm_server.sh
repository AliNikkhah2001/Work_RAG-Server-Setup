#!/usr/bin/env bash
set -euo pipefail

# Launch vLLM OpenAI-compatible API server for a single-file GGUF model.
# vLLM requires a single .gguf (does NOT support split/multi-part GGUF).
MODEL="${1:?usage: vllm_server.sh <path-to-model.gguf> [port] [gpu-mem-util]}"
PORT="${2:-8000}"
GPU_MEM="${3:-0.85}"
VENV_PY="/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/venv/bin/python3.12"

exec "$VENV_PY" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --load-format gguf \
    --quantization gguf \
    --host 0.0.0.0 \
    --port "$PORT" \
    --gpu-memory-utilization "$GPU_MEM" \
    --max-model-len 8192
