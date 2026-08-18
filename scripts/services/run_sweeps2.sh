#!/usr/bin/env bash
# Resume sweeps: 5-shot (needs bigger ctx) + temperature sweep on GPU1.
set -e
cd /splunk-data/v1/Work_RAG-Server-Setup
export HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=1
PY=offline-prep/venv/bin/python3.12
MODEL=offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf

run() {
  local tag="$1"; shift
  echo "[$(date +%H:%M:%S)] START $tag"
  $PY scripts/eval_persian.py --model "$MODEL" --limit 50 --chat --max-tokens 160 \
    --out "evalp_qwen2.5-7b_${tag}.json" "$@"
  echo "[$(date +%H:%M:%S)] DONE $tag"
}

run 5shot --n-shots 5 --n-ctx 16384
run temp02 --temperature 0.2
run temp05 --temperature 0.5
run temp08 --temperature 0.8
run temp10 --temperature 1.0
echo "[$(date +%H:%M:%S)] ALL SWEEPS DONE"