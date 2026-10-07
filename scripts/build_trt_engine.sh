#!/usr/bin/env bash
set -euo pipefail
# Build TensorRT-LLM FP8 engine for Gemma-4-31B (Option A)
# Requires HF checkpoint at offline-prep/models/huggingface/google_gemma-4-31b-it
# Output: offline-prep/models/trt_engines/gemma-4-31b_fp8 -> deployed to triton repo
ROOT="/splunk-data/v1/Work_RAG-Server-Setup"
HF_CKPT="$ROOT/offline-prep/models/huggingface/google_gemma-4-31b-it"
ENGINE_OUT="$ROOT/offline-prep/models/trt_engines/gemma-4-31b_fp8"
TRITON_MODEL_DIR="$ROOT/deploy/triton/model_repository/gemma-4-31b-trt/1"

if [ ! -d "$HF_CKPT" ] || [ -z "$(ls -A "$HF_CKPT" 2>/dev/null | grep -E 'config.json|safetensors')" ]; then
  echo "[trtllm] HF checkpoint not found at $HF_CKPT"
  echo "[trtllm] Run download first: HF_HUB_DISABLE_XET=1 $ROOT/offline-prep/venv/bin/python3.12 scripts/download_models.py --only google/gemma-4-31b-it"
  exit 1
fi

# Use Triton builder image to avoid host torch mismatch
IMAGE="nvcr.io/nvidia/tritonserver:24.12-trtllm-python-py3"
echo "[trtllm] building FP8 engine via $IMAGE ..."
mkdir -p "$ENGINE_OUT" "$(dirname "$TRITON_MODEL_DIR")"
docker run --rm --gpus all \
  -v "$HF_CKPT:/ckpt:ro" \
  -v "$ENGINE_OUT:/out" \
  "$IMAGE" bash -c "trtllm-build --checkpoint_dir /ckpt --output_dir /out --max_batch_size 8 --max_input_len 8192 --max_seq_len 8192 --use_fp8 --gemm_plugin fp8 --gpt_attention_plugin float16 --paged_kv_cache enable --workers 1 && chmod -R 777 /out"

echo "[trtllm] engine built at $ENGINE_OUT (du: $(du -sh "$ENGINE_OUT" | cut -f1))"
echo "[trtllm] deploying to Triton repo $TRITON_MODEL_DIR ..."
rm -rf "$TRITON_MODEL_DIR"
cp -r "$ENGINE_OUT" "$TRITON_MODEL_DIR"
curl -s -X POST http://127.0.0.1:8004/v2/repository/models/gemma-4-31b-trt/load 2>&1 | head -c 500 || echo "manual: docker restart triton-test"
echo "[trtllm] done"
