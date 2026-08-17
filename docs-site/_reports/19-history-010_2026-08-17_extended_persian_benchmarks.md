---
title: "010 — 2026-08-17: Extended Persian Benchmarks (Gemma-3, Qwen3 family), Creative Plots, Auto-git"
nav_order: 19
---

# 010 — 2026-08-17: Extended Persian Benchmarks (Gemma-3, Qwen3 family), Creative Plots, Auto-git

## Summary (current status)

- **Benchmarked 3 more complete models** on the Persian eval suite (50 rows/task, chat, temp 0.0): Gemma-3-27B Q4_K_M (**0.600**), Qwen3.8-27B Q4_K_M (**0.477**), Qwen3-30B-A3B Q4_K_M (**0.283**). Total: **9 models** now ranked.
- **Qwen3 "collapse" was OUR bug, not the model**: Qwen3 GGUFs emit ` thinking... response` reasoning blocks; with `max_tokens=128` the real answer (after ` response`) was truncated and the old parser grabbed numbers/letters (`44`, `I`) from thinking text. Fixed via `strip_think()` + `--max-tokens 400` → Qwen3.8-27B 0.169→**0.477** (ARC 0.92, MC 0.62, RC 0.58), Qwen3-30B-A3B 0.131→**0.283** (ARC 0.52). Sentiment ~0.72–0.76 confirms the models read Persian well; the gap is structured-task format following.
- **Rebuilt the report generator** (`scripts/gen_eval_report.py`) with creative plots:
  - `persian_scatter.png` — model size (GB) vs mean accuracy, bubble = params
  - `persian_radar.png` — ability-group radar (Reasoning & Knowledge / Language Understanding / Info Extraction)
  - `persian_radar_family.png` — per-family radar subplots
  - `persian_speed.png` — tokens/sec + latency per task (new)
  - `persian_spider.png` — 7-axis per-task spider per model (new)
  - kept `persian_mean.png`, `persian_by_task.png`
- **Speed bench** (`scripts/bench_speed.py`, `scripts/services/run_speed_bench.sh`): 256-token Persian generation, all 9 models on GPU1. Results: Phi-3-mini 226.6, Mistral-7B 172.7, Qwen2.5-7B 163.9, Qwen3-30B-A3B 155.1 (MoE, 3B active), Llama-3.2-3B 72.2, Gemma-3-27B 67.3, Qwen3.8-27B 61.2, Gemma-4-31B 55.7, Nemotron-49B 45.6 tok/s.
- **2-shot eval**: `--n-shots 2` on Qwen2.5-7B → 0.466 (vs 0-shot 0.443); lifts NER 0.88→0.96, ARC 0.68→0.74, RC 0.14→0.34; hurts math 0.38→0.12.
- **Embedding comparison**: 3 embedders (e5-small 384d / bge-m3 1024d / paraphrase-MiniLM 384d) on 6-doc Persian retrieval — all top-1=1.0; mean top-1 cosine 0.898 / 0.646 / 0.555; latency 0.14 / 0.27 / 0.09 s. README §4d.
- **Sample-questions section (README §4c)**: 7 tricky prompts (one per task) where the 9 models disagree, each model's raw output + score inline in README (also as `docs/reports/persian_sample_questions.md`). Generator: `scripts/gen_sample_questions.py`. Sample selection keyed by `(task,index)` (NER prompt template is identical across rows).
- **README updated** with 9-model table (corrected Qwen3 scores), ability-group table, speed table, n-shot + same-question sections, all 7 plots embedded, "how to read the plots" explanations.
- **Auto-commit/push daemon** (`scripts/services/autogit_daemon.sh`) now runs **every 30 min** (AUTOGIT_INTERVAL=1800s default), commit-then-rebase-then-push ordering fixed. Alive pid 900590.

## What was done

### 1. New benchmarks (all Q4_K_M, chat, limit 50; Qwen3 rerun max_tokens 400)

| Model | Mean | ARC | MC | Math | Sent | Entail | NER | RC |
|---|---|---|---|---|---|---|---|---|
| Gemma-3-27B | 0.600 | 0.900 | 0.440 | 0.520 | 0.680 | 0.200 | 0.980 | 0.400 |
| Qwen3.8-27B | 0.477 | 0.920 | 0.620 | 0.180 | 0.760 | 0.260 | 0.020 | 0.580 |
| Qwen3-30B-A3B | 0.283 | 0.520 | 0.280 | 0.040 | 0.720 | 0.260 | 0.000 | 0.160 |

- Gemma-3-27B is 2nd overall, nearly matching Gemma-4-31B on ARC (0.90 vs 0.96) and NER (0.98 vs 1.00).
- Qwen3.8-27B jumped 3 ranks to 4th; NER still 0.02 (emits prose instead of expected structure). Qwen3-30B-A3B NER 0.00.
- All Qwen3 reruns written over the original `logs/evalp_qwen3_*.json` files (old mtime noted before overwrite).

