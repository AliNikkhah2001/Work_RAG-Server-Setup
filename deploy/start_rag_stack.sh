#!/usr/bin/env bash
# Start the RAG stack on the H200 host with the CORRECT cross-service wiring.
#
# Why this exists: several services silently fall back to broken defaults when
# started without env (KB -> empty SQLite, Orchestrator -> unsloth model that
# the manager does not host, no embed server on :8003 so the subspace
# classifier never runs). This script pins the known-good configuration.
#
# Idempotent: a service is only started when its port is not already listening.
# Usage: ./start_rag_stack.sh [--force]
set -uo pipefail

FORCE="${1:-}"
VENV=/tmp/kb-venv/bin/python
ROOT=/splunk-data/v1
PHASE1=$ROOT/Work_Credit-RAG_Phase1/components
KB_DIR=$PHASE1/knowledgebase/kb-manager
ORCH_DIR=$PHASE1/orchestrator
GR_DIR=$PHASE1/guardrails
MG_DIR=$ROOT/Work_RAG-Server-Setup/llm_inference_manager
EMBED=$ROOT/Work_RAG-Server-Setup/scripts/services/embed_server.py

# Shared model cache. HF_HUB_CACHE must be the "hub" subdir (not HF_HOME).
export HF_HOME=/root/.cache/huggingface
export HF_HUB_CACHE=/root/.cache/huggingface/hub
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
# Localhost must never go through the corporate Squid proxy.
export no_proxy=localhost,127.0.0.1
export NO_PROXY=localhost,127.0.0.1

listening() { ss -ltn 2>/dev/null | grep -q ":$1\b"; }

start_if_down() {
  local port=$1 name=$2; shift 2
  if listening "$port" && [ "$FORCE" != "--force" ]; then
    echo "[skip] $name already on :$port"
    return 0
  fi
  echo "[start] $name :$port"
  setsid bash -c "$*" </dev/null >/tmp/${name}.log 2>&1 &
  disown
}

# 1) Manager gateway (:9000) - routes gemma-4-31b to the live Triton/TRT or
#    llama.cpp backend (health-aware retry inside app.py).
cd "$MG_DIR" || exit 1
start_if_down 9000 manager \
  "cd '$MG_DIR' && exec '$VENV' -m uvicorn app:app --host 0.0.0.0 --port 9000 --log-level info"

# 2) KB (:8000) - MUST use the pgvector corpus, otherwise it silently opens an
#    empty ./data/kb_test.db and every answer becomes "not found".
#    Also drop stale kb:search cache entries: they are keyed only by
#    query|top_k|boost and would keep serving empty results cached while the
#    DB was empty.
if ! listening 8000 || [ "$FORCE" = "--force" ]; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^redis-test$'; then
    docker exec redis-test redis-cli --scan --pattern 'kb:search:*' 2>/dev/null \
      | while read -r k; do docker exec redis-test redis-cli DEL "$k" >/dev/null; done
  fi
  start_if_down 8000 kb \
    "cd '$KB_DIR' && export KB_DB_MODE=pgvector \
       KB_DB_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/kb_manager' \
       KB_WEB_HOST=0.0.0.0 KB_WEB_PORT=8000 \
       KB_EMBED_MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2' \
       KB_EMBED_DIM=384 KB_EMBED_DEVICE=cuda:1 \
       KB_RERANKER_MODEL='BAAI/bge-reranker-v2-m3' KB_RERANKER_DEVICE=cuda:1 \
       KB_REDIS_URL='redis://127.0.0.1:16379/0' KB_REDIS_TTL=600 && \
     exec '$VENV' run_server.py"
fi

# 3) Embedding service (:8003) - used by the orchestrator subspace
#    classifier/ambiguity scorer. Without it the classifier silently
#    degrades to source="fallback".
start_if_down 8003 embed8003 \
  "cd '$ROOT' && exec '$VENV' '$EMBED' \
     --model 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2' \
     --model-id 'paraphrase-multilingual-MiniLM-L12-v2' --port 8003 --host 0.0.0.0"

# 4) Guardrails (:8200). The LLM judge has its OWN defaults that point at the
#    Vast model id and :18000 - both wrong here; a failing judge fails CLOSED
#    and refuses benign questions with "policy_violation".
start_if_down 8200 guardrails \
  "cd '$GR_DIR' && PYTHONPATH=./src \
     UPSTREAM_LLM_BASE_URL=http://127.0.0.1:9000/v1 \
     UPSTREAM_LLM_MODEL=gemma-4-31b \
     GUARD_JUDGE_MODEL=gemma-4-31b \
     exec '$VENV' -m uvicorn \
       work_rag_guardrails.api:create_app --factory --host 0.0.0.0 --port 8200 --log-level info"

# 5) Orchestrator (:8100) - UPSTREAM_LLM_MODEL must be a model the manager
#    actually hosts, otherwise guardrails answers "Unable to reach the model
#    service" (default config value is a Vast-only unsloth id).
start_if_down 8100 orchestrator \
  "cd '$ORCH_DIR' && PYTHONPATH=./src \
     UPSTREAM_LLM_MODEL=gemma-4-31b \
     KB_BASE_URL=http://127.0.0.1:8000 \
     GUARDRAILS_BASE_URL=http://127.0.0.1:8200 \
     OBSERVABILITY_URL=http://127.0.0.1:3000 \
     exec '$VENV' -m uvicorn work_rag_orchestrator.api:create_app --factory \
       --host 0.0.0.0 --port 8100 --log-level info"

sleep 8
echo
echo "--- readiness ---"
for p in 9000 8000 8003 8200 8100; do
  printf ":%s " "$p"
  case $p in
    8000|8003|8200|8100) curl -s --noproxy '*' -m 5 "http://127.0.0.1:$p/health" | head -c 120 ;;
    9000) curl -s --noproxy '*' -m 5 "http://127.0.0.1:$p/health" | head -c 120 ;;
  esac
  echo
done
