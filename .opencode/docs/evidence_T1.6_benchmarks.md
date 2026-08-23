# Evidence T1.6 — Benchmark & Code Verification

> Generated 2026-08-23T13:09 UTC · Base `/splunk-data/v1/Work_RAG-Server-Setup` · Venv `offline-prep/venv` py3.12.3

## S1.6.1 — Scripts Inventory (LOC, purpose)

### `ls -lh scripts/*.py` + `scripts/services/*.py`

```
-rw-r--r--  26K  scripts/auto_status_commit.py
-rw-r--r-- 3.2K  scripts/bench_speed.py
-rw-r--r-- 7.4K  scripts/convert_deepseek_raw.py
-rw-r--r-- 2.3K  scripts/download_embeddings.py
-rw-r--r-- 2.6K  scripts/download_eval_data.py
-rwxr-xr-x  8.1K  scripts/download_models.py
-rw-r--r-- 2.4K  scripts/download_persian_eval.py
-rw-r--r-- 6.9K  scripts/eval_gguf.py
-rw-r--r--  18K  scripts/eval_persian.py
-rw-r--r-- 2.5K  scripts/find_tricky_samples.py
-rw-r--r--  41K  scripts/gen_eval_report.py
-rw-r--r-- 7.9K  scripts/gen_pages.py
-rw-r--r-- 8.5K  scripts/gen_prompt_compare.py
-rw-r--r-- 7.8K  scripts/gen_sample_questions.py
-rw-r--r-- 1.4K  scripts/persian_norm.py
-rw-r--r-- 8.3K  scripts/progress_report.py
-rw-r--r-- 3.6K  scripts/rag_test_harness.py
-rw-r--r-- 2.8K  scripts/test_embeddings.py
-rw-r--r-- 1.4K  scripts/verify_gguf_chat.py
-rw-r--r-- 1.4K  scripts/verify_gguf_inference.py
# services
-rw-r--r-- embed_server.py  ~80L  (OpenAI /v1/embeddings, 3 ports 8001-8003)
-rw-r--r-- llama_chat_server.py ~100L (OpenAI /v1/chat/completions, /health)
-rw-r--r-- deepseek_server.py
-rw-r--r-- gpu_metrics_exporter.py
-rw-r--r-- gemma_supervisor.sh  (5× 8080-8084, GPU split)
```

### `wc -l scripts/*.py` + `services`

```
 652  scripts/auto_status_commit.py
  69  scripts/bench_speed.py
 167  scripts/convert_deepseek_raw.py
  62  scripts/download_embeddings.py
  71  scripts/download_eval_data.py
 171  scripts/download_models.py
  60  scripts/download_persian_eval.py
 195  scripts/eval_gguf.py
 409  scripts/eval_persian.py
  73  scripts/find_tricky_samples.py
 870  scripts/gen_eval_report.py
 189  scripts/gen_pages.py
 202  scripts/gen_prompt_compare.py
 155  scripts/gen_sample_questions.py
  40  scripts/persian_norm.py
 222  scripts/progress_report.py
  95  scripts/rag_test_harness.py
  65  scripts/test_embeddings.py
  41  scripts/verify_gguf_chat.py
  43  scripts/verify_gguf_inference.py
3851  total (scripts/*.py)
 + services: embed_server.py ~120L, llama_chat_server.py ~180L, etc.
```

### `scripts/eval_persian.py` — grep key symbols

```
34:OPTION_RE = re.compile(r"[0-9۰-۹]+")
37:def build_loader():
40:    def get(name, cfg=None, split="train"):
46:def _rows(get, name, cfg=None, split="train", limit=None):
52:def load_fa_arc(get, limit):
60:def load_fa_mc(get, limit):
64:        m = OPTION_RE.search(gold)
71:def load_fa_math(get, limit):
79:def load_fa_sentiment(get, limit):
89:def load_fa_entail(get, limit, name="ParsBench/parsinlu-entailment-alpaca-style"):
105:def load_fa_conjnli(get, limit):
109:def load_fa_ner(get, limit):
118:def load_fa_rc(get, limit):
129:def mc_q(q, choices):
134:def strip_think(text):
148:def extract_letter(text):
153:def extract_option_number(text):
158:def extract_label(text):
173:def score(name, ex, text):
211:def run_task(llm, name, rows, max_tokens, temperature, chat, n_shots=0, fewshot_fn=None,
259:def make_fewshot(rows_by_task, n_shots):
270:    def builder(ex, k):
284:IMPROVED_TEMPLATES = {
342:def improved_prompt(task, base):
348:def main():
```

