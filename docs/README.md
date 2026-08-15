> **Date:** 2026-08-15 · **Machine:** `ai-gpu1` · **Repo-root:** `/splunk-data/v1/Work_RAG-Server-Setup`
> Everything below is verified live on the host as of this date.

# RAG Server — Documentation Index

A self-hosted RAG + inference platform on 2× NVIDIA H200 NVL (281 GiB total VRAM), 1 TB RAM,
with a full suite of docker-backed vector databases, observability, an OpenAI-compatible inference
layer (vLLM + llama.cpp), and a resilient offline model-download daemon.

## Quick facts

| | |
|---|---|
| **Hosts / gateway** | `192.168.96.82` and `192.168.177.10`, UI gateway `:8088` (nginx) |
| **Chat OpenAI API** | `http://192.168.96.82:8000/v1` (vLLM) and `:8080/v1` (llama.cpp) |
| **Embeddings** | `http://192.168.96.82:8001` (`bge-small`, dim 384) |
| **Docker** | 9 images, 9 running containers, `restart=unless-stopped` |
| **Live models** | Qwen2.5-7B (vLLM + llama.cpp), plus ready small models (see Models page) |
| **Downloads** | 72B Qwen2.5 (in-flight), Qwen3-30B-A3B, Gemma-3-27B, Nemotron 49B/253B, MiniMax-M3, GLM-5.2, Kimi K3, DeepSeek-V4-Flash (daemonized) |
| **Disk** | `/splunk-data` 5.5 T free; root freed to 49% after docker-containerd relocation |

## Report & guides

| Document | Contents |
|---|---|
| **[`REPORT.md`](REPORT.md)** | Master system report & runbook (services, images, env, known issues) |
| [`guides/01-environment.md`](guides/01-environment.md) | Hardware, OS, network, GPU topology, disk |
| [`guides/02-engines-and-libraries.md`](guides/02-engines-and-libraries.md) | Inference engines + installed library inventory |
| [`guides/03-services-and-endpoints.md`](guides/03-services-and-endpoints.md) | Full port/endpoint map |
| [`guides/04-docker-and-storage.md`](guides/04-docker-and-storage.md) | Docker images, containers, storage relocation |
| [`guides/05-models-catalog.md`](guides/05-models-catalog.md) | Models downloaded / downloading / planned |
| [`guides/06-model-runnability-fit.md`](guides/06-model-runnability-fit.md) | VRAM/RAM fit matrix — what can run on this box |
| [`guides/07-download-daemon.md`](guides/07-download-daemon.md) | The `rag-dl` download daemon & ops |
| [`guides/08-sample-projects.md`](guides/08-sample-projects.md) | Sample projects → dedicated env + self-hosted endpoint |
| [`guides/09-reboot-runbook.md`](guides/09-reboot-runbook.md) | Bring everything back up after a reboot |
| **[`findings.md`](findings.md)** | Discoveries & gotchas (all workarounds) |
| [`history/`](history/README.md) | Per-session installation history (001–005) |
| [`plan.md`](plan.md) | Deliverable plan & progress |

## Live status snapshot (15 Aug 2026)

- **Docker:** all 9 containers `Up`; open-webui `healthy`.
- **Inference:** vLLM serves `qwen2.5:7b-vllm` (~54 tok/s), llama.cpp serves `qwen2.5:7b`.
- **Downloads:** daemon `rag-dl.service` active, resuming the 72B (Q4 + Q8 parts), then the
  frontier-MoE catalog sequentially (shared proxy ≈230 KB/s — patience required).
- **Vector stores:** milvus, qdrant (`rag_docs` green, 0 points — ingestion pending), pgvector, redis.

## Running the dashboard

```bash
offline-prep/venv/bin/python3.12 scripts/progress_report.py --watch   # or --once
```