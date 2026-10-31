#!/bin/bash
# Build all Docker images for RAG services.
# Run from: Work_Credit-RAG_Phase1 (parent repo root)
#
# Usage:
#   bash Work_RAG-Server-Setup/deploy/docker/build-all.sh [registry]
#
# Example:
#   bash Work_RAG-Server-Setup/deploy/docker/build-all.sh local-h200:5000

set -euo pipefail

REGISTRY="${1:-local-h200:5000}"
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
TAG="${SHA}"

# Proxy args (corporate Squid: 192.168.203.2:3128)
HTTP_PROXY="${HTTP_PROXY:-http://192.168.203.2:3128}"
HTTPS_PROXY="${HTTPS_PROXY:-http://192.168.203.2:3128}"
NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}"

echo "=== RAG Docker Image Build ==="
echo "Registry: $REGISTRY"
echo "Tag: $TAG"
echo "Proxy: $HTTP_PROXY"
echo ""

# Ensure Docker is available
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon not available. Start Docker first."
    exit 1
fi

# Ensure NVIDIA container toolkit for GPU builds
if ! docker info | grep -i nvidia >/dev/null 2>&1; then
    echo "WARNING: NVIDIA container toolkit not detected. Gemma builds may fail at runtime."
fi

# ── Services in Work_Credit-RAG_Phase1 (submodules) ──
echo "[1/7] Building KB (port 8000)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-kb:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.kb \
    .

echo "[2/7] Building Guardrails (port 8200)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-guardrails:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.guardrails \
    .

echo "[3/7] Building Orchestrator (port 8100)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-orchestrator:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.orchestrator \
    .

echo "[4/7] Building Tracing (port 3000)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-tracing:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.tracing \
    .

# ── Services in Work_RAG-Server-Setup ──
echo "[5/7] Building LLM Manager (port 9000)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-manager:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.manager \
    ../Work_RAG-Server-Setup

echo "[6/7] Building Gemma (ports 8080-8084)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-gemma:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.gemma \
    ../Work_RAG-Server-Setup

echo "[7/7] Building Embed (ports 8001-8003)..."
docker build \
    --build-arg HTTP_PROXY="${HTTP_PROXY}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY}" \
    --build-arg NO_PROXY="${NO_PROXY}" \
    -t "${REGISTRY}/rag-embed:${TAG}" \
    -f ../Work_RAG-Server-Setup/deploy/docker/Dockerfile.embed \
    ../Work_RAG-Server-Setup

echo ""
echo "=== Build Complete ==="
echo "Images tagged with ${REGISTRY}/*:${TAG}"
echo ""
echo "Next steps:"
echo "  1. Push images: docker push ${REGISTRY}/rag-kb:${TAG} (etc.)"
echo "  2. Test on alt ports: docker compose -f Work_RAG-Server-Setup/deploy/docker/docker-compose.test.yml up -d"
echo "  3. Run E2E via Open WebUI"
echo "  4. Cutover to prod ports: docker compose -f Work_RAG-Server-Setup/deploy/docker/docker-compose.prod.yml up -d"
