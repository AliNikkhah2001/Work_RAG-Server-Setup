# Containerization Migration Plan — Work_RAG-Server-Setup (H200 Production)

**Repository:** `Work_RAG-Server-Setup` (GitHub: `AliNikkhah2001/Work_RAG-Server-Setup`)  
**Branch:** `main`  
**Target Host:** 2× H200 NVL (ai-gpu1), Docker available, Jenkins self-hosted as root  
**Registry:** Local H200 Docker registry  
**Date:** 2026-10-31  
**Status:** Approved for Phase 1 implementation

---

## 1. Executive Summary

All 8 production services currently run as bare host processes (venvs) or individual Docker containers on the H200 server. This plan containerizes every service **without breaking any running process**, using a side-by-side validation approach:

1. Build Docker images from source (no containers started yet).
2. Run each container on an **alternate port** to validate it works independently.
3. Run end-to-end integration test through Open WebUI (port 13000) pointing to containerized backends on alt ports.
4. Only after E2E passes, perform **per-service cutover**: stop host process, start container on the **same production port**.
5. Rollback per service if health check fails (host venv remains intact).

**Zero services are stopped or modified during Phases 1–3.** Production traffic is unaffected until Phase 4 cutover.

---

## 2. Current Production Inventory (Do Not Touch)

| # | Service | Port | Process Type | Entry Point | GitHub Repo |
|---|---------|------|--------------|-------------|-------------|
| 1 | Gemma backend ×5 | 8080–8084 | host venv + `gemma_supervisor.sh` | `scripts/services/llama_chat_server.py` | `Work_RAG-Server-Setup` |
| 2 | LLM Manager (gateway) | 9000 | host venv | `llm_inference_manager/app.py` | `Work_RAG-Server-Setup` |
| 3 | Embedding ×3 | 8001–8003 | host venv | `scripts/services/embed_server.py` | `Work_RAG-Server-Setup` |
| 4 | KB Retrieval | 8000 | host venv | `kb_manager/web/app.py` (submodule) | `Work_RAG-KB` |
| 5 | Guardrails | 8200 | host venv | `work_rag_guardrails.api:create_app` (submodule) | `Work_RAG-Guardrails` |
| 6 | Orchestrator (LangGraph) | 8100 | host venv | `work_rag_orchestrator.api:create_app` (submodule) | `Work_RAG-Orchestrator` |
| 7 | Tracing fallback | 3000 | host venv | `components/tracing/app.py` | `Work_Credit-RAG_Phase1` |
| 8 | Open WebUI | 13000 | Docker (already containerized) | `ghcr.io/open-webui/open-webui:main` | — |
| 9 | Redis (cache) | 16379 | Docker (already running) | `redis:7-alpine` | — |
| 10 | postgres + pgvector | 5432 | system cluster | system install | — |

**Constraint:** Ports 8000, 8001–8003, 8080–8084, 8100, 8200, 9000, 13000, 16379, 5432, 3000 remain unchanged in the final state.

---

## 3. Migration Architecture

### 3.1 Layer Separation

```
Production Layer (served & deployed)
├── api/ (thin wrappers → components/)         ← Work_Credit-RAG_Phase1
├── components/ (submodules, pinned commits)   ← Work_RAG-KB, Guardrails, Orchestrator, Tracing
├── deploy/ (start/stop/health scripts)        ← Work_RAG-Server-Setup
├── Dockerfiles (per service)                  ← Work_RAG-Server-Setup
└── docker-compose.prod.yml                    ← Work_RAG-Server-Setup

Agent State Layer (agent only)
└── agent-state/                                ← ICS_ChatBot_agent-state

Development Layer (NOT for production)
└── dev/ (patches, tests, investigation)        ← Work_Credit-RAG_Phase1
```

### 3.2 Container-to-Service Mapping

