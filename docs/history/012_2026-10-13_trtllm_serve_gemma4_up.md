# 012 — 2026-10-13 — TensorRT-LLM 1.3.0rc29 SERVING gemma-4-31b (four blockers fixed)

## Current status (2026-10-13 ~00:45 UTC)

- **`trtllm-serve` is UP and serving `gemma-4-31b`** on **GPU1 `:8010`** (`google_gemma-4-31b-it`, PyTorch backend, tp_size 1). ~136 GB GPU (110 GB weights + KV), `/v1/models` + `/v1/chat/completions` verified.
- Single-stream decode **~47–50 tok/s** (batch 1, FLASHINFER attention). Smoke: `17*23 → 391`.
- **Next:** register/promote `gemma-4-31b-trtllm` in the manager (`:9000`) and run the GGUF (llama.cpp) vs TensorRT-LLM benchmark.

## What blocked us (all four had to be fixed together)

The 1.3.0rc29 venv installed fine on 2026-10-12 (see 011) but `trtllm-serve` never came up. Diagnostic tool: `py-spy dump` on the hung processes.

1. **mpi4py dynamic `MPI_Comm_spawn` deadlock.** Bare `trtllm-serve` builds a `MpiPoolSession` → `MPIPoolExecutor` → `MPI_Comm_spawn`. Here the parent spins in `client_sync`/`bcast_send` and the spawned worker in `server_sync`/`bcast_recv` — a permanent deadlock (one core pinned). A trivial 10-line `MPIPoolExecutor` test reproduces it, so it is the OpenMPI 4.1.6 spawn path, not TRT-LLM. `mpirun -n 1`/`-n 2` work.
   - **Fix:** `mpirun -n 1 <venv>/bin/trtllm-llmapi-launch <venv>/bin/trtllm-serve serve ...`. The launcher exports `TLLM_SPAWN_PROXY_PROCESS=1`, switching to the mgmn leader/worker + `RemoteMpiCommSessionClient` IPC path (no `MPI_Comm_spawn`).
2. **`trtllm-llmapi-launch` runs bare `python3`.** It execs `python3 -m tensorrt_llm.llmapi.mgmn_leader_node`; system `python3` has no `tensorrt_llm` → leader `exit 1` → serve hangs.
   - **Fix:** `export PATH="$VENV/bin:$PATH"` (venv first).
3. **FlashInfer JIT nvcc too old.** FlashInfer 0.6.18 compiles kernels at startup with `-Xfatbin=-compress-all --compress-mode=size` (needs CUDA ≥12.8); host `/usr/bin/nvcc` is CUDA 12.0 → `nvcc fatal : Unknown option '--compress-mode=size'` → ninja build fails.
   - **Fix:** compose a CUDA 13.2 toolkit inside the venv from pypi.nvidia.com: `nvidia-cuda-nvcc==13.2.86` (→`bin/nvcc`), `nvidia-cuda-crt==13.2.86` (→`include/crt/host_config.h`), `nvidia-nvvm==13.2.86` (→`nvvm/bin/cicc`), landing under `site-packages/nvidia/cu13/`. Set `CUDA_HOME` to it, prepend `$CUDA_HOME/bin` to `PATH`, add `$CUDA_HOME/lib` to `LD_LIBRARY_PATH`, and `ln -s libcudart.so.13 libcudart.so`.
4. **Gemma4 per-layer `head_dim` vs MMHA.** `global_head_dim=512` (full-attention layers) vs `head_dim=256` (sliding). Default gemma4 backend is `TRTLLM` (MMHA) which asserts `Head size 512 is not supported by MMHA` (`attentionOp.cpp:2954`) during warmup.
   - **Fix:** `attn_backend: FLASHINFER` via `--extra_llm_api_options scripts/trtllm_extra_options.yaml` (explicit option overrides the model default; verified `attn_backend='FLASHINFER'` in the final LLM-args dump). `VANILLA` is the fallback.

## Working launch recipe

