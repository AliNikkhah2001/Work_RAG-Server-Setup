# Evidence T1.7 — README Gap Analysis

> Generated 2026-08-23T13:09 UTC · README 803 lines (was spec 797L, now 803L after minor edits) · Todo requires exhaustive step-by-step run & test guide

## S1.7.1 — README Section Map (current)

`wc -l README.md` → **803 lines**
`grep -n "^## " README.md`:

```
11:## Implementation Progress
57:## Download Progress
118:## 1. Hardware & Environment
171:## 2. Architecture / Components
206:## 3. What was done
225:## 4. Models inventory
278:## 4b. Model benchmark — Persian LLM evaluation
483:## 4c. Sample questions — one tricky prompt per category, all models
709:## 4d. Embedding model comparison (Persian retrieval)
723:## 5. Plan & Progress
752:## 6. Commands
785:## 7. Known issues / gotchas
795:## 8. Documentation
```

### Current coverage per §

| § | Title | Lines | Status |
|---|-------|-------|--------|
| 1 | Hardware & Environment | 118-170 | Has nvidia-smi table, proxy env snippet, BASE_DIR fix note, but not runnable `env | grep proxy` block + `cat proxy_setup.sh` + Docker daemon proxy |
| 2 | Architecture / Components | 171-205 | Diagram + ports list, but lacks `docker ps` 9-container table + compose inspect evidence |
| 3 | What was done | 206-224 | Narrative, no per-file LOC table |
| 4 | Models inventory | 225-277 | Table of 6-7 GGUFs with sizes, but missing 17-dir hf inventory (many dirs omitted), no exact `du -sh` numbers, no HF links per row, no download cmd |
| 4b | Persian benchmark | 278-482 | Excellent — ranked mean table, radar, scatter, speed tok/s, 10 plots, reproduction cmds — **most complete section** |
| 4c | Sample questions | 483-708 | Per-task tricky sample Q&A across models, good but lacks `gen_sample_questions.py` invocation |
| 4d | Embedding comparison | 709-722 | Small — needs embed_server args + curl per port |
| 5 | Plan & Progress | 723-751 | Checklist, not step-by-step runbook |
| 6 | Commands | 752-784 | Short runnable block, but not covering each of 11 models, each embed, manager curls, opencode session |
| 7 | Known issues | 785-794 | 5 bullets (proxy drops, vLLM single-file, numpy pin, .state.json stale, docker data-root) — missing trust_env fix, opencode hang, XET, qwen3 thinking |
| 8 | Documentation | 795-803 | Links to docs/history, deploy/compose, docs/reports |

## Required vs Actual — Gaps Matrix

Mission requires: *checked, detailed, step-by-step project run & test README covering ALL models, benchmark code, all code, model files, requirements downloads, plus run Models Manager OpenAI API expose + opencode test session*

