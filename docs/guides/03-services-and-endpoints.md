# Guide 03 — Services, Ports & Endpoints

> [Back to index](../README.md)

All services bind `0.0.0.0` → reachable on both host IPs (`192.168.96.82`, `192.168.177.10`).
`GATEWAY = http://192.168.96.82:8088` (nginx). Test locally with `curl --noproxy '*'`.

| Service | Port(s) | Gateway path | What it is |
|---|---|---|---|
| nginx gateway | `:8088` | `/` | landing page (`deploy/gateway/index.html`) |
| **vLLM OpenAI API** | `:8000` | `/vllm/` | `qwen2.5:7b-vllm`; `/v1/models`, `/v1/chat/completions`, `/metrics` |
| **llama.cpp OpenAI API** | `:8080` | `/llama/` | `qwen2.5:7b`; chat + stream + `/v1/models` |
| **Embeddings API** | `:8001` | `/embeddings/` | `local-embed` (bge-small, dim 384) |
| **Open WebUI** | `:13000` | `/webui/` | chatbot UI, wired to llama.cpp, `WEBUI_AUTH=false` |
| Grafana | `:13001` | `/grafana/` | admin/admin, anon view on, provisioned Prom datasource |
| Prometheus | `:19090` | `/prometheus/` | scrapes vllm `:8000/metrics`, gpu `:9101`, node `:19100` |
| otel-collector | `:14317` gRPC, `:14318` HTTP, `:19092` prom | — | OTLP intake → batch → debug + prometheus |
| GPU metrics exporter | `:9101/metrics` | — | host `nvidia-smi` → prometheus (`gpu_utilization_percent`, etc.) |
| Milvus | `:19530` gRPC, `:19091` metrics | `/milvus/` | collection `rag_docs` (dim 384, IVF_FLAT / COSINE) |
| Qdrant | `:16333` REST, `:16334` gRPC | `/qdrant/` | collection `rag_docs` (dim 384, cosine) |
| pgvector | `:15432` | — | ext `vector 0.8.6`, table `rag_docs` (embedding vector(384)) |
| Redis | `:16379` | — | key/value cache |
| netdata-style node exporter | `:19100` | — | host metrics (container) |

## Docker bridge ports ↔ host mapping

| Container (image) | Host port → container port |
|---|---|
| `webui-test` (open-webui) | `13000 → 8080` |
| `milvus-test` | `19530 → 19530`, `19091 → 9091` |
| `qdrant-test` | `16333 → 6333`, `16334 → 6334` |
| `pgvector-test` | `15432 → 5432` |
| `redis-test` | `16379 → 6379` |
| `prometheus-test` | `19090 → 9090` |
| `grafana-test` | `13001 → 3000` |
| `node-exporter-test` | `19100 → 9100` (pid: host) |
| `otel-test` | `14317 → 4317`, `14318 → 4318`, `19092 → 9091` |

## Smoke checks

```bash
curl --noproxy '*' http://localhost:13000/                    # webui 200
curl --noproxy '*' http://localhost:8000/v1/models            # vllm model list
curl --noproxy '*' http://localhost:8080/v1/models            # llama.cpp model list
curl --noproxy '*' http://localhost:16333/collections/rag_docs # qdrant green
```

> Historical backend choices for RAG: qdrant (`rag_docs`, used by the pipeline), milvus, pgvector —
> the pipeline targets **qdrant** as primary; the others are staged/verified as density-independent
> options.