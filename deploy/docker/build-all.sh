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

echo "=== RAG Docker Image Build ==="
echo "Registry: $REGISTRY"
echo "Tag: $TAG"
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

# Build contexts
PARENT_CTX="."                              # Work_Credit-RAG_Phase1 (has submodules)
SETUP_CTX="../Work_RAG-Server-Setup"        # Work_RAG-Server-Setup (has Dockerfiles + offline-prep)
DOCKER_DIR="$SETUP_CTX/deploy/docker"

# ── Services in Work_Credit-RAG_Phase1 (submodules) ──
echo "[1/7] Building KB (port 8000)..."
docker build \
    -t "${REGISTRY}/rag-kb:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.kb" \
    "$PARENT_CTX"

echo "[2/7] Building Guardrails (port 8200)..."
docker build \
    -t "${REGISTRY}/rag-guardrails:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.guardrails" \
    "$PARENT_CTX"

echo "[3/7] Building Orchestrator (port 8100)..."
docker build \
    -t "${REGISTRY}/rag-orchestrator:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.orchestrator" \
    "$PARENT_CTX"

echo "[4/7] Building Tracing (port 3000)..."
docker build \
    -t "${REGISTRY}/rag-tracing:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.tracing" \
    "$PARENT_CTX"

# ── Services in Work_RAG-Server-Setup ──
echo "[5/7] Building LLM Manager (port 9000)..."
docker build \
    -t "${REGISTRY}/rag-manager:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.manager" \
    "$SETUP_CTX"

echo "[6/7] Building Gemma (ports 8080-8084)..."
docker build \
    -t "${REGISTRY}/rag-gemma:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.gemma" \
    "$SETUP_CTX"

echo "[7/7] Building Embed (ports 8001-8003)..."
docker build \
    -t "${REGISTRY}/rag-embed:${TAG}" \
    -f "$DOCKER_DIR/Dockerfile.embed" \
    "$SETUP_CTX"

echo ""
echo "=== Build Complete ==="
echo "Images tagged with ${REGISTRY}/*:${TAG}"
echo ""
echo "Next steps:"
echo "  1. Test on alt ports: docker compose -f Work_RAG-Server-Setup/deploy/docker/docker-compose.test.yml up -d"
echo "  2. Mount host site-packages: -v /splunk-data/v1/Work_RAG-Server-Setup/offline-prep/venv/lib/python3.12/site-packages:/host-site-packages:ro"
echo "  3. Run E2E via Open WebUI"
echo "  4. Cutover to prod ports: docker compose -f Work_RAG-Server-Setup/deploy/docker/docker-compose.prod.yml up -d"