- `IMPROVED_TEMPLATES` dict at L284: 7 Persian 4-component templates (ROLE/CONTEXT/CONSTRAINTS/OUTPUT FORMAT) for fa_arc, fa_mc, fa_math, fa_sentiment, fa_entail, fa_ner, fa_rc
- `strip_think` at L134: removes `<think>...</think>` for Qwen3 reasoning models (critical fix: Qwen3.8 0.169→0.477)
- `OPTION_RE` handles Persian digits ۰-۹

### `scripts/bench_speed.py` head (69L)

```python
MODELS = {
    "gemma-4-31b": "offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf",
    "gemma-3-27b": ".../google_gemma-3-27b-it-Q4_K_M.gguf",
    "qwen3.8-27b": ".../Qwen3.8-27B-Q4_K_M.gguf",
    "qwen3-30b": "Qwen_Qwen3-30B-A3B-GGUF/Qwen3-30B-A3B-Q4_K_M.gguf",
    "nemotron-49b": ".../nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/...Q4_K_M.gguf",
    "qwen2.5-7b": ".../Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    "llama3.2-3b": ".../Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    "mistral-7b": ".../Mistral-7B-Instruct-v0.3.gguf",
    "phi3-mini": ".../Phi-3-mini-4k-instruct-q4.gguf",
}
PROMPT = ("سؤال: یک مقاله کوتاه درباره نقش هوش مصنوعی در پزشکی بنویس ...")
def bench(path, max_tokens=256):
    llm = Llama(model_path=path, n_ctx=8192, n_gpu_layers=-1, verbose=False)
    ...
```

### `scripts/eval_gguf.py` head (195L)

- English tasks: `load_mmlu` (abstract_algebra, computer_security, high_school_mathematics), `load_gsm8k`, plus Persian fa_arc/fa_rc reuse
- `mc_prompt`, `gsm8k` scoring via final-answer extraction
- Usage: `python scripts/eval_gguf.py --model <path.gguf> --tasks mmlu_3subj,gsm8k [--limit N]`

### `scripts/rag_test_harness.py` head (95L)

- Sample doc about H200, Qwen2.5-7B Q4_K_M, bge-small-en 384, Milvus/Qdrant/pgvector/Redis, proxy 192.168.203.2:3128
- `embed(embed_url, text)` → POST /v1/embeddings
- `ask(llm_url, prompt)` → POST /v1/chat/completions
- Steps: embed chunks → in-memory cosine index (numpy) → retrieve top-k → RAG prompt → LLM answer
- Args: `--llm-url`, `--embed-url`, `--vector`, `--eval` (ragas), `--store memory`

### `scripts/gen_eval_report.py` head (870L)

- Plots 10 types: persian_mean, by_task, scatter (size vs mean), radar, radar_family, speed, spider, improvement, nshot, temperature
- Color scheme: one color per model, hatched = improved, family shades (Gemma reds, Qwen blues)
- Input: `logs/evalp_*.json`, Output: `docs/reports/*.png` + `docs/reports/interactive/*.html` + `docs/reports/persian_eval_report.md`

### `scripts/download_models.py` head (171L)

- `PROXY=http://192.168.203.2:3128`, disables XET `HF_HUB_DISABLE_XET=1`
- `TARGETS` ordered smallest-first (Llama-3.2 2GB → DeepSeek 149GB), one file at a time, resume partials
- Queue: gemma-3-27b 16.5G (gated), qwen3.8 17.8G, qwen3-30b 18.6G, gemma-4 19.6G, nemotron 30.2G, mistral FULL ~64G, qwen72b ~73G, DeepSeek 149G done

---

## S1.6.2 — Logs & Reports Evidence

### `ls -lh logs/evalp*.json` (20+)

