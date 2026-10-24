# 013 — 2026-10-13 — TRT-LLM champion config, concurrency sweep, promotion

## Current status (2026-10-13 ~10:40 UTC)

- **`gemma-4-31b` champion is now served by TensorRT-LLM on GPU1 `:8010`** (dense CUDA-graph config, `max_batch_size 128`). Promoted in the manager (`POST /admin/triton/promote?backend=trt&url=http://127.0.0.1:8010`); the `:9000` gateway routes `gemma-4-31b` to it (`champion_promoted=true`), with automatic fallback to the llama.cpp pool if `:8010` is down.
- **Peak measured: ~3874 tok/s at concurrency 128** (vs llama.cpp GGUF ~58 tok/s) = **~67× aggregate** via continuous batching. Single-stream is near parity (50 vs 58 tok/s; TRT is BF16, llama.cpp Q4_K_XL).
- **Quantization could NOT be enabled** in this environment (see below): FP8 KV cache crashes; weight FP8 needs a ModelOpt/quantized checkpoint (not installed, not producible offline quickly). So all TRT-LLM numbers are **BF16**.
- Launcher now defaults to the champion config: `bash scripts/serve_trtllm.sh` → `max_batch_size 128`, `max_num_tokens 16384`, `--extra_llm_api_options scripts/trtllm_extra_options.yaml`.

## Final benchmark (2026-10-13, `scripts/bench_trtllm_vs_llamacpp.py`)

Same Persian prompt, `max_tokens=256`, temp 0.3, 5 repeats, tokens re-encoded with the shared gemma tokenizer (llama.cpp `:18000` returns no `usage`).

| conc | llama.cpp Q4 (`:18000`, GPU0) agg tok/s | TRT-LLM BF16 (`:8010`, GPU1) agg tok/s | TRT speedup | TRT per-req tok/s | TRT p50 |
|-----:|------:|------:|------:|------:|------:|
| 1    | 57.6  | 50.5   | 0.88×  | 50.5 | 5066 ms |
| 4    | 59.1  | 194.5  | 3.38×  | 48.7 | 5257 ms |
| 8    | 59.4  | 386.2  | 6.51×  | 48.4 | 5289 ms |
| 16   | —     | 764.5  | 13.3×  | 47.9 | 5344 ms |
| 32   | —     | 1384.5 | 24.0×  | 43.5 | 5837 ms |
| 64   | —     | 2423.9 | 42.1×  | 38.2 | 6707 ms |
| 128  | —     | **3874.2** | **67.3×** | 30.7 | 8317 ms |

(llama.cpp `:18000` is the single-slot `llama_chat_server.py` placeholder — it does not batch, so its aggregate is flat at ~58–59 and its latency degrades linearly; cap its concurrency in benchmarks.)

Result JSONs: `logs/bench_trtllm_vs_llamacpp_20261013_*.json` (several sweeps).

## Key discovery: CUDA-graph batch-size cliff

TRT-LLM captures decode CUDA graphs only for the batch sizes in `cuda_graph_config` — **default `[1..32, 64, 128]`**. At any other concurrency (e.g. 33–63, 96) decode runs **eager** and throughput collapses:

| conc | default graphs | dense graphs |
|-----:|-------:|-------:|
| 40 | ~560  | ~1580 |
| 48 | ~670  | ~1860 |
| 56 | ~670  | ~1540 |
| 96 | ~1050 | ~2900 |

Fix: widen `cuda_graph_config.batch_sizes` (kept ≤ 128). This is now the default in `scripts/trtllm_extra_options.yaml`. Trade-off: a very dense set reserves more memory and can trim a few % off the pure-128 peak, so the chosen set is "dense enough" (fills the real gaps, not every integer up to 128).

## Limits / things that did NOT work

- **`--kv_cache_dtype fp8` crashes** the executor at profiling: `RuntimeError: No supported CUDA architectures found for major versions [10, 11, 12]` (during `profiling_executor_creation`). Not pursued (would need the FlashInfer FP8 kernel JIT to target the composed CUDA-13.2 toolkit correctly). BF16 KV works.
- **Weight FP8 not available**: no `modelopt` in the venv and no pre-quantized `gemma-4` checkpoint offline. The PyTorch backend loads quantized weights only from a checkpoint carrying `hf_quant_config`; there is no on-the-fly BF16→FP8 flag. (If desired later: `nvidia-modelopt` quantization pass, then serve the quantized checkpoint.)
- **Batch 256 CUDA graph capture fails**: `aligned_alloc ... batch_prefill_tmp_v size 401604608 ... only 335544320 bytes` — FlashInfer prefill workspace too small. 128 is the practical concurrency ceiling on this build.
- **Throughput is power/state sensitive**: the batch-128 number is a **~3.8k tok/s first-burst**; under sustained back-to-back load it settles to **~2.9k tok/s** (`SW Power Capping` ~160 s accumulated). Single measurements are unreliable; the sweep above is warm but not throttled. For production sizing use the sustained figure.

## Files touched

- `scripts/serve_trtllm.sh` — defaults now `max_batch_size 128`, `max_num_tokens 16384`, KV-dtype/max-tokens overridable via `TRTLLM_*` env.
- `scripts/trtllm_extra_options.yaml` — champion config (FLASHINFER + dense decode graphs ≤128).
- `scripts/trtllm_extra_options_b128dense.yaml`, `..._b128min.yaml`, `..._b256.yaml` — sweep variants (b256 not usable: capture overflow).
- `scripts/bench_trtllm_vs_llamacpp.py` — direct-endpoint A/B benchmark (shared-tokenizer counts).
- `docs/findings.md` — CUDA-graph cliff, KV-fp8 crash, batch-256 workspace, power sensitivity.