| Container Image | Source Repo | Port | GPU | Volume Mounts |
|-----------------|-------------|------|-----|---------------|
| `rag-kb` | `Work_RAG-KB` | 8000 | No | `data/`, `offline-prep/models/huggingface` |
| `rag-guardrails` | `Work_RAG-Guardrails` | 8200 | No | `kb/hurtlex_allowlist.json`, `policies/` |
| `rag-orchestrator` | `Work_RAG-Orchestrator` | 8100 | No | `src/work_rag_orchestrator/` |
| `rag-tracing` | `Work_Credit-RAG_Phase1` | 3000 | No | `components/tracing/` |
| `rag-manager` | `Work_RAG-Server-Setup` | 9000 | No | `manager.db`, `logs/` |
| `rag-gemma-8080` … `rag-gemma-8084` | `Work_RAG-Server-Setup` | 8080–8084 | Yes (H200) | `offline-prep/models/` (GGUF) |
| `rag-embed-8001` … `rag-embed-8003` | `Work_RAG-Server-Setup` | 8001–8003 | No | `offline-prep/models/huggingface` |
| `open-webui` | Docker Hub | 13000 | No | `/app/backend/data` |

---

## 4. Phase-by-Phase Execution Plan

### Phase 1: Image Build & Alt-Port Validation (No Production Impact)

**Goal:** Build all Docker images and verify each starts independently on alternate ports.

**Alt ports for testing** (do not collide with production):

| Service | Prod Port | Test Port |
|---------|-----------|-----------|
| KB | 8000 | 8100 |
| Guardrails | 8200 | 8201 |
| Orchestrator | 8100 | 8101 |
| Tracing | 3000 | 3001 |
| Manager | 9000 | 9001 |
| Gemma ×5 | 8080–8084 | 8085–8089 |
| Embed ×3 | 8001–8003 | 8004–8006 |

**Steps:**
1. Write `Dockerfile` for each service in `deploy/docker/`
2. Build images: `docker build -t local-registry:5000/rag-<service>:<sha>`
3. Run each container on its test port with `docker run -d -p <test>:<internal> ...`
4. Verify `curl http://127.0.0.1:<test-port>/health` returns `{"status":"ok"}`
5. Verify environment variables, volume mounts, and model paths resolve correctly

**Success criteria:** All 8 container images build and respond to `/health` on test ports.

### Phase 2: End-to-End Integration Test on Alt Ports

**Goal:** Verify the full chain works containerized before touching production ports.

**Test chain:**
```
Open WebUI (:13000) → Orchestrator container (:8101) → Guardrails container (:8201) → KB container (:8100) → Gemma container (:8085) → response
```

**Steps:**
1. Temporarily configure Open WebUI `OPENAI_API_BASE_URL=http://127.0.0.1:8101/v1` (test only)
2. Send 3 sample queries via Open WebUI:
   - `SBD1` → expect correct answer with supplement data
   - `MTX1` → expect correct answer with supplement data
   - `shareholders` → expect correct answer
   - generic query → expect clarification (no false entity match)
3. Verify `finish_reason="stop"`, `citations>0`, Persian text, no `<unused>` tokens
4. Verify traces appear in tracing container (`:3001`)
5. Revert Open WebUI config to production orchestrator (`:8100`)

**Success criteria:** All 3 sample queries return correct answers; generic query clarifies. No production process was stopped.

### Phase 3: Jenkins Pipeline Setup

**Goal:** Automate build, test, and deploy via self-hosted Jenkins on H200.

**Jenkins location:** Root user, normal directory (e.g., `/var/lib/jenkins` or `/home/jenkins`)

**Pipeline stages (per service repo):**
1. `checkout` — GitHub repo
2. `lint` — `ruff` (Python), `hadolint` (Dockerfile)
3. `test` — `pytest` on `eval/`
4. `build` — `docker build -t local-registry:5000/rag-<service>:sha-$COMMIT`
5. `push` — `docker push local-registry:5000/rag-<service>:sha-$COMMIT`
6. `deploy-dev` — `docker compose -f docker-compose.test.yml up -d` (alt ports)
7. `e2e-test` — Open WebUI chat test through full chain
8. `deploy-prod` — manual approval; `docker compose -f docker-compose.prod.yml up -d`

