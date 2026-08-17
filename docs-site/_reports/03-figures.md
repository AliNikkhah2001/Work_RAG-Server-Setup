---
title: "Figures"
nav_order: 3
---

## persian_mean.png

![persian_mean.png]({{ '/assets/plots/persian_mean.png' | relative_url }})

Ranked mean accuracy across the 7 Persian tasks (vanilla prompts). Gemma-4-31B leads, small models collapse.

## persian_by_task.png

![persian_by_task.png]({{ '/assets/plots/persian_by_task.png' | relative_url }})

Per-task accuracy by model. Format-strict tasks (NER, entailment) spread models most; Gemma-4 is 1.0 on NER.

## persian_scatter.png

![persian_scatter.png]({{ '/assets/plots/persian_scatter.png' | relative_url }})

Model size on disk vs mean accuracy, bubble = parameter count. Size helps but is not sufficient (Qwen3-30B-A3B MoE trails dense models).

## persian_radar.png

![persian_radar.png]({{ '/assets/plots/persian_radar.png' | relative_url }})

Ability-group radar (Reasoning & Knowledge, Language Understanding, Information Extraction). Gemma models fill the largest polygon.

## persian_radar_family.png

![persian_radar_family.png]({{ '/assets/plots/persian_radar_family.png' | relative_url }})

Per-family radar profiles — Gemma vs Qwen vs Nemotron vs Llama vs Mistral vs Phi.

## persian_speed.png

![persian_speed.png]({{ '/assets/plots/persian_speed.png' | relative_url }})

Generation speed (tokens/sec) and latency per task. Phi-3-mini is fastest, Nemotron-49B slowest.

## persian_spider.png

![persian_spider.png]({{ '/assets/plots/persian_spider.png' | relative_url }})

Per-task 7-axis spider per model — a round spider is balanced; spikes show task-specific strength.

## persian_improvement.png

![persian_improvement.png]({{ '/assets/plots/persian_improvement.png' | relative_url }})

Vanilla vs improved prompting (4-component Persian templates): every model improves, most on format-strict tasks.

