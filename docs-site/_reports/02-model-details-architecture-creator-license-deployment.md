---
title: "Model details — architecture, creator, license, deployment"
nav_order: 2
---

All nine models were downloaded from the Hugging Face Hub as **GGUF** weight files, quantized with llama.cpp (Q4_K_M unless noted), and run **offline on the same 2× H200 NVL GPU box** via llama-cpp-python (GPU offload, `n_gpu_layers=-1`). Nothing ran on CPU. The 7-task Persian eval is single-pass, temperature 0.0, max_tokens 400 (needed so Qwen3-style thinking blocks are not truncated).

| Property | [Gemma 4 31B IT](https://huggingface.co/google/gemma-4-31B) | [Gemma 3 27B IT](https://huggingface.co/google/gemma-3-27b-it) | [Nemotron Super 49B v1](https://huggingface.co/nvidia/Llama-3_3-Nemotron-Super-49B-v1) | [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | [Qwen2.5-7B Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | [Llama 3.2 3B Instruct](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) | [Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B) | [Mistral 7B Instruct v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3) | [Phi-3 Mini 4K Instruct](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) |
|---|---|---|---|---|---|---|---|---|---|
| Creator | Google DeepMind | Google DeepMind | NVIDIA | Alibaba (Qwen team) | Alibaba (Qwen team) | Meta AI | Alibaba (Qwen team) | Mistral AI | Microsoft |
| License | Apache 2.0 | Gemma Terms of Use | NVIDIA Open Model + Llama 3.3 Community | Apache 2.0 | Apache 2.0 | Llama 3.2 Community License | Apache 2.0 | Apache 2.0 | MIT |
| Architecture | Dense decoder-only (multimodal: text+image) | Dense decoder-only (multimodal: text+image) | Dense decoder-only reasoning model (Llama-3.3-70B derivative, NAS) | Dense decoder-only VLM (text+image+video), thinking mode | Dense decoder-only Instruct | Dense decoder-only Instruct | Mixture-of-Experts decoder-only (3B active), thinking mode | Dense decoder-only Instruct | Dense decoder-only Instruct |
| Params / active | 31B / 31B | 27B / 27B | 49B / 49B | 27B / 27B | 7.6B / 7.6B | 3.2B / 3.2B | 30B / 3B | 7.3B / 7.3B | 3.8B / 3.8B |
| Context window | 256K | 128K | 128K | 262K (→1M) | 32K | 128K | 128K | 32K | 4K |
| Key arch notes | 60 layers, hybrid sliding-window+global attention, GQA, p-RoPE, 262K vocab | Gemma 3 transformer, GQA, sliding window (SWA), 256K vocab | Llama-3.3-70B-Instruct customized via Neural Architecture Search | 64 layers, GQA 24/4 heads, Gated-DeltaNet linear attention interleaved with full attention | 28 layers, GQA 28/4 heads, SwiGLU, RoPE | Llama 3.2 transformer, GQA | MoE (A3B = 3B active of 30B), GQA, thinking mode | 32 layers, GQA 8/8 heads, Sliding Window Attention, SwiGLU | 32 layers, GQA 32/4 heads, 4K context |
| Weights format | GGUF Q4_K_M | GGUF Q4_K_M | GGUF Q4_K_M | GGUF Q4_K_M | GGUF Q4_K_M | GGUF Q4_K_M | GGUF Q4_K_M | GGUF Q4_K_M | GGUF q4 |
| Disk size | 19.6 GB | 16.5 GB | 30.2 GB | 17.8 GB | 4.4 GB | 1.9 GB | 18.6 GB | 4.4 GB | 2.4 GB |
| Hardware | GPU | GPU | GPU | GPU | GPU | GPU | GPU | GPU | GPU |