| Requirement | Required Evidence | Found in README | Gap |
|-------------|-------------------|-----------------|-----|
| **ALL 11 registry models** step-by-step run | Per-model: id, size GB, gguf path, creator, quant, context, benchmark mean, backend port(s), `curl /health` + `curl /v1/chat/completions` both direct and via :9000, load/unload example | §4 lists ~6-7 models, §4b mentions 9 evaluated, but §6 shows only 2 example curls; no per-model 11-row table with `POST /admin/models/load?model_id=gemma-3-27b` demo | **HIGH** — need 11-row LLM table + per-model curl block |
| **ALL 5 embeds** step-by-step | 3 live (8001 e5-small 384, 8002 bge-m3 1024, 8003 paraph 384) + 2 offline (bge-small-en 383M, all-MiniLM 912M), `ps aux | grep embed`, `curl /health` per port, `curl /v1/embeddings` per port, dim verification, WebUI config | §4d tiny, §6 has one embed curl | **HIGH** — need embed table + 3 health+embedding curls |
| **ALL docker** run & test | 9 containers (webui 13000 healthy, milvus 19530, pgvector 15432, qdrant 16333, redis 16379 + grafana 13001, prometheus 19090, otel 14317, node-exporter 19100), `cat deploy/docker-compose.yml` snippet, `docker ps` table, per-service health (webui health, milvus /v1/health, psql, qdrant /health, redis-cli ping), `recreate_webui.sh` | §2 lists data-plane 5, §1 mentions docker daemon proxy not shown | **MEDIUM** — need 9-row table + health cmds |
| **Requirements downloads** | `offline-prep/venv` py3.12.3 creation cmd, shebang fix `/usr/bin/python3`, `pip freeze` table (torch 2.8.0+cu128, vllm 0.6.1.post1, flash-attn 2.6.3, llama-cpp 0.3.34, transformers 4.44.0, s-t 3.0.1, faiss-gpu, bitsandbytes 0.50.0, numpy 1.26.4, scipy 1.13.1), `ls pip_cache`, `ls python-packages*/*.whl | wc -l`, `download_models.py` TARGETS walk, `download_embeddings.py`, HF_HUB_DISABLE_XET=1 | §1 mentions venv py3.12.3, §5 checklist mentions requirements, but no freeze table nor download cmd | **HIGH** — need freeze table + download cmds |
| **Model files inventory** | 17 hf dirs with `du -sh` exact GB (gemma-4 19.6G 19G du, gemma-3 16.5G, qwen3.8 17.8G, qwen3-30b 18.6G, nemotron 30.2G 29G, qwen2.5-7b 4.4G, llama3.2 1.9G, mistral 127G multi-file, phi3 9.4G, deepseek 149G 46 shards, qwen72b ~512G, 5 embeds sizes, plus `ls *.gguf` filenames, HF repo links, policy ≤100GB excluded list) | §4 partially covers but omits ~10 dirs, sizes rounded, no filenames column | **HIGH** — need 17-row inventory with `du -sh` numbers + gguf filename column |
| **ALL code** (benchmark etc) | Scripts table with LOC (eval_persian 409L, bench_speed 69L, eval_gguf 195L, gen_eval_report 870L, gen_prompt_compare 202L, rag_test_harness 95L, download_models 171L etc), purpose per script, runnable examples per harness (limit, n-shots, prompt-style, bench --only, report gen), logs/evalp*.json 20+ + speed_bench.json | §4b reproduction has eval_persian/bench_speed examples, §6 has short commands, but no full scripts LOC table | **MEDIUM** — need scripts LOC table + per-harness blocks |
| **Manager OpenAI API expose** | Manager app.py 580L read-through, MODEL_REGISTRY 11, `trust_env=False` line 321, 8 endpoints (GET /health, /v1/models, /v1/models/{id}, POST /v1/chat/completions, /v1/completions, /v1/sessions, /admin/status|metrics|load|unload), auth sk-local-dev, round-robin, find_next_port 8085..8100, sqlite tables, `llm_inference_manager/test_manager.sh` suite, curl table per model | §6 mentions manager :9000 briefly, no endpoint table, no trust_env, no test script | **HIGH** — need manager API table + curl suite |
| **Opencode test session** | opencode.jsonc 16 models (5 gemma-local 8080-8084 + 11 h200-manager), provider type openai options.baseURL http://localhost:9000/v1, limit context/output, mcp without servers, `opencode models` 11 lines, `opencode run --model h200-manager/gemma-4-31b --format json "say hello one word"` with timeout 60 + hang explanation (compaction loop not API, manager logs 20+ POST 200 streaming step_start/finish), fallback curl canonical, per-model backend ports table | Not in README at all (only .opencode/context.md notes it) | **HIGH** — need new §10 opencode+manager run |
| **Proxy 192.168.203.2:3128** | `env | grep -i proxy`, `cat proxy_setup.sh`, `git config --global http.proxy`, `/etc/apt/.../99proxy`, docker http-proxy.conf, no_proxy localhost, embed/llm bypass | §1 lists proxy IP once, §7 mentions proxy drops, but not runnable env block | **MEDIUM** — need proxy env block with no_proxy |
| **Corrected counts** | `trust_env` 0 mentions now (should be ≥1), `h200-manager` 0 (needs 11), `gemma-4-31b` 0 (needs hyphen variant) | Confirmed via `grep -c` below | **Fix** — normalize model ids to registry ids |

