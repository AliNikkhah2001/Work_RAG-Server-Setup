---
title: "Models (sorted by mean accuracy)"
nav_order: 1
---

| Model | Creator | Type | Params (active) | Size on disk | Context | Weights | Mean | Persian ARC (MC) | Parsinlu MC | Persian Math | Sentiment | Entailment | NER | Reading Comp. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [Gemma 4 31B IT](https://huggingface.co/google/gemma-4-31B) | Google DeepMind | Dense decoder-only (multimodal: text+image) | 31B | 19.6 GB | 256K | GGUF Q4_K_M | 0.663 | 0.960 | 0.700 | 0.640 | 0.820 | 0.160 | 1.000 | 0.360 |
| [Gemma 3 27B IT](https://huggingface.co/google/gemma-3-27b-it) | Google DeepMind | Dense decoder-only (multimodal: text+image) | 27B | 16.5 GB | 128K | GGUF Q4_K_M | 0.600 | 0.940 | 0.520 | 0.260 | 0.900 | 0.200 | 0.980 | 0.400 |
| [Nemotron Super 49B v1](https://huggingface.co/nvidia/Llama-3_3-Nemotron-Super-49B-v1) | NVIDIA | Dense decoder-only reasoning model (Llama-3.3-70B derivative, NAS) | 49B | 30.2 GB | 128K | GGUF Q4_K_M | 0.494 | 0.920 | 0.320 | 0.500 | 0.680 | 0.220 | 0.460 | 0.360 |
| [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | Alibaba (Qwen team) | Dense decoder-only VLM (text+image+video), thinking mode | 27B | 17.8 GB | 262K (→1M) | GGUF Q4_K_M | 0.477 | 0.920 | 0.620 | 0.180 | 0.760 | 0.260 | 0.020 | 0.580 |
| [Qwen2.5-7B Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | Alibaba (Qwen team) | Dense decoder-only Instruct | 7.6B | 4.4 GB | 32K | GGUF Q4_K_M | 0.443 | 0.680 | 0.360 | 0.380 | 0.660 | 0.000 | 0.880 | 0.140 |
| [Llama 3.2 3B Instruct](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) | Meta AI | Dense decoder-only Instruct | 3.2B | 1.9 GB | 128K | GGUF Q4_K_M | 0.326 | 0.560 | 0.300 | 0.140 | 0.580 | 0.240 | 0.000 | 0.460 |
| [Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B) | Alibaba (Qwen team) | Mixture-of-Experts decoder-only (3B active), thinking mode | 30B (3B act.) | 18.6 GB | 128K | GGUF Q4_K_M | 0.283 | 0.520 | 0.280 | 0.040 | 0.720 | 0.260 | 0.000 | 0.160 |
| [Mistral 7B Instruct v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3) | Mistral AI | Dense decoder-only Instruct | 7.3B | 4.4 GB | 32K | GGUF Q4_K_M | 0.186 | 0.360 | 0.240 | 0.060 | 0.300 | 0.180 | 0.020 | 0.140 |
| [Phi-3 Mini 4K Instruct](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) | Microsoft | Dense decoder-only Instruct | 3.8B | 2.4 GB | 4K | GGUF q4 | 0.143 | 0.340 | 0.100 | 0.000 | 0.220 | 0.160 | 0.000 | 0.180 |
