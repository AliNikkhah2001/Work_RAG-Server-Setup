#!/usr/bin/env bash
set -euo pipefail
# Triton Inference Server launcher - fronts both B (vLLM-GGUF) and A (TRT-LLM) backends
# Ports chosen to avoid embeds 8001-8003 and manager 9000, llama 8080-8090, deepseek 9001
# HTTP 8004 / gRPC 8005 / metrics 8006
ROOT="/splunk-data/v1/Work_RAG-Server-Setup"
IMAGE="${TRITON_IMAGE:-nvcr.io/nvidia/tritonserver:24.12-trtllm-python-py3}"
REPO_HOST="$ROOT/deploy/triton/model_repository"
HF_HOST="$ROOT/offline-prep/models/huggingface"
ENGINE_HOST="$ROOT/offline-prep/models/trt_engines"

# ensure engine dir exists (empty until A build completes - Triton tolerates missing model, marks UNAVAILABLE)
mkdir -p "$ENGINE_HOST"

echo "[triton] pulling $IMAGE (proxy-aware)..."
docker pull "$IMAGE" || echo "[triton] pull failed via proxy, retry with --noproxy? Will retry"

echo "[triton] starting container triton-test on 8004/8005/8006 ..."
docker rm -f triton-test 2>/dev/null || true
docker run -d --name triton-test --gpus all \
  -p 8004:8000 -p 8005:8001 -p 8006:8002 \
  -v "$REPO_HOST:/models" \
  -v "$HF_HOST:/hf:ro" \
  -v "$ENGINE_HOST:/engines:ro" \
  --shm-size=8g \
  "$IMAGE" tritonserver --model-repository=/models --log-verbose=1 --metrics-port=8002 --allow-metrics=true

sleep 3
echo "[triton] health: $(curl -s http://127.0.0.1:8004/v2/health/ready || echo 'not ready yet - check docker logs triton-test')"
docker logs --tail 50 triton-test 2>&1 | tail -n 50 || true