### 2. Report generator rewrite (`scripts/gen_eval_report.py`)
- Added `MODEL_META` (params B, disk GB, family, color) keyed by GGUF stem.
- `ABILITY_GROUPS`: Reasoning & Knowledge = ARC/MC/Math; Language Understanding = Sentiment/Entail; Info Extraction = NER/RC.
- `group_accuracy()` mean-per-group → radar inputs.
- 7 plots total (mean bar, per-task grouped bar, size-scatter, all-model radar, per-family radar grid, speed bar-pair, per-task spider). Matplotlib 3.11.1 in venv.
- Speed plot merges `logs/speed_bench.json` (via `load_speed_bench()` + `bench_key()`) when eval `tok_sec` missing.
- Added **same-question cross-model section** (first example per task, all 9 models, hit/miss markers) — shows format-following is the main differentiator (e.g. Qwen3-30B wraps answers in ` thinking`).
- `load_results` distinguishes `(2-shot)`/`(0-shot)` suffixed files.

### 3. eval_persian.py upgrades
- `strip_think()`: removes ` thinking... response` blocks (DOTALL, also handles unbalanced ` response`).
- `--n-shots N` + `make_fewshot()` — prepends exemplars per task.
- `tok_sec` captured per task (completion_tokens/sec).

### 4. README update
- §4b: corrected 9-model table, ability-group table, speed table, 7 embedded PNGs, n-shot section, same-question "why scores differ" section, "how to read the plots", reproduction commands (max_tokens 400 + n-shots + bench_speed).
- §4c (new): sample-questions walkthrough (tricky prompt per task, all models, 0/2-shot).
- §4d (new): embedding model comparison.
- §4 inventory + download status refreshed to 2026-08-17.

### 5. Auto-git daemon
- `scripts/services/autogit_daemon.sh`: default interval changed 300→1800s; ordering fixed to commit → rebase → push so `--rebase` no longer aborts on unstaged changes. Alive pid 900590.
- `rag_storage/` added to `.gitignore`. Manual descriptive commit `d9d2170` pushed (Qwen3 fix + speed bench + README).

## Commands

```bash
# benchmark a new model (400 tokens needed for Qwen3 thinking models)
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
    --model <gguf> --limit 50 --chat --max-tokens 400 --out evalp_<name>.json

# 2-shot variant
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
    --model <gguf> --limit 50 --chat --max-tokens 128 --n-shots 2 --out evalp_<name>_2shot.json

# speed bench (sequential, all models; resume-aware)
HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=1 offline-prep/venv/bin/python3.12 scripts/bench_speed.py \
    --out logs/speed_bench.json

# rebuild report + plots
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py

# auto-git daemon (30 min interval)
setsid bash scripts/services/autogit_daemon.sh
```

## Findings / gotchas

- Python stdout under `nohup` is block-buffered → eval progress lines don't appear until a task finishes; check the JSON file or CPU% instead.
- **Qwen3 thinking mode**: llama-cpp-python 0.3.34 has no `chat_template_kwargs` support, so reasoning can't be disabled via API — must strip ` thinking... response` from output and give the model room (max_tokens 400).
- Background `nohup` jobs launched from a shell that later times out get killed — use `setsid`+`disown` or a wrapper script (`run_speed_bench.sh`); foreground runs worked when background silently died.
- Speed bench must run models **sequentially** — parallel instances share the GPU and skew tok/s.
- Qwen3-30B-A3B GGUF is MoE (3B active) → fastest "large" model (155 tok/s) but weak on structured tasks.
- Embedding takeaway: e5-small best separation (cosine 0.898), bge-m3 safest for low-similarity corpora, MiniLM fastest.

## Status of other work (background)

- Model downloads: Gemma-4-31B, Gemma-3-27B, Qwen3.8-27B, Nemotron-49B, Qwen3-30B-A3B all complete+verified.
- **POLICY (2026-08-17): models > 100 GB download size are excluded** from `scripts/download_models.py` TARGETS. Removed: DeepSeek-V4-Flash (~160 GB, partial 25/46 shards kept on disk, daemon stopped), MiniMax-M3 (~208 GB), Kimi-K3 (~594 GB), GLM-5.2-FP8 (~755 GB). README §4a has the full ≤100 GB table (name / where to get / format / link). No downloads currently in-flight.
- anything-llm: frontend deps done (642 pkgs); server/collector npm installs failed on proxy ECONNREFUSED — need retry.
- dify: core images pulled (api 4.15G, plugin-daemon 2.28G, web, sandbox, agent-backend, squid, postgres, redis); mysql:8.0 pull reported OK but image absent — re-pull needed.
- LightRAG: fully validated e2e on Gemma-4-31B + multilingual-e5-small (EN+FA, 4 query modes).

