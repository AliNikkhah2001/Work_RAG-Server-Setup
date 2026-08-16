# 2026-08-15 — Model Evaluation (Conventional + Persian)

## Summary (current status)
- Downloaded eval datasets (cached via `datasets`): **GSM8K** (en), **MMLU** 3 subjects
  (abstract_algebra, computer_security, high_school_mathematics), **Persian ARC-Easy**
  (`MatinaAI/persian_arc`), **Parsinlu reading comprehension**
  (`community-datasets/parsinlu_reading_comprehension`).
- Downloaded **multilingual/Persian embedding models** (SentenceTransformer format) into
  `offline-prep/models/huggingface/`:
  - `intfloat_multilingual-e5-small` — **DONE** (dim 384, verified on CUDA; embeds Persian
    coherently, e.g. cos("سلام دنیا", Persian AI text) ≈ 0.81).
  - `sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2` — **DONE** (dim 384,
    verified; took ~5 proxy retries on the ~250 MB safetensors).
  - `BAAI_bge-m3` — **DONE** (dim 1024, verified on CUDA; cos("پایتخت ایران تهران است",
    "The capital of Iran is Tehran") ≈ 0.32 — cross-lingual Persian↔English alignment OK).
  - Downloader: `scripts/download_embeddings.py` (infinite-retry, skips onnx/openvino).
- Evaluation harness: `scripts/eval_gguf.py` (llama.cpp backend, no lm-eval-harness needed).
  Tasks: `mmlu_3subj`, `gsm8k`, `fa_arc`, `fa_rc`; limit 100 rows/task, temperature 0.0.
- Note: `allenai/arc-easy` repo ID doesn't exist anymore (404) — dropped from the conventional set.

## Results (limit=100, n_gpu_layers=-1, temp 0.0)
| Model | MMLU (3subj) | GSM8K | Persian ARC | Persian RC | **Mean** |
|---|---|---|---|---|---|
| Llama-3.2-3B Q4_K_M | 0.31 | 0.12 | 0.63 | 0.33 | **0.3475** |
| Qwen2.5-7B Q4_K_M | 0.65 | 0.18 | 0.62 | 0.35 | **0.4500** |
| Mistral-7B v0.3 Q4_K_M | 0.33 | 0.08 | 0.40 | 0.28 | **0.2725** |
| Phi-3-mini q4 | 0.39 | 0.08 | 0.33 | 0.11 | **0.2275** |

Observations:
- Qwen2.5-7B is the best overall (0.45); strong on English MMLU (0.65) and respectable on
  Persian ARC (0.62). Expect higher with chat-template prompts + few-shot (harness uses
  raw instruct-style zero-shot).
- GSM8K scores are low across the board (0.08–0.18) — expected for 3–7B models zero-shot;
  the harness already falls back to "last number" extraction.
- Persian RC (extractive containment metric) is hard zero-shot: answers are long spans,
  exact containment rarely matched. Persian ARC (letter choice) is the more reliable
  Persian signal.
- Raw per-row outputs in `logs/eval_<model>.json`.

## Next steps
- Re-run with higher limit + few-shot when Gemma-3-27B, Qwen3-30B-A3B, Qwen2.5-72B finish
  downloading (daemon `rag-dl` active).
- All 3 Persian-capable embedding models verified loading + embedding Persian text on CUDA
  (see Summary). Optionally point the RAG harness (`scripts/rag_test_harness.py`) at a
  Persian embedding server to sanity-check retrieval in Persian.