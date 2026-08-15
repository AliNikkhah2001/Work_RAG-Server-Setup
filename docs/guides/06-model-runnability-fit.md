# Guide 06 — Model Runnability & Hardware-Fit Matrix

> [Back to index](../README.md)

**Rule of thumb:** this box (281 GiB VRAM + 1 TB RAM) fits *every* model in the catalog. The real
gate is **engine software support**, not memory.

| Model (quant, size) | VRAM fit | RAM offload | Engine needed today | Runs now? |
|---|---|---|---|---|
| Qwen2.5-7B Q4 (4.7 G) | ✅ full | — | vLLM / llama.cpp | ✅ live |
| Qwen2.5-72B Q4 (47 G) | ✅ full | — | vLLM (GGUF via wrapper) | ✅ on download |
| Qwen3-30B-A3B Q4 (18.6 G) | ✅ full | — | llama.cpp `qwen3moe` (build ≥ B5xxx); vLLM new | ⚠️ after build check |
| Gemma-3-27B Q4 (16.5 G) | ✅ full | — | llama.cpp `gemma3` | ⚠️ after download + token |
| Nemotron Super-49B Q4 (30 G) | ✅ full | — | llama.cpp (Llama-3.3 arch) | ✅ on download |
| Nemotron Ultra-253B Q4 (151 G) | ✅ full | — | llama.cpp `-ngl 99` across 2×H200 (vLLM can't do GGUF splits) | ✅ on download |
| MiniMax-M3 UD-IQ4_XS (208 G) | ✅ full | — | **llama.cpp PR #24523** or vLLM ≥ 0.10 | 🚧 build fork |
| Kimi K3 UD-IQ1_S (594 G) | partial (~280 G) | ✅ ~310 G mmap, MoE-in-RAM | **unsloth llama.cpp fork** (`kimi-k3`) or new vLLM (KDA) | 🚧 build fork |
| GLM-5.2-FP8 (755 G) | partial | ✅ ~480 G | **vLLM ≥ 0.23** / SGLang ≥ 0.5.13 / KTransformers | ⛔ engine upgrade |
| DeepSeek-V4-Flash (160 G) | ✅ full | — | new vLLM + `deep_gemm` FP4 kernels | ⛔ engine upgrade |

## Choosing a quant by GPU budget

Given `281 GiB` of combined VRAM (2× H200 NVL, NVLink18):

- **≤ 250 G weights** → fully GPU-resident (keep `--ctx` modest) — best throughput.
- **250–500 G weights** → mixed: MoE experts in RAM via `--n-cpu-moe`, attention/embeddings on GPU.
- **> 500 G weights** → llama.cpp mmap + page-cache (Kimi K3 UD-IQ1_S 594 G validated pattern
  from 6block on 8×H100 + 2 TB RAM; this box matches on RAM, half the GPUs → expect single-digit tok/s).

## Known engine-state facts

- vLLM version 0.6.1 (`--enforce-eager`, `--gpu-memory-utilization 0.5` ≈ reserves 71 GiB on GPU-0
  for a 7B — **raise to 0.9** when serving larger models).
- llama.cpp (via `llama-cpp-python 0.3.34`) on GPU-1 uses ~4 GiB for the 7B.
- GPU 0 / GPU 1 both report 0% util at idle; the box is a single NUMA node — no cross-socket penalty.
- Kaggle-style caveat: torch 2.4.0+cu124 wheels vs driver CUDA 13.0 — PyTorch uses sparse kernels
  via CUDA 12.4 toolkit; fine in practice (all engines load).

## Bottom line

Nemotron pair + the 72B are the "safe today" frontier-scale wins; MiniMax-M3 and Kimi K3 become
runnable after building the two llama.cpp forks (Guide 06 → see `findings.md` for the PRs);
GLM-5.2 and DeepSeek-V4-Flash need a vLLM upgrade that's best staged as wheels through the proxy.