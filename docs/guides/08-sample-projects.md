# Guide 08 — Sample Projects → Dedicated Env + Self-Hosted Endpoint

> [Back to index](../README.md)

Four upstream projects are cloned under `offline-prep/sample-projects/` (upstream repos, do not
edit their internals):

| Project | Dir | Size | Kind |
|---|---|---|---|
| AnythingLLM | `offline-prep/sample-projects/anything-llm` | 166 M | full-stack RAG UI (node + python collector) |
| Dify | `offline-prep/sample-projects/dify` | 649 M | workflow-oriented RAG/LangGraph platform |
| RAGFlow | `offline-prep/sample-projects/ragflow` | 266 M | deep-document RAG platform |
| LightRAG | `offline-prep/sample-projects/lightrag` | 148 M | light-weight pure-python RAG |

## Self-hosted endpoints they all connect to

| Endpoint | URL | What | Key |
|---|---|---|---|
| Chat LLM (OpenAI-compatible) | `http://192.168.96.82:8000/v1` (vLLM) · `:8080/v1` (llama.cpp) | `qwen2.5:7b-vllm` / `qwen2.5:7b` | any string, e.g. `local` |
| Embeddings | `http://192.168.96.82:8001` | `bge-small`, dim 384 → matches `rag_docs` collections | — |
| Vector store | `http://192.168.96.82:16333` (qdrant) · `:19530` (milvus) · `:15432` (pgvector) | `rag_docs` | — |

Containers reach the host via `http://host.docker.internal:8000` (docker `host-gateway`, already
set in the monitoring compose). Host processes use the plain IPs.

## Per-project runbook (each in its own dedicated env)

### 1. LightRAG — fastest, no containers

```bash
cd offline-prep/sample-projects/lightrag
source /splunk-data/v1/Work_RAG-Server-Setup/offline-prep/sample-projects/lightrag/venv/bin/activate  # deps pending
export OPENAI_API_KEY=local
export OPENAI_API_BASE=http://192.168.96.82:8000/v1
python -m lightrag ...            # or the bundled docker-compose-full.yml for the full stack
```

Best choice to validate the pipeline quickly (single venv, no docker).

### 2. AnythingLLM — docker compose

```bash
cd offline-prep/sample-projects/anything-llm/docker
# configure .env: LLM_PROVIDER=openai generic, OPENAI_BASE_URL=http://host.docker.internal:8000/v1
docker compose up -d
```

In Settings → LLM provider pick "Generic OpenAI", point at the host endpoint, model `qwen2.5:7b-vllm`;
embedding provider → `:8001`.

### 3. RAGFlow — heavier, own stack

```bash
cd offline-prep/sample-projects/ragflow
# build helpers: docker/build.sh, then docker compose up -d (needs its images)
# Admin → Add model → OpenAI-compatible → base_url http://host.docker.internal:8000/v1
```

### 4. Dify — docker compose multi-service

```bash
cd offline-prep/sample-projects/dify && docker compose up -d   # api, web, worker, redis, postgres
# Settings → Models → Add model → "OpenAI-API-compatible" → base_url http://host.docker.internal:8000/v1
```

## Why 4 projects?

They represent different RAG philosophies on the SAME model endpoint:

- LightRAG — nimble graph/entity-based retrieval, minimal footprint.
- AnythingLLM — easy team UI, "chat with your docs".
- RAGFlow — deep chunking/OCR-heavy document parsing.
- Dify — visual workflows/agents, tool + app orchestration.

All are interchangeable downstream of the shared self-hosted OpenAI-compatible layer, so the
choice is UX/workflow, not model wiring.