```bash
# scripts/serve_trtllm.sh encodes all of this; key env:
CU13=$VENV/lib/python3.12/site-packages/nvidia/cu13
export CUDA_HOME=$CU13
export PATH=$CU13/bin:$VENV/bin:$PATH
export LD_LIBRARY_PATH=$(find $VENV/lib/python3.12/site-packages/nvidia -maxdepth 3 -type d -name lib | paste -sd:):$CU13/lib
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export HF_HOME=.../models/huggingface HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export no_proxy=localhost,127.0.0.1 CUDA_VISIBLE_DEVICES=1

mpirun -n 1 $VENV/bin/trtllm-llmapi-launch $VENV/bin/trtllm-serve serve \
  offline-prep/models/huggingface/google_gemma-4-31b-it \
  --host 0.0.0.0 --port 8010 --backend pytorch --tp_size 1 \
  --max_batch_size 8 --max_seq_len 8192 --kv_cache_free_gpu_memory_fraction 0.85 \
  --extra_llm_api_options scripts/trtllm_extra_options.yaml
```

Startup timeline (GPU1 memory): ~110 GB weights at ~60 s, JIT + memory profiling to ~160 s, ready by ~180 s.

## Harmless warnings seen

`Could not load AutoProcessor for Gemma4` (manual fallback, text OK); `MetaInitException → Fallback to regular model init`; flashinfer cutile "mismatched nvidia pip packages (tileiras 13.1.80 vs 13.2.86)" (cutile only); `torchao` cpp-ext skip; rope_fusion auto-disabled (backend lacks support).

## Files touched

- `scripts/serve_trtllm.sh` — rewritten for mpirun + llmapi-launch + CUDA 13.2 env + extra options.
- `scripts/trtllm_extra_options.yaml` — `attn_backend: FLASHINFER`.
- `docs/findings.md` — appended "Gemma-4 + TensorRT-LLM 1.3.0rc29 actually SERVING".

## Benchmark: llama.cpp GGUF vs TensorRT-LLM (2026-10-13 ~00:50 UTC)

`scripts/bench_trtllm_vs_llamacpp.py` — hits both endpoints directly (bypasses the `:9000` manager so promotion can't reroute), same Persian prompt, `max_tokens=256`, temperature 0.3, 3 repeats/batch. Completion tokens counted by **re-encoding each output with the shared gemma tokenizer** (llama.cpp `:18000` returns no `usage`), so both sides are real subword tokens.

Targets: `llama_cpp` = `:18000` `/splunk-data/models/gemma-4-31B-it-UD-Q4_K_XL.gguf` (GPU0) · `trtllm` = `:8010` HF BF16 (GPU1).

| concurrency | llama.cpp Q4 (agg tok/s) | TRT-LLM BF16 (agg tok/s) | TRT speedup | llama per-req | TRT per-req |
|-------------|-------------------------:|-------------------------:|------------:|--------------:|------------:|
| 1           | 58.0                     | 50.2                     | **0.87×**   | 58.1          | 50.2        |
| 4           | 58.9                     | 194.5                    | **3.30×**   | 28.1          | 48.7        |
| 8           | 59.4                     | 384.7                    | **6.48×**   | 18.2          | 48.2        |

Read-outs:
- **Single-stream (conc 1): llama.cpp Q4 is ~15% faster** (58 vs 50 tok/s). Expected — Q4 halves bytes/token of BF16, and llama.cpp single-stream is very well tuned.
- **TRT-LLM batches almost perfectly**: per-request throughput stays ~48–50 tok/s from conc 1→8 (agg scales 50→195→385). This is in-flight continuous batching.
- **The llama.cpp `:18000` placeholder does NOT batch**: aggregate is flat at ~58–59 tok/s regardless of concurrency, and per-request latency degrades linearly (4.4s → 10.9s → 19.5s). It is `scripts/services/llama_chat_server.py` (single-slot), not `llama-server` with parallel slots.
- **Not yet apples-to-apples on precision**: TRT-LLM is running **BF16**; the fair TRT-LLM analogue of Q4_K_XL is **FP8**. FP8 should lift single-stream substantially (~2× bandwidth) and is the obvious next lever. Alternatively point llama.cpp at a real multi-slot `llama-server`.

Result JSON: `logs/bench_trtllm_vs_llamacpp_20261013_004953.json`.
