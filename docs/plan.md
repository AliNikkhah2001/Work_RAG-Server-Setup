# Plan Deliverables

Machine-parseable checklist (the progress dashboard reads the `[x]`/`[ ]` markers).
Update these as work completes.

**Overall: `[ ]` — Setup RAG dev/prod system on H200 and run+test the sample repos.**

## P0 — Stabilize environment ✅
- [x] Fix stale `BASE_DIR` in `offline_prepare_cli.py` (now derives from `__file__`)
- [x] Repair venv shebangs + activate scripts (dead `/ai-gpu1/...` → `/splunk-data/...`)
- [x] Resolve numpy/scipy conflict (scipy 1.18.0 → 1.13.1; numpy stays 1.26.4)
- [x] Baseline verified: 5 docker containers up, venv imports OK, proxy active
- [x] Docs updated (`docs/history/003`)

## P1 — Complete model set
- [x] Qwen2.5-7B Q4_K_M downloaded (4.68 GB) + llama.cpp validated
- [ ] Llama-3.2-3B Q4_K_M downloaded (2.02 GB) — **downloading**
- [ ] Mistral-7B v0.3 Q4_K_M downloaded (4.37 GB)
- [ ] All weights integrity-checked and loadable

## P2 — Inference engines (llama.cpp + vLLM) + embeddings
- [x] llama.cpp chat server smoke-tested (`:8080`, Mistral IQ2_M)
- [x] Embeddings endpoint live (`:8001`, bge-small, dim 384)
- [x] vLLM GGUF flags verified; launcher script written
- [x] vLLM serving Qwen2.5-7B on H200 (tokens/sec logged) — 53.6 tok/s
- [x] llama.cpp serving Qwen2.5-7B Q4_K_M on `:8080`

## P3 — RAG data plane
- [x] Vector DBs + Open WebUI containers running
- [x] Compose reference written (`deploy/docker-compose.yml`)
- [x] Vector collection/schema setup (Milvus, Qdrant, pgvector) — `deploy/setup_data_plane.py`
- [x] Open WebUI wired to local OpenAI endpoints — `deploy/recreate_webui.sh`
- [ ] End-to-end ingest → retrieve works against a real vector DB

## P4 — Run + test sample repos (parallel)
- [x] Shared RAG test harness written (`scripts/rag_test_harness.py`)
- [x] lightrag dedicated venv created
- [ ] lightrag run + test (`scripts/services/lightrag_run.sh` ready)
- [ ] anything-llm run + test
- [ ] ragflow run + test
- [ ] dify run + test
- [ ] Results recorded in `docs/history/`

## P5 — Production hardening + runbook
- [ ] systemd/compose services with auto-restart
- [ ] Env/secrets management (no secrets in code)
- [ ] GPU limits + monitoring
- [x] Progress dashboard built (`scripts/progress_report.py`, cron-able)
- [ ] Cold-restart verified + runbook doc
