#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find tricky per-task samples where models disagree, for the README section."""
import json
import glob
from collections import defaultdict

FILES = [f for f in glob.glob("logs/evalp_*.json")
         if "smoke" not in f]

def short_name(m):
    if "gemma-4" in m.lower() or "gemma_4" in m.lower() or "gemma-4-31b" in m.lower():
        return "Gemma-4-31B"
    if "gemma-3" in m.lower() or "gemma-3-27b" in m.lower():
        return "Gemma-3-27B"
    if "qwen3.8" in m.lower() or "qwen3_8" in m.lower():
        return "Qwen3.8-27B"
    if "qwen3-30b" in m.lower() or "qwen3_30b" in m.lower():
        return "Qwen3-30B-A3B"
    if "nemotron" in m.lower():
        return "Nemotron-49B"
    if "qwen2.5" in m.lower():
        return "Qwen2.5-7B"
    if "llama-3.2" in m.lower() or "llama3.2" in m.lower():
        return "Llama-3.2-3B"
    if "mistral" in m.lower():
        return "Mistral-7B"
    if "phi-3" in m.lower() or "phi3" in m.lower():
        return "Phi-3-mini"
    return m

# collect: task -> prompt -> {model: (output, hit, full)}
by_task = defaultdict(lambda: defaultdict(dict))
means = {}
for f in FILES:
    d = json.load(open(f))
    m = short_name(d["model"])
    tag = " (2-shot)" if "2shot" in f else ""
    means[m + tag] = d["overall_mean"]
    for r in d["results"]:
        task = r["task"]
        for s in r["samples"]:
            by_task[task][s["prompt"]][m + tag] = {
                "output": s.get("output") or s.get("pred"),
                "hit": s["hit"],
                "full": s,
            }

for task, prompts in by_task.items():
    print(f"##### {task} #####")
    best = None
    best_score = 99
    for prompt, models in prompts.items():
        if len(models) < 4:
            continue
        hits = sum(1 for v in models.values() if v["hit"])
        total = len(models)
        # tricky: disagreement not too one-sided
        frac = hits / total
        score = abs(frac - 0.5)
        if score < best_score:
            best_score = score
            best = (prompt, models)
    if best is None:
        print("  (no shared prompt with >=4 models)")
        continue
    prompt, models = best
    print("  PROMPT:", prompt.replace("\n", " | ")[:300])
    gold = models[next(iter(models))]["full"]["gold"]
    print("  GOLD:", gold)
    for name, v in sorted(models.items()):
        out = (v["output"] or "").replace("\n", " ")[:90]
        print(f"    {name:20s} hit={v['hit']}  {out}")
    print()