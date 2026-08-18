---
title: "Figures"
nav_order: 4
---

## persian_mean.png

![persian_mean.png]({{ '/assets/plots/persian_mean.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_mean.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_mean.png"></iframe>

Ranked mean accuracy across the 7 Persian tasks. **Each model has one color** used consistently: solid bar = vanilla prompts, hatched bar = improved prompting of the *same* model. Gemma-4-31B leads; small models collapse.

## persian_by_task.png

![persian_by_task.png]({{ '/assets/plots/persian_by_task.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_by_task.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_by_task.png"></iframe>

Per-task accuracy by model. Format-strict tasks (NER, entailment) spread models most; Gemma-4 is 1.0 on NER.

## persian_scatter.png

![persian_scatter.png]({{ '/assets/plots/persian_scatter.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_scatter.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_scatter.png"></iframe>

Model size on disk vs mean accuracy, bubble = parameter count. Size helps but is not sufficient (Qwen3-30B-A3B MoE trails dense models).

## persian_radar.png

![persian_radar.png]({{ '/assets/plots/persian_radar.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_radar.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_radar.png"></iframe>

Ability-group radar (Reasoning & Knowledge, Language Understanding, Information Extraction). Gemma models fill the largest polygon.

## persian_radar_family.png

![persian_radar_family.png]({{ '/assets/plots/persian_radar_family.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_radar_family.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_radar_family.png"></iframe>

Per-family radar profiles — Gemma vs Qwen vs Nemotron vs Llama vs Mistral vs Phi. Models in the same family share similar shades.

## persian_speed.png

![persian_speed.png]({{ '/assets/plots/persian_speed.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_speed.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_speed.png"></iframe>

Generation speed (tokens/sec) and latency per task. Phi-3-mini is fastest, Nemotron-49B slowest.

## persian_spider.png

![persian_spider.png]({{ '/assets/plots/persian_spider.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_spider.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_spider.png"></iframe>

Per-task 7-axis spider per model — a round spider is balanced; spikes show task-specific strength.

## persian_improvement.png

![persian_improvement.png]({{ '/assets/plots/persian_improvement.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_improvement.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_improvement.png"></iframe>

Vanilla vs improved prompting (4-component Persian templates): every model improves, most on format-strict tasks. Same color = same model; hatched bar = improved.

## persian_nshot.png

![persian_nshot.png]({{ '/assets/plots/persian_nshot.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_nshot.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_nshot.png"></iframe>

Few-shot scaling: mean accuracy at 0 / 1 / 2 / 3 / 5 in-context exemplars per task (Qwen2.5-7B).

## persian_temperature.png

![persian_temperature.png]({{ '/assets/plots/persian_temperature.png' | relative_url }})

<iframe src="{{ '/assets/plots/interactive/persian_temperature.html' | relative_url }}" width="100%" height="600" frameborder="0" title="Interactive persian_temperature.png"></iframe>

Effect of sampling temperature (0.0 → 1.0) on mean accuracy (Qwen2.5-7B).

