#!/bin/bash
# Run improved-prompt evals sequentially across all 9 models (GPU1).
# Each run: 7 tasks x 50 rows, max_tokens 400 (Qwen3 thinking models included).
cd /splunk-data/v1/Work_RAG-Server-Setup || exit 1
export HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=1
V=offline-prep/venv/bin/python3.12
M=offline-prep/models/huggingface
declare -a MODELS=(
  "bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
  "bartowski_Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
  "bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
  "microsoft_Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4.gguf"
  "bartowski_google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-Q4_K_M.gguf"
  "bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf"
  "Qwen_Qwen3-30B-A3B-GGUF/Qwen3-30B-A3B-Q4_K_M.gguf"
  "bartowski_Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf"
  "bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf"
)
for path in "${MODELS[@]}"; do
  stem=$(basename "$path" .gguf)
  echo "=== IMPROVED $stem ==="
  "$V" scripts/eval_persian.py --model "$M/$path" --limit 50 --chat --max-tokens 400 \
      --prompt-style improved --out "logs/evalp_${stem}_improved.json"
  echo "done $stem"
done
echo "ALL IMPROVED EVALS DONE"