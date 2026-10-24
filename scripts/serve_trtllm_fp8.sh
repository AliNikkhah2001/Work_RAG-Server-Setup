#!/bin/bash
# Serve the ModelOpt-quantized gemma-4-31b checkpoint with TensorRT-LLM.
#
# This is a thin wrapper around scripts/serve_trtllm.sh: the only thing that
# changes is TRTLLM_MODEL, which now points at the FP8/NVFP4 checkpoint produced
# by scripts/quantize_gemma4_fp8.py. TRT-LLM's PyTorch backend auto-detects the
# quantization from `hf_quant_config.json` in the checkpoint, so no extra
# quant flag is required on the command line.
#
# Safety: the live production champion runs on GPU1:8010 (never touch it). This
# wrapper defaults to GPU0:8011 and refuses to start on :8010.
#
# Usage:
#   scripts/serve_trtllm_fp8.sh                       # GPU0, port 8011
#   TRTLLM_GPU=0 TRTLLM_PORT=8011 scripts/serve_trtllm_fp8.sh
#   TRTLLM_MODEL=/path/to/other-fp8 scripts/serve_trtllm_fp8.sh
#
# Any serve_trtllm.sh env var may be overridden here (TRTLLM_TP, TRTLLM_KV_FRACTION,
# TRTLLM_EXTRA_OPTIONS, TRTLLM_LOG, ...).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Point the generic launcher at the quantized checkpoint.
export TRTLLM_MODEL="${TRTLLM_MODEL:-$ROOT/offline-prep/models/huggingface/google_gemma-4-31b-it-fp8}"
export TRTLLM_PORT="${TRTLLM_PORT:-8011}"
export TRTLLM_GPU="${TRTLLM_GPU:-0}"
export TRTLLM_LOG="${TRTLLM_LOG:-$ROOT/logs/trtllm_serve_fp8.log}"

if [ ! -d "$TRTLLM_MODEL" ]; then
  echo "ERROR: quantized checkpoint not found: $TRTLLM_MODEL" >&2
  echo "Run scripts/quantize_gemma4_fp8.py first." >&2
  exit 1
fi

# Never clash with the live champion on :8010.
if [ "$TRTLLM_PORT" = "8010" ]; then
  echo "ERROR: port 8010 is reserved for the production champion (GPU1)." >&2
  exit 1
fi

echo "Serving FP8 checkpoint: $TRTLLM_MODEL"
echo "  gpu=$TRTLLM_GPU port=$TRTLLM_PORT tp=${TRTLLM_TP:-1} log=$TRTLLM_LOG"
exec "$ROOT/scripts/serve_trtllm.sh"
