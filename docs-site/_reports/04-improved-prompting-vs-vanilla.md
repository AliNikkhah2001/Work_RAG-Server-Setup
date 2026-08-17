---
title: "Improved prompting vs vanilla"
nav_order: 4
---

For every model we re-ran the full 7-task suite using **improved Persian prompts** (4-component framework: ROLE + CONTEXT + CONSTRAINTS + OUTPUT FORMAT, kept under ~80 tokens per task) instead of the raw dataset prompts. Deliberate output-format constraints in Persian were added because the scorers expect a strict shape (letter, option number, final-answer block, one label, tuple list, short span).

| Model | vanilla mean | improved mean | Δ |
|---|--:|--:|--:|
| google_gemma-4-31B-it-Q4_K_M | 0.663 | 0.820 | +0.157 |
| nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M | 0.494 | 0.694 | +0.200 |
| google_gemma-3-27b-it-Q4_K_M | 0.600 | 0.683 | +0.083 |
| Qwen2.5-7B-Instruct-Q4_K_M | 0.443 | 0.580 | +0.137 |
| Qwen3.8-27B-Q4_K_M | 0.477 | 0.540 | +0.063 |
| Mistral-7B-Instruct-v0.3-Q4_K_M | 0.186 | 0.409 | +0.223 |
| Qwen3-30B-A3B-Q4_K_M | 0.283 | 0.397 | +0.114 |
| Llama-3.2-3B-Instruct-Q4_K_M | 0.326 | 0.371 | +0.046 |
| Phi-3-mini-4k-instruct-q4 | 0.143 | 0.314 | +0.171 |

### Per-task deltas (improved − vanilla)

| Model | Persian ARC (MC) | Parsinlu MC | Persian Math | Sentiment | Entailment | NER | Reading Comp. |
|---|---|---|---|---|---|---|---|
| google_gemma-4-31B-it-Q4_K_M | +0.00 | +0.02 | -0.04 | +0.00 | +0.62 | +0.00 | +0.50 |
| nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M | +0.00 | +0.18 | +0.02 | +0.22 | -0.04 | +0.54 | +0.48 |
| google_gemma-3-27b-it-Q4_K_M | +0.00 | +0.00 | +0.16 | -0.08 | +0.14 | +0.02 | +0.34 |
| Qwen2.5-7B-Instruct-Q4_K_M | +0.02 | -0.06 | +0.00 | +0.18 | +0.08 | +0.12 | +0.62 |
| Qwen3.8-27B-Q4_K_M | +0.04 | +0.04 | -0.08 | +0.04 | +0.26 | +0.00 | +0.14 |
| Mistral-7B-Instruct-v0.3-Q4_K_M | +0.12 | -0.06 | +0.04 | +0.12 | +0.02 | +0.98 | +0.34 |
| Qwen3-30B-A3B-Q4_K_M | +0.20 | +0.06 | +0.00 | -0.06 | +0.16 | +0.00 | +0.44 |
| Llama-3.2-3B-Instruct-Q4_K_M | +0.06 | -0.06 | +0.02 | -0.56 | +0.00 | +0.62 | +0.24 |
| Phi-3-mini-4k-instruct-q4 | +0.02 | +0.04 | +0.00 | +0.24 | +0.02 | +0.80 | +0.08 |
