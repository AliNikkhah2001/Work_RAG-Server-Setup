#!/bin/bash
cd /splunk-data/v1/Work_RAG-Server-Setup || exit 1
for m in qwen3.8-27b qwen3-30b nemotron-49b qwen2.5-7b llama3.2-3b mistral-7b phi3-mini; do
  echo "=== $m ==="
  HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=1 offline-prep/venv/bin/python3.12 scripts/bench_speed.py --only $m --out logs/speed_$m.json
  echo "done $m"
done
echo "ALL DONE"