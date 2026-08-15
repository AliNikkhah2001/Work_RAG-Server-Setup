# Guide 05 — Models Catalog (downloaded / downloading / planned)

> [Back to index](../README.md)

Location: `offline-prep/models/huggingface/<repo with / → _>/`; partials under
`.cache/huggingface/download/*.incomplete`. Sizes below are measured on disk (GB, decimal).

## ✅ Downloaded & runnable now

| Model | File | Size | Status |
|---|---|---|---|
| Qwen2.5-7B-Instruct | `Qwen2.5-7B-Instruct-Q4_K_M.gguf` | 4.68 GB | ✅ serving on vLLM `:8000` + llama.cpp `:8080` |
| Llama-3.2-3B-Instruct | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 2.02 GB | ✅ ready |
| Phi-3-mini-4k-instruct | (multiple GGUF quants) | ~10 GB | ✅ ready |
| Mistral-7B-Instruct-v0.3 | `-Q3_K_S`, `-Q5_K_M` + `-Q4_K_M` | ~30 GB | ⏳ **Q4_K_M ~85%**, others complete |
| bge-small-en-v1.5 | safetensors | 383 MB | ✅ embeddings (`local-embed`, dim 384) |
| all-MiniLM-L6-v2 | safetensors | 932 MB | ✅ embeddings |

## 🔄 Downloading now (daemon `rag-dl`, in this order)

| Repo / file | Planned size | Current (approx) |
|---|---|---|
| `bartowski/Qwen2.5-72B-Instruct-GGUF` → `Q4_K_M` (single-file, vLLM+llama.cpp) | 47.4 GB | partial ~1.3 GB + Q8_0 resumed |
| → `Q8_0` (2 parts, llama.cpp only) | 77.3 GB | partials up to ~4.4 GB |
| `Qwen/Qwen3-30B-A3B-GGUF` → `Q4_K_M` | 18.6 GB | partial ~250 MB |
| `bartowski/google_gemma-3-27b-it-GGUF` → `Q4_K_M` | 16.5 GB | partial ~80 MB — ⚠️ **gated: needs HF_TOKEN**, auto-skips if absent |
| `bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF` → `Q4_K_M` | 30.2 GB | staged |
| `bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF` → `Q4_K_M` (split) | 151 GB | staged |
| `unsloth/MiniMax-M3-GGUF` → `UD-IQ4_XS` | 208 GB | queued |
| `deepseek-ai/DeepSeek-V4-Flash` (FP4+FP8 safetensors) | 160 GB | queued |
| `zai-org/GLM-5.2-FP8` (official FP8) | 755 GB | queued |
| `unsloth/Kimi-K3-GGUF` → `UD-IQ1_S` | 594 GB | queued |

**Total queued ≈ 2.0 TB** (disk free: 5.5 T — fits). The corporate proxy sustains only
≈230 KB/s, so the full queue is measured in **weeks**; resumption/appends happen every daemon
pass automatically.

## Model notes

- **Qwen2.5-72B** (47.4 G Q4): strong Persian/multilingual, works in both engines. Full quant set
  (Q8_0 ~93 G) targeted for llama.cpp.
- **Qwen3-30B-A3B** (30.5 B total / 3.3 B active MoE): best cost/quality for Persian; runs on
  llama.cpp `qwen3moe`.
- **Gemma-3-27B**: multimodal-capable chat GGUF; repo is **gated** — set an `HF_TOKEN` for it.
- **Nemotron Super/Ultra**: Llama-3.3/3.1 derivative reasoning/RAG models; Ultra-253B Q4 = 151 GB
  fits in the 281 GiB VRAM pool.
- **MiniMax-M3** (~428 B/23 B act), **Kimi K3** (2.8 T/104 B act), **GLM-5.2** (744 B/40 B act),
  **DeepSeek-V4-Flash** (284 B/13 B act): frontier MoEs — see fit matrix for engine requirements.

## Wrappers & quantization helpers

- GGUF wrapper dir `offline-prep/models/gguf-wrappers/qwen2.5-7b-q4km/` (config + `model.gguf`
  symlink) lets vLLM load the Qwen2.5 GGUF.
- Refer to [Guide 06](06-model-runnability-fit.md) for per-model VRAM/RAM + engine feasibility.