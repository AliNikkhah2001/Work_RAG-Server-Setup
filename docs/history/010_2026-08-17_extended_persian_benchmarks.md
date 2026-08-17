# 010 — 2026-08-17: Extended Persian Benchmarks (Gemma-3, Qwen3 family), Creative Plots, Auto-git

## Summary (current status)

- **Benchmarked 3 more complete models** on the Persian eval suite (50 rows/task, chat, temp 0.0): Gemma-3-27B Q4_K_M (**0.600**), Qwen3.8-27B Q4_K_M (**0.169**), Qwen3-30B-A3B Q4_K_M (**0.131**). Total: **9 models** now ranked.
- **Diagnosed the Qwen3 collapse**: both Qwen3 models fail the eval's strict answer-format parsing (emit `44`/`I` instead of option letters; NER 0.00, RC ≈ 0) yet score mid-level sentiment (0.48) — a **format-instruction weakness**, not missing Persian ability.
- **Rebuilt the report generator** (`scripts/gen_eval_report.py`) with creative plots:
  - `persian_scatter.png` — model size (GB) vs mean accuracy, bubble = params
  - `persian_radar.png` — ability-group radar (Reasoning & Knowledge / Language Understanding / Info Extraction)
  - `persian_radar_family.png` — per-family radar subplots
  - kept `persian_mean.png`, `persian_by_task.png`
- **README updated** with 9-model table, ability-group table, all 5 plots embedded, and "how to read the plots" explanations.
- **Auto-commit/push daemon** (`scripts/services/autogit_daemon.sh`) now runs **every 30 min** (AUTOGIT_INTERVAL=1800s default), commit-then-rebase-then-push ordering fixed.

## What was done

### 1. New benchmarks (all Q4_K_M, chat, limit 50, max_tokens 128)

| Model | Mean | ARC | MC | Math | Sent | Entail | NER | RC |
|---|---|---|---|---|---|---|---|---|
| Gemma-3-27B | 0.600 | 0.900 | 0.440 | 0.520 | 0.680 | 0.200 | 0.980 | 0.400 |
| Qwen3.8-27B | 0.169 | 0.240 | 0.040 | 0.020 | 0.480 | 0.360 | 0.000 | 0.040 |
| Qwen3-30B-A3B | 0.131 | 0.140 | 0.020 | 0.040 | 0.480 | 0.240 | 0.000 | 0.000 |

- Gemma-3-27B is 2nd overall, nearly matching Gemma-4-31B on ARC (0.90 vs 0.96) and NER (0.98 vs 1.00).
- Qwen3.8-27B `fa_mc` sample pred `'44'`, Qwen3-30B-A3B pred `'I'` — the scorer can't map these → near-zero on structured tasks. Sentiment (free-form) is fine → confirms format-instruction failure.

### 2. Report generator rewrite (`scripts/gen_eval_report.py`)
- Added `MODEL_META` (params B, disk GB, family, color) keyed by GGUF stem.
- `ABILITY_GROUPS`: Reasoning & Knowledge = ARC/MC/Math; Language Understanding = Sentiment/Entail; Info Extraction = NER/RC.
- `group_accuracy()` mean-per-group → radar inputs.
- 5 plots total (mean bar, per-task grouped bar, size-scatter with bubble=params, all-model radar, per-family radar grid). Matplotlib 3.11.1 in venv.

### 3. README update
- §4b now has: 9-model table w/ family+params+size, ability-group table, 5 embedded PNGs, "how to read the plots" narrative, reproduction command fixed to `--max-tokens 128`.

### 4. Auto-git daemon
- `scripts/services/autogit_daemon.sh`: default interval changed 300→1800s; ordering fixed to commit → rebase → push so `--rebase` no longer aborts on unstaged changes. Restarted with `AUTOGIT_INTERVAL=1800`.
- Verified earlier daemon pushed commit `9ba75ac` to origin/main; latest auto-commit `25ba3d5` pushed.
- `rag_storage/` added to `.gitignore`.

## Commands

```bash
# benchmark a new model
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
    --model <gguf> --limit 50 --chat --max-tokens 128 --out evalp_<name>.json

# rebuild report + plots
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py

# auto-git daemon (30 min interval)
setsid bash scripts/services/autogit_daemon.sh
```

## Findings / gotchas

- Python stdout under `nohup` is block-buffered → eval progress lines don't appear until a task finishes; check the JSON file or CPU% instead.
- Qwen3 family needs the eval's chat template/formatter tuned (option-letter extraction) before their real capability can be measured.
- The Qwen3-30B-A3B GGUF is a MoE (active 3B) — its low structured-task scores are NOT a compute-limitation story; it's the format parser.

## Status of other work (background)

- Model downloads: Gemma-4-31B, Gemma-3-27B, Qwen3.8-27B, Nemotron-49B, Qwen3-30B-A3B all complete+verified. DeepSeek-V4-Flash at 25/46 shards (~54%), proxy-limited. Qwen2.5-72B + Nemotron-Ultra-253B removed from queue (partials on disk).
- anything-llm: frontend deps done (642 pkgs); server/collector npm installs failed on proxy ECONNREFUSED — need retry.
- dify: core images pulled (api 4.15G, plugin-daemon 2.28G, web, sandbox, agent-backend, squid, postgres, redis); mysql:8.0 pull reported OK but image absent — re-pull needed.
- LightRAG: fully validated e2e on Gemma-4-31B + multilingual-e5-small (EN+FA, 4 query modes).
