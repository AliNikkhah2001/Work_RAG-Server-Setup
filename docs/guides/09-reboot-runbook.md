# Guide 09 — Reboot Runbook

> [Back to index](../README.md)

Cleanest sequence to bring this host fully back up. **Order matters** (containerd before docker,
databases before UIs, models daemon last).

## 1. Containerd + Docker (the storage-relocation proof)

```bash
systemctl start containerd
systemctl start docker
docker info --format '{{.DockerRootDir}} images={{.Images}} containers={{.Containers}}'
# expect: /splunk-data/v1/docker-data  images=9  containers=9
```

## 2. Data-plane containers (all have restart=unless-stopped)

```bash
docker start webui-test milvus-test pgvector-test qdrant-test redis-test \
            prometheus-test grafana-test node-exporter-test otel-test
docker ps        # expect all 9 "Up"
```

## 3. Native inference engines

```bash
# vLLM  (OpenAI API :8000)  — served model qwen2.5:7b-vllm
./offline-prep/venv/bin/python3.12 scripts/services/vllm_server.sh   # (per its flags)

# llama.cpp (:8080) + embeddings (:8001) + GPU metrics (:9101)
./offline-prep/venv/bin/python3.12 scripts/services/llama_chat_server.py \
  --model offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --port 8080 --n-ctx 8192 --n-gpu-layers -1 --model-id qwen2.5:7b
# python scripts/services/embed_server.py   (port 8001)
# python scripts/services/gpu_metrics_exporter.py  (port 9101)
```

## 4. Gateway (nginx) — expose everything behind :8088

```bash
nginx -s reload          # /etc/nginx/sites-available/rag-gateway
curl --noproxy '*' -s -o /dev/null -w '%{http_code}\n' http://localhost:8088/   # 200
```

## 5. Downloads daemon

```bash
systemctl enable --now rag-dl.service     # auto-starts on boot and resumes partials
systemctl status rag-dl
```

## 6. Verify

```bash
cd /splunk-data/v1/Work_RAG-Server-Setup
offline-prep/venv/bin/python3.12 scripts/progress_report.py --once   # services + models dashboard
df -h / /splunk-data        # root 49%, /splunk-data 5.5 T free
```

## Reboot checklist quick wins

- Firewall is inactive (all ports open) — no ufw rules to re-add.
- Proxies are already persistent via `proxy_setup.sh`; the download daemon exports its own proxy env.
- If docker ever shows the old `/ai-gpu1` data-root, re-verify `daemon.json` + the
  `/var/lib/containerd` symlink (see Guide 04).
- prometheus stays on tag 2.52.0 (2.53.x SIGBUS-crashes in docker on this host).