# Guide 04 — Docker Images, Containers & Storage

> [Back to index](../README.md)

## Images present (9)

```
ghcr.io/open-webui/open-webui:main        7.16 GB   (chat UI)
milvusdb/milvus:latest                    3.93 GB   (vector db)
pgvector/pgvector:pg16                    621 MB    (postgres + pgvector)
qdrant/qdrant:latest                      275 MB    (vector db)
redis:7-alpine                             57.8 MB
grafana/grafana:11.2.0                     635 MB
prom/prometheus:v2.52.0                    382 MB    (do NOT go to 2.53.x — SIGBUS in docker)
prom/node-exporter:v1.8.1                   38.2 MB
otel/opentelemetry-collector-contrib:0.105.0 334 MB
```

Saved importable tars of the 5 core images live in `offline-prep/docker-images/*.tar`.

## Running containers (9, all `restart=unless-stopped`)

`webui-test`, `milvus-test`, `pgvector-test`, `qdrant-test`, `redis-test`,
`prometheus-test`, `grafana-test`, `node-exporter-test`, `otel-test`.

## Documented gaps

- `vllm/vllm-openai:latest`, `nvidia/cuda:12.8.0-runtime-ubuntu22.04` — pulls never succeeded
  through the proxy; **vLLM runs natively**, so the vLLM image is optional.
- `pghistory` postgres extension not installed.

## Storage relocation (root-disk fix — done)

Docker kept two data-roots on the root partition; both moved off-root:

- `/etc/docker/daemon.json` → `"data-root": "/splunk-data/v1/docker-data"` (proxies block preserved)
- `/var/lib/containerd` is a **symlink** → `/splunk-data/v1/containerd-data`
  (this held the real bulk: ~13 G of overlayfs + content; the docker dir was only ~60 M of metadata)

Old `/ai-gpu1/v1/{containerd-data,docker-data}` and `/var/lib/containerd.bak` were removed after a
verified plain `rsync -a` (file count matched source exactly: 109044). Result: root went
**100% → 49% used** (~24 G free).

## Restart order (docker is secondary to containerd)

```bash
systemctl start containerd && systemctl start docker
docker info --format '{{.DockerRootDir}} images={{.Images}} containers={{.Containers}}'   # expect /splunk-data/v1/docker-data, 9, 9
docker start webui-test milvus-test pgvector-test qdrant-test redis-test prometheus-test grafana-test node-exporter-test otel-test
```

## Provenace of the `-test` suffix

Containers follow the `*-test` naming convention used by the initial bring-up scripts
(`deploy/recreate_webui.sh`, `deploy/docker-compose.yml`, `deploy/monitoring/docker-compose.yml`).