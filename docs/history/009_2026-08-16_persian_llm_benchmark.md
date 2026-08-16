# 009 — 2026-08-16: Persian LLM Benchmark Suite & Reports

## Summary (current status)

- Built a **Persian-native LLM evaluation harness** (`scripts/eval_persian.py` + `scripts/persian_norm.py`) that benchmarks GGUF models on 7 Persian tasks (ParsBench suite + Persian ARC) using chat completions with Persian text normalization.
- **Downloaded the ParsBench dataset suite** offline (`scripts/download_persian_eval.py`) for: parsinlu-multiple-choice, persian-math, persian-ner, pnsummary, farstail-entailment, persian-conjnli, parsinlu-entailment, sentiment, reading-comprehension.
- **Benchmarked 6 complete models**: Gemma-4-31B Q4_K_M (mean 0.663), Nemotron-49B Q4_K_M (0.494), Qwen2.5-7B Q4_K_M (0.443), Llama-3.2-3B Q4_K_M (0.326), Mistral-7B Q4_K_M (0.186), Phi-3-mini q4 (0.143).
- Generated **report + plots** (`docs/reports/`): `persian_eval_report.md`, `persian_mean.png`, `persian_by_task.png`; README updated with tables/plots/download status.
- Downloads continue under the **exponential-backoff daemons** (never-stop retry loop); 72B Q8_0 part 1 at 86%, Gemma-3-27B at 71%.

## What was done

### 1. Persian preprocessing module (`scripts/persian_norm.py`)
- `normalize()`: Arabic↔Persian letter unification (ي→ی, ك→ک, آ→ا …), Persian/Arabic digit → ASCII, ZWNJ→space, diacritic strip, space/connector collapse, punctuation→space.
- `norm_tokens()` / `jaccard()` for token-set similarity scoring (used for open-ended math/RC/NER answers).

### 2. Eval harness (`scripts/eval_persian.py`)
- Tasks: `fa_arc` (Persian ARC-Easy MC), `fa_mc` (Parsinlu MC), `fa_math`, `fa_sentiment`, `fa_entail` (ParsBench), `fa_conjnli`, `fa_ner`, `fa_rc` (Parsinlu RC).
- Always `--chat` (chat completions) because Gemma-4/Nemotron emit 0 tokens on raw prompts (thinking-channel EOS).
- Scorers per task: exact letter/option, label classifier (positive/negative/entailment/contradiction/neutral incl. ParsBench letter codes c/e/n), numeric extraction (last number when gold is numeric), Jaccard thresholds for open tasks.
- Saves per-example prompt/gold/pred/output/hit → drives the report.

### 3. Dataset downloads (`scripts/download_persian_eval.py`)
- All ParsBench alpaca-style repos cached except **machine-translation-en-fa** — its ~1 GB JSONL fails pyarrow generation (`block_size ... too large to convert to int32_t`, a datasets/pyarrow bug), even with streaming; **excluded** and noted in code.
- `Mohammadreza/persian-mmlu-categorized` **cannot load**: "Dataset scripts are no longer supported" under datasets 5.0.1 — skipped.

### 4. Model benchmarking (50 rows/task, temp 0.0, chat)

| Model | Mean | ARC | Parsinlu MC | Math | Sent | Entail | NER | RC |
|---|---|---|---|---|---|---|---|---|
| **Gemma-4-31B Q4** | **0.663** | 0.96 | 0.70 | 0.64 | 0.82 | 0.16 | **1.00** | 0.36 |
| Nemotron-49B Q4 | 0.494 | 0.92 | 0.32 | 0.50 | 0.68 | 0.22 | 0.46 | 0.36 |
| Qwen2.5-7B Q4 | 0.443 | 0.68 | 0.36 | 0.38 | 0.66 | 0.00 | 0.88 | 0.14 |
| Llama-3.2-3B Q4 | 0.326 | 0.56 | 0.30 | 0.14 | 0.58 | 0.24 | 0.00 | 0.46 |
| Mistral-7B Q4 | 0.186 | 0.36 | 0.24 | 0.06 | 0.30 | 0.18 | 0.02 | 0.14 |
| Phi-3-mini q4 | 0.143 | 0.34 | 0.10 | 0.00 | 0.22 | 0.16 | 0.00 | 0.18 |

