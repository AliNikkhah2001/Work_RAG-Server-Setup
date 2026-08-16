# 2026-08-16 — Big-Model Inference + Eval (Gemma-4-31B, Nemotron-49B); 72B download resumption

## Summary (current status)
- **All fully-downloaded GGUF models now verified for inference** via chat completions
  (`scripts/verify_gguf_chat.py`, applies embedded chat template — required because
  **Gemma-4-31B silently emits 0 tokens on raw prompts**; its thinking-channel EOS only
  works through `create_chat_completion`).
- Newly verified this session: **Gemma-4-31B Q4_K_M** ("Hello there!" ✓) and
  **Nemotron-Super-49B Q4_K_M** (coherent RAG definition ✓). Plus re-verified the 5 small
  models (Llama-3.2-3B, Qwen2.5-7B, Mistral-7B, Phi-3 q4+fp16) — all PASS again.
- **Download daemons now run in parallel:**
  1. `rag-dl` (systemd, pid 589229) — on **Nemotron-Ultra-253B Q4** (151 GB), proxy
     retrying.
  2. New resumer (pid 708239): `download_models.py --only Qwen2.5-72B --daemon` — resumed
     **Qwen2.5-72B Q8_0 part 1** (was 26.5 GB stalled → 27.1 GB and growing at 08:05) and
     will continue to the 72B Q4_K_M file after.
- Qwen2.5-72B Q8_0 **part 2/2 is complete** (37.3 GB) but the split can't load until
  part 1 finishes — testing deferred.

## Inference verification (chat completions, H200, n_gpu_layers=-1)
| Model | Load (s) | tok/s | Output |
|---|---|---|---|
| Llama-3.2-3B Q4_K_M | ~1.5 | 128.6 | coherent ✓ |
| Qwen2.5-7B Q4_K_M | ~1.8 | 96.9 | coherent ✓ |
| Mistral-7B Q4_K_M | ~1.5 | 128.7 | coherent ✓ |
| Phi-3-mini q4 | ~3.3 | 99.6 | coherent ✓ |
| Phi-3-mini fp16 | ~7.6 | 105.8 | coherent ✓ |
| **Gemma-4-31B Q4_K_M** | 5.2 | (raw 0 tok; chat OK) | "Hello there!" ✓ |
| **Nemotron-Super-49B Q4_K_M** | 6.3 | 42.7 | coherent ✓ |

## Eval (added Gemma-4 + Nemotron; chat mode; limit 100, temp 0.0)
| Model | MMLU (3subj) | GSM8K | Persian ARC | Persian RC | Mean |
|---|---|---|---|---|---|
| Qwen2.5-7B Q4_K_M | 0.65 | 0.18 | 0.62 | 0.35 | **0.4500** |
| **Gemma-4-31B Q4_K_M** | 0.46 | 0.06 | **0.94** | 0.33 | **0.4475** |
| **Nemotron-49B Q4_K_M** | 0.25 | 0.05 | 0.88 | 0.31 | 0.3725 |
| Llama-3.2-3B Q4_K_M | 0.31 | 0.12 | 0.63 | 0.33 | 0.3475 |
| Mistral-7B Q4_K_M | 0.33 | 0.08 | 0.40 | 0.28 | 0.2725 |
| Phi-3-mini q4 | 0.39 | 0.08 | 0.33 | 0.11 | 0.2275 |

Notes:
- **Gemma-4-31B and Nemotron-49B are exceptionally strong on Persian ARC (0.94 / 0.88)**
  despite mid scores on English MMLU — the bigger multilingual models clearly win on
  Persian comprehension.
- Eval harness updated: `eval_gguf.py --chat` flag added (raw-prompt path fails on
  thinking-channel models). Datasets are cached → run with `HF_HUB_OFFLINE=1` to avoid
  proxy drops during eval.

## Pending
- Qwen2.5-72B Q8_0: wait for part 1 (was 27.1/40 GB), then run inference + eval.
- Nemotron-Ultra-253B, DeepSeek-V4-Flash, MiniMax-M3, Kimi-K3, GLM-5.2 (daemon queue).
- Re-run the 3 stalled files (Gemma-3-27B, Qwen3-30B-A3B) — the 72B resumer pattern
  (`--only <repo>`) can be reused for them.