#!/usr/bin/env bash
set -euo pipefail

# Start LightRAG server wired to the local data plane.
# LLM    -> llama.cpp OpenAI endpoint      (localhost:8080/v1)
# Embed  -> the embeddings server          (localhost:8001/v1)
# Uses the lightrag venv; requires `pip install -e .` done first.
#
#   ./lightrag_run.sh [llm_port] [llm_model] [embed_port]

HERE="$(cd "$(dirname "$0")/.." && pwd)"
LLM_PORT="${1:-8080}"
LLM_MODEL="${2:-qwen2.5:7b}"
EMBED_PORT="${3:-8001}"

LIGHTRAG_DIR="${HERE}/offline-prep/sample-projects/lightrag"
LIGHT_VENV="${LIGHTRAG_DIR}/.venv"

if [ ! -x "${LIGHT_VENV}/bin/python" ]; then
  echo "ERROR: lightrag venv not found at ${LIGHT_VENV} (run pip install -e . first)"
  exit 1
fi

export LLM_BINDING=openai
export LLM_BINDING_HOST="http://127.0.0.1:${LLM_PORT}/v1"
export LLM_BINDING_API_KEY=local
export LLM_MODEL="${LLM_MODEL}"

export EMBEDDING_BINDING=openai
export EMBEDDING_BINDING_HOST="http://127.0.0.1:${EMBED_PORT}/v1"
export EMBEDDING_BINDING_API_KEY=local
export EMBEDDING_MODEL=local-embed
export EMBEDDING_MAX_TOKEN_SIZE=512

export RAG_STORAGE_DIR="${LIGHTRAG_DIR}/rag_storage"
export RAG_WORKING_DIR="${RAG_STORAGE_DIR}"
export LIGHTRAG_PORT=9621
export LIGHTRAG_APP_ENV=production
export SCARF_NO_ANALYTICS=true
export DO_NOT_TRACK=true

echo "lightrag-server : LLM=${LLM_BINDING_HOST} model=${LLM_MODEL}  embed=${EMBEDDING_BINDING_HOST}"
echo "                 storage=${RAG_STORAGE_DIR}"
mkdir -p "${RAG_STORAGE_DIR}"

exec "${LIGHT_VENV}/bin/python" -m lightrag.api.lightrag_server \
  --host 0.0.0.0 --port "${LIGHTRAG_PORT}"
