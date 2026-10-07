#!/usr/bin/env bash
set -euo pipefail
# Triton-optimized vLLM launcher for champion GGUF (Option B: reuse, no HF download)
# Uses Docker vllm/vllm-openai (bundles correct torch+triton) to avoid host venv mismatch
# Ports: 8104 = Triton-vLLM optimized endpoint that Manager will promote as gemma-4-31b
ROOT="/splunk-data/v1/Work_RAG-Server-Setup"
GGUF="/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf"
IMG="${VLLM_IMAGE:-vllm/vllm-openai:latest}"
PORT="${1:-8104}"
GPU_MEM="${2:-0.90}"

if [ ! -f "$GGUF" ]; then
  echo "[vllm-opt] GGUF not found: $GGUF" >&2
  exit 1
fi

# Pull via proxy-aware docker daemon (already configured in proxy_setup.sh)
echo "[vllm-opt] docker pull $IMG ..."
docker pull "$IMG" 2>&1 | tail -n 20 || echo "[vllm-opt] pull failed, will try existing local image"

echo "[vllm-opt] cleaning old container vllm-gemma-opt ..."
docker rm -f vllm-gemma-opt 2>/dev/null || true

# GGUF via file mount; vLLM 0.6.1+ supports --load-format gguf
echo "[vllm-opt] launching $IMG on :$PORT GPU mem $GPU_MEM ..."
docker run -d --name vllm-gemma-opt --gpus all \
  -p ${PORT}:8000 \
  -v "$(dirname "$GGUF"):/models:ro" \
  -v "$ROOT/offline-prep/hf_cache:/root/.cache/huggingface" \
  "$IMG" \
  --model "/models/$(basename "$GGUF")" \
  --load-format gguf \
  --quantization gguf \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization "$GPU_MEM" \
  --max-model-len 8192 \
  --enable-prefix-caching \
  --enable-auto-tool-choice \
  --tool-call-parser hermes

echo "[vllm-opt] waiting for health http://127.0.0.1:$PORT/health ..."
for i in $(seq 1 60); do
  if curl -s http://127.0.0.1:$PORT/health >/dev/null 2>&1 || curl -s http://127.0.0.1:$PORT/v1/models >/dev/null 2>&1; then
    echo "[vllm-opt] ready after $i*2s"
    curl -s http://127.0.0.1:$PORT/v1/models | head -c 500; echo
    exit 0
  fi
  sleep 2
  if [ $((i % 10)) -eq 0 ]; then echo "[vllm-opt] still waiting... $((i*2))s"; docker logs --tail 20 vllm-gemma-opt 2>&1 | tail -n 20 || true; fi
done
echo "[vllm-opt] timeout, last logs:"
docker logs --tail 100 vllm-gemma-opt 2>&1 | tail -n 100 || true
exit 1