**GitHub integration:** Webhooks from GitHub → Jenkins on push/PR to `main`/`develop`.

### Phase 4: Production Cutover (One Service at a Time)

**Goal:** Migrate each service from host process to container on the **same production port**.

**Cutover order (safest first):**

| Order | Service | Port | Rollback |
|-------|---------|------|----------|
| 1 | Tracing | 3000 | Restart host venv |
| 2 | Embed ×3 | 8001–8003 | Restart host venvs |
| 3 | KB Retrieval | 8000 | Restart host venv |
| 4 | Guardrails | 8200 | Restart host venv |
| 5 | Orchestrator | 8100 | Restart host venv |
| 6 | LLM Manager | 9000 | Restart host venv |
| 7 | Gemma ×5 | 8080–8084 | Restart `gemma_supervisor.sh` |

**Per-service cutover steps:**
1. `docker stop` the test container (if still running on alt port)
2. Stop host process: `fuser -k <port>/tcp` or `pkill -f <service>`
3. Start container on production port: `docker run -d -p <port>:<internal> ...`
4. Health check: `curl http://127.0.0.1:<port>/health`
5. If healthy → mark service migrated. If fails → stop container, restart host process immediately.

**Success criteria:** All 7 services running as containers on production ports, Open WebUI E2E passes.

### Phase 5: Decommission Host Venvs (After 24h Stability)

**Goal:** Remove host venv processes once containers are stable.

**Steps:**
1. Verify all services stable for 24 hours (health checks green, no restarts)
2. Stop remaining host venv processes
3. Remove host venvs (optional, keep as backup for 1 week)
4. Update `AGENTS.md` and runbooks to reflect containerized deployment

---

## 5. Dockerfile Specifications (Per Service)

### 5.1 Base Image Strategy
- **CPU services** (KB, Guardrails, Orchestrator, Tracing, Manager): `python:3.11-slim`
- **GPU services** (Gemma ×5): `nvidia/cuda:12.4.1-runtime-ubuntu22.04` + `nvidia-container-toolkit`
- **Embed services**: `python:3.11-slim` (CPU-only sentence-transformers)

### 5.2 Common Dockerfile Pattern

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Non-root user
RUN useradd -m -u 1000 raguser && chown -R raguser:raguser /app
USER raguser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

CMD ["python", "<entry_point>.py"]
```

### 5.3 GPU Dockerfile Pattern (Gemma)

```dockerfile
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-pip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn llama-cpp-python httpx pydantic

COPY scripts/services/llama_chat_server.py ./
COPY offline-prep/models/ ./models/

ENV CUDA_VISIBLE_DEVICES=0
EXPOSE 8080

HEALTHCHECK CMD curl -f http://127.0.0.1:8080/health || exit 1

CMD ["python3", "llama_chat_server.py", "--model", "./models/...", "--port", "8080"]
```

---

## 6. Docker Compose (Production)

`deploy/docker/docker-compose.prod.yml` will orchestrate all containers with:
- Custom network `rag-prod`
- Volume mounts for models, data, logs, manager.db
- Health checks on every service
- `restart: unless-stopped`
- GPU device reservations for Gemma containers
- Proxy env vars (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY=localhost,127.0.0.1`)

---

## 7. Jenkins Integration Details

### 7.1 Jenkins Host
- **User:** root
- **Directory:** `/var/lib/jenkins` (standard) or `/home/jenkins`
- **Port:** 8080
- **Plugins:** Docker Pipeline, GitHub, Pipeline, SSH Agent

### 7.2 Credentials
- GitHub personal access token (for cloning repos)
- Local registry credentials (H200 Docker registry)
- SSH keys (for deploy to H200 if Jenkins runs elsewhere)

