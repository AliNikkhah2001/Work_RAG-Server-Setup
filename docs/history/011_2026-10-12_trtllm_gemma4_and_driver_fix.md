# 011 — 2026-10-12 — Gemma-4 TRT-LLM bring-up, NVIDIA driver mismatch fix

## Current status (2026-10-12 ~07:00 UTC)

- **NVIDIA driver mismatch FIXED** (no reboot): kernel module and userspace both `580.178.04`; `nvidia-smi` + NVML working; 2× H200 NVL visible.
- **All live RAG services healthy** after the module reload (embeds 8001-8003, KB 8000, orchestrator 8100, llama 8104/18000, manager 9000).
- **Runtime decision:** serve champion `gemma-4-31b` (`google_gemma-4-31b-it`, arch `gemma4`) with **TensorRT-LLM `1.3.0rc29` via `trtllm-serve`** (the legacy `trtllm-build` engine path is obsolete for this model).
- **In progress:** building an isolated venv `offline-prep/venv-trtllm` (does not touch the shared live venv). `torch-2.14.0+cu132` downloaded + sha256-verified; `tensorrt_llm-1.3.0rc29` wheel downloading (~35% at time of writing).
- **Next:** finish install → `trtllm-serve` the HF checkpoint → register in manager → benchmark GGUF (llama.cpp) vs TensorRT-LLM.

## Context

Champion is `gemma-4-31b`. The current optimized/"Triton" path (`gemma-4-31b-triton-vllm`, :8104) is only a **host llama.cpp placeholder** (~40 tok/s, speedup 1.0). A real speedup needs an NVIDIA-optimized runtime.

## Why TRT-LLM 1.3.0rc29 (not 1.2.1)

- `tensorrt_llm 1.2.1` was downloaded (`/tmp/tensorrt_llm-1.2.1-cp312-cp312-linux_x86_64.whl`, 2.4G / `2514282461`) and installed into the **shared** venv. Its import initially failed on missing `libcublasLt.so.13` / `libnvrtc.so.13`.
- Fix: downloaded + installed `nvidia-cublas 13.8.1.7` (`439315821` bytes, sha256 `c11a27fd4379510e5b1f84b367a2514d1e52fe5cc13442117a0e0a1addee3cf2`) → `.../nvidia/cu13/lib/libcublas.so.13`. Import then needed `LD_LIBRARY_PATH` over all `site-packages/nvidia/*/lib`.
- **Blocking discovery:** 1.2.1 has **no `gemma4` support** (only gemma3 / gemma3vl), and its pinned `transformers==4.57.3` cannot even parse the `gemma4` config. Gemma 4 support first appears in **`tensorrt_llm 1.3.0rc*`** (NVIDIA/TensorRT-LLM PR #12932), and the old `build_trt_engine.sh` (`trtllm-build --use_fp8`) workflow is **removed** — the supported path is **`trtllm-serve`**.

## NVIDIA driver mismatch (root cause + fix)

- Symptom: after installing 1.2.1, `pynvml.nvmlInit()` raised `NVMLError_LibRmVersionMismatch: RM has detected an NVML/RM version mismatch`; even `nvidia-smi` failed.
- Cause: an `unattended-upgrade` on **2026-10-09 06:39** upgraded the userspace NVIDIA libs to `580.178.04` while the **loaded kernel module stayed `580.173.02`**.
- Fix (user-approved, no reboot): stopped the 7 processes holding `/dev/nvidia*` (embeds 8001-8003, llama 8104, KB 8000, orchestrator 8100, llama 18000), captured their envs to `/tmp/reload_backup/env_*.txt`, `rmmod nvidia_drm nvidia_modeset nvidia_uvm nvidia` then reloaded → kernel now `580.178.04`. DKMS module `580.178.04` verified present for running kernel `6.8.0-138-generic`.
- Recovery: `/tmp/reload_backup/restore_services.sh` restarted every service; all health green; manager `gpu_info()` recovered.

## Isolated venv for 1.3.0rc29

`tensorrt_llm 1.3.0rc29` requirements (GitHub `v1.3.0rc29`) are incompatible with the shared venv (which has torch 2.9.1, numpy 1.26.4, transformers 4.57.3, flashinfer 0.6.4, triton 3.5.1):

```
torch>=2.14.0a0,<=2.14.0
transformers==5.5.4
flashinfer-python==0.6.18
triton==3.8.0
numpy>=2.0.0,<2.4
torchao>=0.14.1,<0.16.0
extra-index: cu132 (CUDA 13.2)
```

So a fresh venv was created at `offline-prep/venv-trtllm` (Python 3.12.3) with its own `pip.conf` (proxy + PyTorch `cu132` index). Wheels are staged under `offline-prep/wheels/`.

## Files added

- `scripts/serve_trtllm.sh` — launches `trtllm-serve` from `venv-trtllm` on the HF checkpoint (port 8010 default).
- `offline-prep/venv-trtllm/` — isolated env (gitignored under `offline-prep/`).
- `offline-prep/wheels/` — staged wheels (`torch-2.14.0+cu132`, `tensorrt_llm-1.2.1`, `nvidia_cublas-13.8.1.7`).
