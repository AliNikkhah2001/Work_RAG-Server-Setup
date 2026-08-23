# Project Context

## Environment
- ai-gpu1 2xH200 143GB driver 580.173.02 CUDA13, proxy 192.168.203.2:3128, dir /splunk-data/v1/Work_RAG-Server-Setup
- Venv py3.12.3, docker 9 Up (webui13000/milvus19530/pgvector15432/qdrant16333/redis16379 + grafana/prom/otel/node-exporter), embeds 8001-3, gemma 5x 8080-84 + qwen 8090 via manager 9000

## Dashboard Webapp — NEW (2026-08-23 14:11)
- File: llm_inference_manager/app.py 917 lines (was 580), patched with dashboard routes, backup app.py.bak
- Routes: GET / (dashboard), GET /dashboard (same), GET /api/dashboard (comprehensive JSON), GET /api/project, GET /api/usage, PATCH/PUT /admin/models/{id}, POST /admin/models/load/unload
- Dashboard HTML: DASHBOARD_HTML 300+ lines, tabs Overview/Models/Embeds&Docker/Project/Usage/Playground, vanilla JS fetch /api/dashboard, GPU bars, model cards with Run/Stop/Test/Edit buttons, embed/docker/disk/project/usage, chat + embed playgrounds
- Manager restarted pid 2289945, health models_loaded 2 (after reload qwen 8085, GPU1 free 76321), gemma still 5x, qwen 8090 + 8085 both, all health 200
- Tests: curl /dashboard → HTML ok, curl /api/dashboard → 11 models/9 docker/3 embeds/9 project/benchmarks 28 logs, curl /api/project, /api/usage (99 gemma 1862ms avg, 39 qwen 1418ms), curl /v1/chat gemma→Hello OK

## Previous Milestone — DONE 50/50 (100%)
- README 1540 lines 114K ✅ VERIFIED RUNBOOK (sections 0..14), backup README.md.bak.20260823, 3 manager_test logs, 2 opencode_session logs, Reviewer gate closed 13:21
- Manager trust_env=False fix, opencode h200-manager 11 models visible, both configs synced
- Todos: 0 remaining /50 done, M1-M4 completed, status pass

## Pending Tasks Dashboard
- Verify run/stop via curl: test POST /admin/models/load gemma-3-27b →8085 and unload, test PATCH edit, ensure UI buttons work in browser (curl already proves API)
- Update README to document dashboard: add §15 Dashboard (routes, screenshots, curls, run/stop/edit)
- Retest opencode models + curl gemma chat after dashboard restart
- Update todo.md to add M5 Dashboard milestone and mark done, update work-log
- Ensure manager log persists, no regression of 5x gemma