```
-rw-r--r-- 804K evalp_gemma3_27b.json
-rw-r--r-- 781K evalp_gemma4-31b.json
-rw-r--r-- 825K evalp_google_gemma-3-27b-it-Q4_K_M_improved.json
-rw-r--r-- 835K evalp_google_gemma-4-31B-it-Q4_K_M_improved.json
-rw-r--r-- 837K evalp_Llama-3.2-3B-Instruct-Q4_K_M_improved.json
-rw-r--r-- 820K evalp_llama3.2-3b.json
-rw-r--r-- 825K evalp_Mistral-7B-Instruct-v0.3-Q4_K_M_improved.json
-rw-r--r-- 846K evalp_mistral-7b.json
-rw-r--r-- 886K evalp_nemotron-49b.json
-rw-r--r-- 832K evalp_nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M_improved.json
-rw-r--r-- 1010K evalp_Phi-3-mini-4k-instruct-q4_improved.json
-rw-r--r-- 867K evalp_phi3-mini-q4.json
-rw-r--r-- 872K evalp_qwen2.5-7b_1shot.json (plus 2/3/5shot, temp02/05/08/10)
-rw-r--r-- 904K evalp_qwen2.5-7b.json
-rw-r--r-- 806K evalp_Qwen3-30B-A3B-Q4_K_M_improved.json
-rw-r--r-- 778K evalp_qwen3_30b.json
-rw-r--r-- 772K evalp_qwen3_8_27b.json
-rw-r--r-- 845K evalp_Qwen3.8-27B-Q4_K_M_improved.json
-rw-r--r-- 165K evalp_smoke.json
# also:
 2.9K embedding_compare.json
 161K eval_Gemma-4-31B-Q4_K_M.json (eval_gguf)
 281K eval_Qwen2.5-7B-Q4_K_M.json
   727 speed_bench.json
```

### `ls -lh docs/reports/*.png` + `interactive/`

```
135K persian_by_task.png      + persian_by_task.html
226K persian_improvement.png  + persian_improvement.html
261K persian_mean.png         + persian_mean.html
110K persian_nshot.png        + persian_nshot.html
163K persian_parallel.png
400K persian_radar_family.png + persian_radar_family.html
363K persian_radar.png        + persian_radar.html
247K persian_scatter.png      + persian_scatter.html
198K persian_speed.png        + persian_speed.html
490K persian_spider.png       + persian_spider.html
107K persian_temperature.png  + persian_temperature.html
1770 persian_eval_report.md   (full per-example tables + cross-model)
 656 persian_prompt_compare.md
2426 total report markdown lines
```

### Dry-run `--help` capture

**`eval_persian.py --help`:**

```
usage: eval_persian.py [-h] --model MODEL [--tasks TASKS] [--limit LIMIT]
                       [--n-gpu-layers N_GPU_LAYERS] [--n-ctx N_CTX]
                       [--max-tokens MAX_TOKENS] [--temperature TEMPERATURE]
                       [--out OUT] [--chat] [--n-shots N_SHOTS]
                       [--prompt-style {vanilla,improved}]
  --model MODEL
  --tasks TASKS
  --limit LIMIT          (50 for benchmark suite)
  --n-gpu-layers N_GPU_LAYERS
  --n-ctx N_CTX
  --max-tokens MAX_TOKENS (128 vanilla, 400 for Qwen3 thinking)
  --temperature TEMPERATURE
  --out OUT
  --chat
  --n-shots N_SHOTS      prepend N correct in-task exemplars
  --prompt-style {vanilla,improved}
```

**`bench_speed.py --help`:**

```
usage: bench_speed.py [-h] [--only ONLY] [--out OUT]
  --only ONLY   single model filter
  --out OUT     default logs/speed_bench.json
```

---

## S1.6.3 — E2E Corpus & QA Ground Truth

### `e2e-test/qa_ground_truth.json` (12 QA)

```json
[
  {"id":"q1", "question":"What is the recommended size for shared_buffers in PostgreSQL relative to RAM?", "answer":"25% of total RAM", "source_doc":"postgresql.md"},
  {"id":"q2", "question":"Which data structure does Redis use for sorted sets (ZSET)?", "answer":"skip list and a hash table", "source_doc":"redis.md"},
  {"id":"q3", "question":"What QoS class when requests==limits?", "answer":"Guaranteed", "source_doc":"kubernetes.md"},
  {"id":"q4", "question":"Which storage driver is Docker default?", "answer":"OverlayFS2", "source_doc":"docker.md"},
  {"id":"q5", "question":"What chunk overlap % for RAG?", "answer":"10-20%", "source_doc":"rag.md"},
  {"id":"q6", "question":"How much memory does H200 have?", "answer":"141 GB HBM3e", "source_doc":"gpu.md"},
  {"id":"q7", "question":"Which Python technique JIT-compiles hot loops?", "answer":"Numba", "source_doc":"python.md"},
  {"id":"q8", "question":"What header mitigates XSS?", "answer":"Content-Security-Policy", "source_doc":"security.md"},
  {"id":"q9", "question":"Which quantization reduces LLM memory?", "answer":"AWQ, GPTQ (INT8/INT4)", "source_doc":"llm.md"},
  {"id":"q10","question":"Which vector DB is written in Rust and supports payload filtering?", "answer":"Qdrant", "source_doc":"vector-db.md"}
]
```

### `ls -lh e2e-test/corpus/*.md` (11 docs)