### Quantified gaps (`grep -c` in README.md)

```
trust_env: 0   → need 1 (manager fix line 321)
h200-manager: 0 → need ≥5 (opencode provider name)
Q4_K_M: 30     → OK (many GGUF mentions)
192.168: 5     → OK but need runnable env block not just mentions
offline-prep/venv: 23 → OK but need freeze table
gemma-4-31b: 0 → BUG — README uses 31b without hyphen in model-id? Actually gemma-4-31b vs Gemma-4-31B confusion, need normalized registry ids gemma-4-31b
eval_persian: 6 → OK
bench_speed: 1 → need 2 (help + runnable)
```

### Minimal ToC for expanded README (required M2)

```
0 Quick Start       — one-command smoke test (manager + curl hello + embed dim)
1 Hardware & Env    — nvidia-smi, nvcc, env | grep proxy, proxy_setup.sh, BASE_DIR fix, df -h
2 Docker Data-Plane — compose ref, 9 containers table, docker ps, per-service health (5+4)
3 Venv & Requirements — venv creation, shebang fix, pip freeze table, wheels, venv-deepseek
4 Model Files       — 17-row inventory (repo_id, path, gguf, size GB du -sh, quant, ctx, mean, status, HF link, download cmd, ≤100GB policy)
5 Embed Services    — embed_server args, 3 live +2 offline, ps, curl /health + /v1/embeddings per port, dim, WebUI
6 LLM Services      — llama_chat_server flags, supervisor 5× 8080-84 GPU split, 11-row registry table, curl direct + via manager per model, load/unload example
7 Benchmark Code    — scripts LOC table, eval_persian 7 tasks + params (limit 50 temp 0.0 max_tokens 400/128, n-shots, improved), bench_speed tok/s table, eval_gguf MMLU/GSM8K, gen_eval_report 10 png+interactive, gen_prompt_compare, rag_test_harness, runnable blocks per variant
8 Reports & Logs    — 10 png inventory, interactive twins, persian_eval_report 1770L, prompt_compare 656L, logs/evalp*.json 20+, how to read plots
9 Troubleshooting   — XET disable, proxy instability, scipy/numpy pin, vllm gguf single-file, /ai-gpu1 stale, .state.json stale, trust_env, opencode hang compaction loop, qwen3 thinking max_tokens 128→400 + strip_think
10 Manager + OpenCode — manager health/models/admin, 8 endpoints table, trust_env fix, test_manager.sh suite, curl table per model, opencode.jsonc provider, opencode models, opencode run with timeout + hang note, fallback curl canonical
```

### Dependencies for M2

- Requires S1.1.x–S1.6.x evidence docs (T1.1–T1.6) — especially `du -sh` numbers, `pip freeze`, `docker ps`, `curl :9000/health`, `speed_bench.json` tok/s
- Content sources: `.opencode/docs/evidence_T1.1_T1.2.md`, `evidence_T1.3_models.md`, `evidence_T1.4_T1.5_services.md`, `evidence_T1.6_benchmarks.md` (this series), plus `manager_api.md`, `models_inventory.md`, `benchmark_harness.md` caches (S1.7.2-5)

---
*Evidence: `wc -l README.md`, `grep -n "^## "`, `grep -c` for 8 terms, section line ranges via `sed -n`, plus mission todo checklist cross-ref. Collected 2026-08-23 in Work_RAG-Server-Setup.*