Findings:
- Gemma-4-31B is the clear winner: 0.96 Persian ARC, perfect NER (1.0), best everywhere except entailment/RC.
- Qwen2.5-7B is a strong small model on NER (0.88) but scores 0.00 on entailment (emits label letters the scorer can't map).
- Small models collapse on NER/math; Llama-3.2-3B is best small model on RC (0.46).

### 5. Report generator (`scripts/gen_eval_report.py`)
- Reads `logs/evalp_*.json`, emits Markdown table + per-model I/O samples + matplotlib PNGs.
- matplotlib 3.11.1 installed into venv from `pip download` (proxy-safe, offline wheel install).

### 6. Download daemon status (backoff active, all healthy)

| Target | Progress |
|---|---|
| Qwen2.5-72B Q8_0 part 1 | 34.4/40 GB (86%) — daemon resuming, ~0.2–2.5 GB/retry |
| Gemma-3-27B Q4_K_M | 11.7/16.5 GB (71%) — resumed from 6.5 GB |
| Qwen3-30B-A3B | 11.5/18.6 GB (paused mid-download) |
| Nemotron-Ultra-253B Q4_K_M | 151 GB — partials, queued |
| Qwen2.5-72B Q4_K_M | queued |

Daemons: systemd `rag-dl` (main walk) + dedicated 72B resume daemon. Each failure → exponential brake (90s base, ×2, cap 3600s, jitter), then resume from `.incomplete` file. Both confirmed alive at 14:18 UTC with consecutive-failure brakes (attempt 9, brake ~3000–4000s).

## Gotchas / findings

- **Persian-MMLU & machine-translation datasets cannot be cached** under datasets 5.0.1 (loading scripts deprecated; pyarrow int32 `block_size` overflow on huge JSONL). Use alternative parquet mirrors or skip.
- **Phi-3-mini's GGUF has `add_eos_token: false`** → generation runs to `max_tokens`; keep `--max-tokens` small (128) for speed. Earlier "hang" was just 400-token outputs on every prompt.
- **Run evals with `HF_HUB_OFFLINE=1`** so cached datasets are used and no proxy call is attempted mid-run.
- **Gemma-4 / Nemotron / Qwen chat models require `--chat`**; raw `llm(prompt)` returns 0 tokens (thinking-channel EOS).

## Files

- `scripts/persian_norm.py`, `scripts/eval_persian.py`, `scripts/download_persian_eval.py`, `scripts/gen_eval_report.py`
- `logs/evalp_<model>.json` (per-model results incl. samples), `logs/evalp_run1.out`, `logs/evalp_run2.out`
- `docs/reports/persian_eval_report.md`, `docs/reports/persian_mean.png`, `docs/reports/persian_by_task.png`
- `README.md` — added §4b benchmark tables/plots + download-status table

---

## Addendum 1 — Download history (2026-08-16, 14:36 UTC)

### Download log trail
`offline-prep/logs/dl_models_*.log` (one file per daemon launch):

| Log file | Daemon / role |
|---|---|
| `dl_models_20260815_1335.log` | main walk (original), later restarted |
| `dl_models_20260816_0735.log` | pre-backoff 72B resumer (attempts 1–18, ~27 MB/chunk, no brake) |
| `dl_models_20260816_0852.log` | main walk with **backoff** (Gemma-3-27B) |
| `dl_models_20260816_0853.log` | 72B resume daemon with **backoff** |
| `dl_models_20260816_1436.log` | **Qwen3.8-27B** dedicated daemon (new) |

### Historical failure pattern (evidence of the proxy problem)
- **Pre-backoff** (`0735.log`, attempts 1–18): each retry moved only ~3–25 MB then died (`IncompleteRead`); no wait between attempts → wasted cycles.
- **Post-backoff** (`0852/0853.log`): consecutive failures now transfer **0.2–2.5 GB per retry** then brake exponentially (consec=9 → brake ~3000–4000 s). Resume is always byte-offset (`*.incomplete` files persist).
- Root cause confirmed: **Squid proxy resets TLS streams** on >1 GB transfers (`Connection broken: IncompleteRead`). Not auth, disk, or GPU.

### Progress snapshots (partial `.incomplete` files, 14:36 UTC)
| Target | File size | Note |
|---|---|---|
| Qwen2.5-72B Q8_0 part 1 | 34.4/40 GB (86%) | resuming |
| Gemma-3-27B Q4_K_M | 12.7/16.5 GB (77%) | grew 11.7→12.7 GB since 13:37 |
| Qwen3-30B-A3B Q4_K_M | 11.5/18.6 GB | paused mid-download |
| Nemotron-Ultra-253B Q4_K_M | ~1–1.3 GB partials | queued behind smaller files |

---

## Addendum 2 — Qwen3.8-27B added to model set & daemon list

- **Model**: `Qwen/Qwen3.8-27B` (multimodal, `qwen3_5` arch, image-text-to-text, Apache-2.0, not gated) — official repo ships **safetensors only (18 shards, ~58 GB), no GGUF**.
- **GGUF source**: `bartowski/Qwen3.8-27B-GGUF` (full quant range, incl. `Q4_K_M` 17.77 GB + `mmproj-*.gguf` vision projector ~0.93 GB). Also `unsloth/Qwen3.8-27B-GGUF` exists.
- **Verified downloadable**: HEAD request → HTTP 302 to `us.aws.cdn.hf.co` (same CDN pattern as all successfully-downloaded bartowski files); not gated.
- **Daemon entry added** to `scripts/download_models.py` TARGETS (between Gemma-4 and Qwen3-30B in smallest-first order):
  ```python
  ("bartowski/Qwen3.8-27B-GGUF",
   ["Qwen3.8-27B-Q4_K_M.gguf"]),   # 17.8 GB (multimodal)
  ```
- **Live download confirmed**: dedicated daemon pid 750522 (`--only Qwen3.8-27B --daemon`) started 14:36 UTC; **62.9 MB fetched in first 30 s** (growing `.incomplete`), log `dl_models_20260816_1436.log`.
- Once complete, it will be runnable through the eval harness like the other 6 models (chat completions).