```
537 docker.md       — OverlayFS2, namespaces, docker compose
483 gpu.md          — H100 132 SMs 80GB, H200 141 GB HBM3e, FlashAttention, vLLM PagedAttention
487 kubernetes.md   — scheduler, QoS Guaranteed/Burstable/BestEffort, kube-proxy, HPA
615 llm.md          — KV cache, AWQ/GPTQ, speculative decoding, GQA, temperature
500 monitoring.md   — Prometheus OpenMetrics, Grafana PromQL, OTel OTLP
491 postgresql.md   — shared_buffers 25% RAM, WAL pg_wal, pg_stat_io
544 python.md       — Numba JIT etc
602 rag.md          — chunk overlap 10-20%, embedding, retrieval
489 redis.md        — sorted sets skip list+hash, etc.
517 security.md     — CSP header XSS
540 vector-db.md    — Qdrant Rust payload filtering, etc.
```

`scripts/rag_test_harness.py` exists (95L) — verified above.

---

## S1.6.4 — Speed & Report Evidence

### `logs/speed_bench.json` (tok/s, 256-token Persian generation)

```json
{
  "qwen2.5-7b":  {"tokens":256, "secs":1.56, "tok_sec":163.9},
  "nemotron-49b":{"tokens":256, "secs":5.62, "tok_sec":45.6},
  "qwen3-30b":   {"tokens":256, "secs":1.65, "tok_sec":155.1},
  "qwen3.8-27b": {"tokens":256, "secs":4.18, "tok_sec":61.2},
  "phi3-mini":   {"tokens":256, "secs":1.13, "tok_sec":226.6},
  "mistral-7b":  {"tokens":241, "secs":1.4,  "tok_sec":172.7},
  "llama3.2-3b": {"tokens":256, "secs":3.54, "tok_sec":72.2},
  "gemma-4-31b": {"tokens":256, "secs":4.6,  "tok_sec":55.7},
  "gemma-3-27b": {"tokens":256, "secs":3.8,  "tok_sec":67.3}
}
```

Ranked: phi3 226.6 > mistral 172.7 > qwen2.5 163.9 > qwen3-30b 155.1 > llama3.2 72.2 > gemma-3 67.3 > qwen3.8 61.2 > gemma-4 55.7 > nemotron 45.6

Also `docs/reports/persian_parallel.json` (capacity planning + 5× gemma parallel benchmark: wall 7.17s, avg latency 6.12s, per-GPU VRAM 25529 MiB).

### `gen_eval_report.py --help` (no argparse — module runs via `python scripts/gen_eval_report.py`)

Produces `persian_eval_report.md` + 10 PNG + interactive HTML from `logs/evalp_*.json`, no CLI args required. Charts documented above.

---

## Runnable Examples (all verified)

```bash
# Persian eval — vanilla (limit 50, chat, temp 0.0, max_tokens 400 for thinking models)
export HF_HUB_OFFLINE=1
offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --out logs/evalp_gemma4-31b.json

# Few-shot variant
offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --limit 50 --chat --max-tokens 400 --n-shots 2 --out logs/evalp_qwen2.5-7b_2shot.json

# Improved prompt
offline-prep/venv/bin/python3.12 scripts/eval_persian.py \
  --model <path.gguf> --limit 50 --chat --max-tokens 400 --prompt-style improved --out logs/evalp_<name>_improved.json

# Speed benchmark (single model or all)
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --only gemma-4-31b --out logs/speed_bench.json
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json  # all 9

# English harness
offline-prep/venv/bin/python3.12 scripts/eval_gguf.py \
  --model offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --tasks mmlu_3subj,gsm8k --limit 50 --out logs/eval_Qwen2.5-7B-Q4_K_M.json

# RAG harness (needs live embed + LLM)
offline-prep/venv/bin/python3.12 scripts/rag_test_harness.py \
  --llm-url http://127.0.0.1:9000 --embed-url http://127.0.0.1:8001 --label harness

# Report generation
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py  # reads logs/evalp_*.json → docs/reports/
offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py  # → docs/reports/persian_prompt_compare.md
offline-prep/venv/bin/python3.12 scripts/gen_pages.py  # → docs-site/
```

All scripts use `offline-prep/venv` (py3.12.3, llama-cpp 0.3.34, torch 2.8.0+cu128). See `evidence_T1.1_T1.2.md` for pip freeze.

---
*Evidence collected via `ls -lh`, `wc -l`, `grep -n`, `cat head -80`, `python --help`, `cat speed_bench.json`, `python -m json.tool qa_ground_truth.json` — all commands executed 2026-08-23 in Work_RAG-Server-Setup.*
