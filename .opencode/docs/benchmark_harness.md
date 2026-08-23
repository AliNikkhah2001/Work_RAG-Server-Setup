# Benchmark Harness — cached (verified --help 2026-08-23)

Source: `scripts/` 17 py files, logs `logs/evalp*.json` 20+ files, `docs/reports/` 10 png + interactive

## Scripts Inventory (wc -l verified)

| Script | LOC | Purpose | Key flags | Runnable |
|--------|-----|---------|-----------|----------|
| eval_persian.py | 17433 | Persian 7-task chat eval | `--model <gguf> --limit 50 --chat --max-tokens 400 --prompt-style improved --n-shots 2 --temperature 0.5 --out` | `HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model <path> --limit 50 --chat --max-tokens 400 --out logs/evalp_<name>.json` |
| bench_speed.py | 3183 | tok/s 256-token Persian prompt `n_gpu_layers=-1` | `--out logs/speed_bench.json` | `offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json` |
| eval_gguf.py | 6989 | English MMLU-3subj, GSM8K, fa_arc, fa_rc | `datasets.load_dataset` + `llama_cpp.Llama` | `.../eval_gguf.py --model <gguf> --limit 50` |
| gen_eval_report.py | 41428 | Rebuild 10 PNG + Plotly + `persian_eval_report.md` + tables | reads `logs/evalp*.json` | `offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py` |
| gen_prompt_compare.py | 8644 | Vanilla vs improved RTL Q&A | `persian_prompt_compare.md` | `.../gen_prompt_compare.py` |
| gen_sample_questions.py | 7948 | Per-model good/bad samples | `persian_sample_questions.md` | - |
| find_tricky_samples.py | 2503 | Disagreement cases | - | - |
| gen_pages.py | 8025 | GitHub Pages multipage | `docs/reports/` -> `docs-site/` | `.../gen_pages.py` |
| download_models.py | 8209 | Proxy HF downloader 17 repos | `HF_HUB_DISABLE_XET=1` exponential backoff 90s->3600s | `HF_HUB_DISABLE_XET=1 ... download_models.py --daemon` |
| rag_test_harness.py | 3676 | RAG ingest->embed(384)->qdrant->generate | - | `.../rag_test_harness.py` |

## Persian 7 Tasks

| Task | Dataset HF | Scoring | Example prompt |
|------|------------|---------|----------------|
| fa_arc | MatinaAI/persian_arc ARC-Easy test | exact letter A/B/C/D | سؤال: ... گزینه‌ها: A) ... فقط حرف |
| fa_mc | ParsBench/parsinlu-multiple-choice | option number | Parsinlu MC |
| fa_math | ParsBench/persian-math | jaccard numeric/date | [پاسخ نهایی] |
| fa_sentiment | Parsinlu sentiment | positive/negative | - |
| fa_entail | Parsinlu entail + ConjNLI | entail/neutral/contradict -> تناقض/خنثی/استنتاج | - |
| fa_ner | ParsBench NER | jaccard tuple list | strict JSON [(token,label)] |
| fa_rc | Parsinlu reading comp | jaccard | span |

## Reproduction (verified --help)

```bash
offline-prep/venv/bin/python3.12 scripts/eval_persian.py --help
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --help

# Vanilla
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf --limit 50 --chat --max-tokens 400 --out logs/evalp_gemma4-vanilla.json

# Improved (ROLE/CONTEXT/CONSTRAINTS/OUTPUT, strip_think for Qwen3 <think>)
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model .../Qwen3.8-27B-Q4_K_M.gguf --limit 50 --chat --max-tokens 400 --prompt-style improved --out logs/evalp_qwen3.8-improved.json

# Few-shot 2
HF_HUB_OFFLINE=1 offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model .../Qwen2.5-7B-Instruct-Q4_K_M.gguf --limit 50 --chat --max-tokens 400 --n-shots 2 --out logs/evalp_qwen_2shot.json

# Speed
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json
cat logs/speed_bench.json | jq
# phi-3-mini 226.6 mistral 172.7 qwen2.5-7b163.9 qwen3-30b-a3b155.1 llama3.2 72.2 gemma-3 67.3 qwen3.8 61.2 gemma-4 55.7 nemotron45.6

# Via manager parity
curl -s http://127.0.0.1:9000/v1/chat/completions -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"سؤال: ..."}]}' | jq

# Reports
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py
offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py
offline-prep/venv/bin/python3.12 scripts/gen_pages.py
```

## Results (9 GGUF mean sorted)

| Model | Mean | ARC | MC | Math | Sent | Entail | NER | RC | tok/s |
|-------|------|-----|----|------|------|--------|-----|----|-------|
| Gemma-4 31B Q4_K_M | 0.663 |0.960|0.700|0.640|0.820|0.160|1.000|0.360|55.7|
| Gemma-3 27B |0.600|0.900|0.440|0.520|0.680|0.200|0.980|0.400|67.3|
| Nemotron 49B|0.494|0.920|0.320|0.500|0.680|0.220|0.460|0.360|45.6|
| Qwen3.8 27B|0.477|0.920|0.620|0.180|0.760|0.260|0.020|0.580|61.2|
| Qwen2.5 7B|0.443|0.680|0.360|0.380|0.660|0.000|0.880|0.140|163.9|
| Llama3.2 3B|0.326|0.560|0.300|0.140|0.580|0.240|0.000|0.460|72.2|
| Qwen3-30B-A3B|0.283|0.520|0.280|0.040|0.720|0.260|0.000|0.160|155.1|
| Mistral 7B|0.186|0.360|0.240|0.060|0.300|0.180|0.020|0.140|172.7|
| Phi-3 mini|0.143|0.340|0.100|0.000|0.220|0.160|0.000|0.180|226.6|

Improved +0.046..+0.223, Qwen3.8 0.169->0.477 after strip_think + max_tokens400, 2-shot helps NER/RC hurts math, temp0.0 best.

## Plots 10 PNG

| File | Desc | How to read |
|------|------|-------------|
| persian_mean.png | ranked mean | solid vanilla hatched improved family colors |
| persian_by_task.png | per-task | Gemma NER1.0 |
| persian_scatter.png | size vs mean bubble params | larger != better |
| persian_radar.png | ability groups | |
| persian_radar_family.png | per-family | |
| persian_speed.png | tok/s | |
| persian_spider.png | 7-axis | |
| persian_improvement.png | delta | |
| persian_nshot.png | 0/1/2/3/5 | |
| persian_temperature.png | 0.0->1.0 | |

Evidence: # Evidence T1.6 — Benchmark & Code Verification

> Generated 2026-08-23T13:09 UTC · Base `/splunk-data/v1/Work_RAG-Server-Setup` · Venv `offline-prep/venv` py3.12.3

## S1.6.1 — Scripts Inventory (LOC...
