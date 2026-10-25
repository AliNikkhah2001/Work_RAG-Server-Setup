#!/bin/bash
# Launch TensorRT-LLM (trtllm-serve) for gemma-4-31b on a single H200 (GPU index CUDA_VISIBLE_DEVICES).
#
# Why this wrapper exists (all fixes are required; see docs/findings.md):
#  1. Dynamic MPI_Comm_spawn (MpiPoolSession / MPIPoolExecutor) HANGS on this host.
#     Under `mpirun -n 1` + `trtllm-llmapi-launch` TRT-LLM instead uses the
#     spawn-proxy (mgmn leader/worker) + RemoteMpiCommSessionClient IPC path.
#  2. trtllm-llmapi-launch calls `python3 -m tensorrt_llm.llmapi.mgmn_leader_node`,
#     so the venv MUST be first on PATH (else system python3 lacks tensorrt_llm).
#  3. FlashInfer JIT runs nvcc with `-Xfatbin=-compress-all --compress-mode=size`
#     (CUDA >=12.8). Host nvcc is CUDA 12.0 -> "Unknown option". We compose a
#     CUDA 13.2 toolkit from pip packages under nvidia/cu13/ and point CUDA_HOME
#     + PATH at it.
#  4. gemma4 has per-layer head_dim (sliding=256, global=512). The default TRTLLM
#     attention backend's MMHA kernel asserts on head size 512, so we override
#     attn_backend (via extra_llm_api_options) to a backend that tolerates it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${TRTLLM_VENV:-$ROOT/offline-prep/venv-trtllm}"
MODEL="${TRTLLM_MODEL:-$ROOT/offline-prep/models/huggingface/google_gemma-4-31b-it}"
HOST="${TRTLLM_HOST:-0.0.0.0}"
PORT="${TRTLLM_PORT:-8010}"
TP="${TRTLLM_TP:-1}"
MAX_BATCH="${TRTLLM_MAX_BATCH:-128}"
MAX_NUM_TOKENS="${TRTLLM_MAX_NUM_TOKENS:-16384}"
MAX_SEQ_LEN="${TRTLLM_MAX_SEQ_LEN:-8192}"
KV_FRAC="${TRTLLM_KV_FRACTION:-0.85}"
KV_DTYPE="${TRTLLM_KV_DTYPE:-}"
GPU="${TRTLLM_GPU:-1}"
EXTRA="${TRTLLM_EXTRA_OPTIONS:-$ROOT/scripts/trtllm_extra_options.yaml}"
LOG="${TRTLLM_LOG:-$ROOT/logs/trtllm_serve.log}"

CU13="$VENV/lib/python3.12/site-packages/nvidia/cu13"
mkdir -p "$ROOT/logs"

# CUDA 13.2 toolkit (nvcc/crt/nvvm/include/lib) composed from pip packages.
export CUDA_HOME="$CU13"
export PATH="$CU13/bin:$VENV/bin:$PATH"

# Runtime libraries: every nvidia/*/lib plus the CUDA 13 toolkit lib.
LIBS="$(find "$VENV/lib/python3.12/site-packages/nvidia" -maxdepth 3 -type d -name lib 2>/dev/null | paste -sd: || true)"
export LD_LIBRARY_PATH="${LIBS}:$CU13/lib:${LD_LIBRARY_PATH:-}"

# Offline HF cache; never let localhost calls hit the corporate Squid proxy.
export HF_HOME="${HF_HOME:-$ROOT/offline-prep/models/huggingface}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export no_proxy="localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="$no_proxy"

# mpirun runs as root here.
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

export CUDA_VISIBLE_DEVICES="$GPU"

EXTRA_ARGS=()
if [ -f "$EXTRA" ]; then
  EXTRA_ARGS=(--extra_llm_api_options "$EXTRA")
fi

# Optional: KV-cache FP8 (prototype) and explicit max batched tokens.
KV_ARGS=()
if [ -n "$KV_DTYPE" ]; then
  KV_ARGS=(--kv_cache_dtype "$KV_DTYPE")
fi
TOK_ARGS=()
if [ -n "$MAX_NUM_TOKENS" ]; then
  TOK_ARGS=(--max_num_tokens "$MAX_NUM_TOKENS")
fi

exec mpirun -n "$TP" "$VENV/bin/trtllm-llmapi-launch" \
  "$VENV/bin/trtllm-serve" serve "$MODEL" \
  --host "$HOST" --port "$PORT" --backend pytorch \
  --tp_size "$TP" --max_batch_size "$MAX_BATCH" --max_seq_len "$MAX_SEQ_LEN" \
  --kv_cache_free_gpu_memory_fraction "$KV_FRAC" \
  "${KV_ARGS[@]}" "${TOK_ARGS[@]}" "${EXTRA_ARGS[@]}" \
  >> "$LOG" 2>&1