### 7.3 Webhook Flow
```
GitHub push/PR → Jenkins webhook → Pipeline job → Build → Test → Push to local registry → Deploy-dev (alt ports) → E2E → Deploy-prod (manual approval)
```

---

## 8. Rollback Plan (Per Service)

If a container fails health check after cutover to production port:

```bash
# Example: KB service on :8000
docker stop rag-kb && docker rm rag-kb
# Host venv still intact — restart it:
cd /splunk-data/v1/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager
source /tmp/kb-venv/bin/activate
nohup python -m uvicorn kb_manager.web.app:app --host 0.0.0.0 --port 8000 &
```

**Maximum downtime per service:** ~30 seconds. No full-system downtime.

---

## 9. Files to Create / Modify

### In `Work_RAG-Server-Setup`:

| File | Purpose |
|------|---------|
| `deploy/docker/Dockerfile.kb` | KB service container |
| `deploy/docker/Dockerfile.guardrails` | Guardrails container |
| `deploy/docker/Dockerfile.orchestrator` | Orchestrator container |
| `deploy/docker/Dockerfile.tracing` | Tracing container |
| `deploy/docker/Dockerfile.manager` | LLM Manager container |
| `deploy/docker/Dockerfile.gemma` | Gemma backend container (×5 instances) |
| `deploy/docker/Dockerfile.embed` | Embed server container (×3 instances) |
| `deploy/docker/docker-compose.test.yml` | Alt-port compose for validation |
| `deploy/docker/docker-compose.prod.yml` | Production compose |
| `deploy/docker/Jenkinsfile` | Pipeline for server-setup services |
| `docs/migration/containerization-report.md` | This document |

### In Component Repos (Jenkinsfiles):

| Repo | File |
|------|------|
| `Work_RAG-KB` | `Jenkinsfile` |
| `Work_RAG-Guardrails` | `Jenkinsfile` |
| `Work_RAG-Orchestrator` | `Jenkinsfile` |
| `Work_Credit-RAG_Phase1` | `Jenkinsfile` (tracing) |

---

## 10. Acceptance Criteria (Before Production Cutover)

| # | Criterion |
|---|-----------|
| 1 | All 8 Docker images build successfully from source |
| 2 | All containers respond to `/health` on test ports |
| 3 | Open WebUI E2E passes on alt ports (3 sample queries + generic clarify) |
| 4 | Jenkins pipeline builds, tests, and pushes images to local registry |
| 5 | Per-service cutover to production ports succeeds with health check green |
| 6 | All 7 services stable on containers for 24 hours |
| 7 | Rollback tested and documented for at least one service |

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Port collision during test | Use alt ports for test; only move to prod ports after host process stopped |
| Container image too large | Multi-stage builds, `python:3.11-slim`, no build tools in runtime |
| Model path mismatch | Mount `offline-prep/models/` at same path inside container |
| Proxy blocks container builds | Set `HTTP_PROXY/HTTPS_PROXY` in Docker build args and Docker daemon config |
| GPU not visible in container | Install `nvidia-container-toolkit`, add `--gpus all` to docker run |
| Host venv broken after cutover | Keep host venvs intact for 1 week as rollback backup |
| Jenkins job fails mid-deploy | Per-service rollback; Jenkins pipeline has health-check gate |

---

## 12. Immediate Next Steps

1. **Approve this plan** ✅ (done)
2. **Create Dockerfiles** in `Work_RAG-Server-Setup/deploy/docker/`
3. **Create test docker-compose** on alt ports
4. **Build and test all images** on alt ports (no production impact)
5. **Run E2E test** via Open WebUI on alt ports
6. **Set up Jenkins** on H200 (root user)
7. **Create Jenkinsfiles** in all repos
8. **Perform per-service cutover** to production ports
9. **Verify 24h stability**, then decommission host venvs

---
