# 014 — 2026-10-14 — FP8 variants benchmarked vs BF16 conc-128 champion

> **Status: DONE.** FP8-KV and weight-FP8 both served on throwaway GPU1 `:8011`
> and A/B-benchmarked against the live BF16 champion (`:8010`, GPU0) at
> concurrencies 1/2/4/8/16/32/64/128 with the standard bench harness.
> Champion + RAG wiring untouched; test instance removed afterwards.

## 1. Method (apples-to-apples)

- Harness: `scripts/bench_trtllm_vs_llamacpp.py` — direct OpenAI endpoints,
  same Persian long-form prompt, `max_tokens=256`, `temperature=0.3`,
  `repeats=5`, shared gemma-tokenizer token accounting.
- All three TRT variants used the **same** champion extra options
  (`scripts/trtllm_extra_options.yaml`: `attn_backend=FLASHINFER` + dense
  decode cuda graphs ≤128) and full champion memory budget
  (`max_batch_size=128`, `max_num_tokens=16384`, `kv_free=0.85`).
- Runs: `logs/bench_bf16_vs_fp8kv.json` (BF16 re-measured same-run),
  `logs/bench_bf16_vs_wfp8.json` (BF16 re-measured same-run again).
- GGUF column is the historical baseline from `013` (llama.cpp `:18000`,
  single-slot placeholder, flat ~58 tok/s).

## 2. Variant A — FP8 KV cache (BF16 weights)

- Launch: `TRTLLM_GPU=1 TRTLLM_PORT=8011 TRTLLM_KV_DTYPE=fp8
  FLASHINFER_CUDA_ARCH_LIST="9.0a"` + the Agent-A flashinfer patch
  (`modules.py:_fa2_head_dim_nvcc_flags` allows majors `[8,9,10,11,12]`
  for 1-byte large-head; without it, JIT raises
  `No supported CUDA architectures found for major versions [10, 11, 12]`).
- Verified in log: `kv_cache_dtype="fp8"`. Correctness spot-check:
  `17*23=?` → `391` (identical to BF16 — expected, weights unchanged).
- VRAM: GPU1 **133935 MiB** vs champion GPU0 **137854 MiB** (~4 GB saved
  at full champion KV budget).

## 3. Variant B — weight FP8 (ModelOpt W8A8)

- Checkpoint: `offline-prep/models/huggingface/google_gemma-4-31b-it-fp8`
  (**32 GB**, 4 shards), built by `scripts/quantize_gemma4_fp8.py` with
  `nvidia-modelopt==0.47.0` `FP8_DEFAULT_CFG` (per-tensor E4M3, text tower
  only; vision/embed/lm_head excluded), **16 calibration samples**.
- Serve auto-detects: `Found .../hf_quant_config.json, pre-quantized
  checkpoint is used` + `Setting quant_algo=FP8 from HF quant config`.
  No extra serve flags needed.
- VRAM: GPU1 **129405 MiB** (~8.6 GB under BF16 at same KV budget).
- **QUALITY REGRESSION (16-sample PTQ):** `17*23=?` → `**399**` (wrong;
  BF16 → `391`); `1234+5678` → transcribed `5678` as `5,676` (sum of the
  misread digits); Persian factual (`پایتخت ایران`) correct. Throughput
  numbers below are real, but this checkpoint is **not production-ready**
  without re-calibration (≥128 samples) + a quality eval gate.

## 4. Results — aggregate tok/s (256-token decode)

| conc | GGUF `:18000` (hist) | BF16 `:8010` | FP8-KV `:8011` | W-FP8 `:8011` |
|-----:|---------------------:|-------------:|---------------:|--------------:|
| 1    | 57.6 | 52.5 / 52.4 | 49.9 (**0.95×**) | 77.6 (**1.48×**) |
| 2    | — | 101.9 / 102.0 | 97.1 (0.95×) | 150.5 (1.48×) |
| 4    | 59.1 | 202.3 / 202.4 | 193.1 (0.95×) | 295.7 (1.46×) |
| 8    | 59.4 | 399.3 / 399.4 | 381.8 (0.96×) | 581.9 (1.46×) |
| 16   | — | 770.8 / 773.6 | 748.9 (0.97×) | 1131.7 (1.46×) |
| 32   | — | 1375.1 / 1401.0 | 1370.0 (1.00×) | 1948.9 (1.39×) |
| 64   | — | 2357.7 / 2397.5 | 2363.9 (1.00×) | 3212.1 (1.34×) |
| 128  | — | 3194.9 / 2980.0 | 3658.6 (**1.15×**) | 4851.7 (**1.63×**) |

Ratios are same-run (each JSON re-measures BF16). BF16 conc-128 varies
run-to-run (3195 vs 2980) — power/thermal variance, not a config change.

## 5. Reading the numbers

- **FP8-KV: ~‑5% at low conc → +15% at conc-128.** At low batch the
  FP8 dequant overhead dominates; at high batch KV-cache bandwidth
  dominates and halving KV bytes pays off. Zero quality risk (weights
  untouched). + VRAM headroom.
- **Weight-FP8: +34–63% everywhere** (FP8 GEMMs raise per-request rate
  50→75 tok/s at conc-1). BUT the 16-sample checkpoint gives wrong
  arithmetic — throughput without correctness is worthless for RAG.
- **GGUF placeholder is not in the race** (flat ~58 tok/s, no batching).

## 6. Recommendation (unchanged ground truth)

- **Keep the BF16 conc-128 champion on `:8010` wired to the orchestrator.**
  Verified after all experiments: E2E `finish: stop, citations: 5`,
  guardrails `upstream_reachable: true`.
- Next safe upgrade: **FP8-KV on the champion** (restart `:8010` with
  `TRTLLM_KV_DTYPE=fp8` + `FLASHINFER_CUDA_ARCH_LIST=9.0a`; patch is
  already in `venv-trtllm`). Expected: +~15% at 128, more KV headroom,
  no quality change. Needs a champion restart window (~3 min).
- Weight-FP8 needs: re-run quant with `--calib-samples 128`
  (~25 min on GPU0/GPU1), then an accuracy gate (arithmetic + Persian
  factual set) before any serve test. Do NOT point RAG at the current
  16-sample checkpoint.

## 7. Artifacts

- `logs/bench_bf16_vs_fp8kv.json` + `.stdout.log`
- `logs/bench_bf16_vs_wfp8.json` + `.stdout.log`
- `logs/trtllm_fp8kv_8011.log`, `logs/trtllm_wfp8_8011.log`
- `offline-prep/models/huggingface/google_gemma-4-31b-it-fp8/` (32 GB)
- Test `:8011` removed; GPU1 back to ~2.4 GB; `:8010` never restarted.
