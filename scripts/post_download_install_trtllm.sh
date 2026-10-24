#!/bin/bash
set -uo pipefail

ROOT="/splunk-data/v1/Work_RAG-Server-Setup"
VENV="$ROOT/offline-prep/venv-trtllm"
WHEELS="$ROOT/offline-prep/wheels"
TRTLLM_WHEEL="$WHEELS/tensorrt_llm-1.3.0rc29-cp312-cp312-manylinux_2_28_x86_64.whl"
TRTLLM_SHA="45e52e1e24e424f5e9a3ce07217b034c8420dafec2fd0d9fb079f20339e2a761"
LOG="/tmp/trtllm_bootstrap.log"
export TMPDIR="$ROOT/offline-prep/tmp"
mkdir -p "$TMPDIR"

echo "$(date) bootstrap(start) begin TMPDIR=$TMPDIR" >> "$LOG"

got=$(sha256sum "$TRTLLM_WHEEL" | awk '{print $1}')
if [ "$got" != "$TRTLLM_SHA" ]; then
  echo "$(date) trtllm wheel SHA mismatch got=$got" >> "$LOG"
  exit 1
fi

for i in $(seq 1 180); do
  if "$VENV/bin/python" -c "import torch; assert torch.__version__.startswith('2.14')" 2>/dev/null; then
    echo "$(date) torch OK $("$VENV/bin/python" -c 'import torch;print(torch.__version__)')" >> "$LOG"
    break
  fi
  echo "$(date) waiting torch ($i)" >> "$LOG"
  sleep 30
done

"$VENV/bin/python" -c "import torch" 2>/dev/null || { echo "$(date) torch never became importable, abort" >> "$LOG"; exit 1; }

echo "$(date) installing tensorrt_llm 1.3.0rc29" >> "$LOG"
for attempt in $(seq 1 60); do
  if "$VENV/bin/pip" install --find-links "$WHEELS" --retries 20 --timeout 300 "$TRTLLM_WHEEL" >> "$LOG" 2>&1; then
    echo "$(date) pip exit ok attempt $attempt" >> "$LOG"
    break
  fi
  echo "$(date) trtllm install attempt $attempt failed, retry" >> "$LOG"
  sleep 15
done

if "$VENV/bin/python" -c "import tensorrt_llm; print('TRTLLM_VERSION', tensorrt_llm.__version__)" >> "$LOG" 2>&1; then
  echo "$(date) TRTLLM INSTALL OK" >> "$LOG"
else
  echo "$(date) TRTLLM IMPORT FAILED" >> "$LOG"
fi
echo "$(date) bootstrap(end)" >> "$LOG"
