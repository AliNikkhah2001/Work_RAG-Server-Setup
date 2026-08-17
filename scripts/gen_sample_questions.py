#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate README §4d 'sample questions' section: one tricky prompt per task,
full model outputs (0-shot + n-shot where available) and per-model scores."""
import json
import glob
from collections import defaultdict

FILES = [f for f in glob.glob("logs/evalp_*.json")
         if "smoke" not in f]


def short_name(m):
    if "gemma-4" in m.lower():
        return "Gemma-4-31B"
    if "gemma-3" in m.lower():
        return "Gemma-3-27B"
    if "qwen3.8" in m.lower():
        return "Qwen3.8-27B"
    if "qwen3-30b" in m.lower():
        return "Qwen3-30B-A3B"
    if "nemotron" in m.lower():
        return "Nemotron-49B"
    if "qwen2.5" in m.lower():
        return "Qwen2.5-7B"
    if "llama-3.2" in m.lower():
        return "Llama-3.2-3B"
    if "mistral" in m.lower():
        return "Mistral-7B"
    if "phi" in m.lower():
        return "Phi-3-mini"
    return m


TASK_LABEL = {
    "fa_arc": "ARC — elementary science (multiple choice)",
    "fa_mc": "Parsinlu multiple choice (analogy/grammar)",
    "fa_math": "Persian math word problem",
    "fa_sentiment": "Sentiment analysis",
    "fa_entail": "Natural language entailment",
    "fa_ner": "Named entity recognition (Persian tokens)",
    "fa_rc": "Reading comprehension",
}

TASK_NOTE = {
    "fa_arc": "All 9 models saw the same lab-safety question; the correct answer is **A**. "
              "Gemma-4, Gemma-3, Qwen3.8 and Llama-3.2 comply with the 'answer one letter' instruction, "
              "but Nemotron-49B, Qwen2.5-7B, Qwen3-30B and Phi-3-mini choose an *arguably reasonable* "
              "but wrong option — showing that ARC scores separate models on Persian science reasoning, "
              "not just on format-following.",
    "fa_mc": "A workers/rate word problem: 8 workers finish in 20 days; adding 2 workers finishes it how many "
             "days *earlier*? (gold `2` = ۴ روز). Gemma-4, Gemma-3, Qwen3.8, Qwen2.5-7B (2-shot) and Llama-3.2 "
             "answer the option number correctly; Nemotron and Qwen2.5-7B (0-shot) pick wrong options (`4`/`3`), "
             "Mistral answers `1. 16 روز`, Phi-3-mini prints *every* option, and Qwen3-30B wraps its answer in "
             "a `thinking` block (truncated). Format-following (bare option number) decides the winner.",
    "fa_math": "'5% of 2000 is equal to 10% of what number?' (gold `1000`). Five models — Gemma-4, Gemma-3, "
              "Nemotron, Qwen3.8 and Qwen2.5-7B (0-shot) — work it correctly; Qwen2.5-7B **2-shot misses** "
              "(the exemplar anchors a different structure), Llama-3.2 and Mistral set up the equation but "
              "never output the final-answer block, and Phi-3-mini degrades into gibberish. Math scores are "
              "gated by final-answer *structure compliance*, and few-shot can actually hurt.",
    "fa_sentiment": "A product review — 'نوشیدنی مالته باید تلخ باشه نه شیرین… کاملا پشیمونم' — is clearly "
                   "**NEGATIVE**. Gemma-4, Gemma-3, Qwen3.8, Llama-3.2 and Qwen2.5-7B (2-shot) get it; "
                   "Mistral-7B says `NEUTRAL`, Qwen2.5-7B and Nemotron hedge with long explanations the scorer "
                   "can't map, and Qwen3-30B emits the right label *after* a `thinking` block (truncation cost). "
                   "A free-form task where prose length and label discipline matter as much as comprehension.",
    "fa_entail": "The gold label is `<برچسب>: c` (تناقض/contradiction) — acid-rain premise vs hypothesis. "
                 "**Half the models miss even this** (the task's best model only scores 0.26). Gemma-3, "
                 "Nemotron, Llama-3.2 and Phi-3 pick تناقض (Qwen3-30B also hits, label hidden inside a "
                 "`thinking` block); Gemma-4 and Qwen2.5 say ناشناخته, Mistral/Qwen2.5 say تناظر, Qwen3.8 "
                 "answers in an English preamble. The *right-class* accuracy would be much higher — most "
                 "failures are output-format, but the underlying NLI signal is genuinely the hardest of the "
                 "seven tasks.",
    "fa_ner": "The input list has facility/location tokens (بزرگراه نیاوران …). Gemma-4/Gemma-3 and "
              "Qwen2.5-7B emit the expected `[('tok','LABEL'), …]` tuples (hit); Qwen3-30B and Qwen3.8 get "
              "stuck in `thinking`/English preamble; Llama-3.2, Mistral, Phi-3 reply with instructions "
              "*instead of* the labeled list. **Qwen2.5-7B 2-shot jumps from prose to clean tuples** — "
              "few-shot examples fix NER format-following better than a bigger model.",
    "fa_rc": "The passage says a triangle cannot have a diagonal → answer **مثلث**. Top models, Llama-3.2 "
             "and Qwen3.8 answer in one word; Mistral, Phi-3, Qwen3-30B and Qwen2.5-7B either paraphrase, "
             "reproduce the passage, or add an explanation that fails the exact-match scorer. RC rewards "
             "*extractive brevity* — models that restate the answer as-is win.",
}


def clip(s, n=110):
    s = (s or "").replace("\n", " ")
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def load_all():
    # key: (task, index) -> {model_tag: sample}; plus overall means
    samples = defaultdict(dict)
    means = {}
    for f in FILES:
        d = json.load(open(f))
        m = short_name(d["model"])
        tag = " (2-shot)" if "2shot" in f else ""
        means[m + tag] = d["overall_mean"]
        for r in d["results"]:
            for i, s in enumerate(r["samples"]):
                samples[(r["task"], i)][m + tag] = s
    return samples, means


samples, means = load_all()
ORDER = ["fa_arc", "fa_mc", "fa_math", "fa_sentiment", "fa_entail", "fa_ner", "fa_rc"]

out = []
out.append("### 4c. Sample questions — one tricky prompt per category, all models\n")
out.append("For each of the 7 task categories below, a deliberately *tricky* prompt is shown where the "
           "9 models **disagree** (best view of real capability). Every model received the exact same input "
           "(same dataset row, same index); outputs are raw, including `thinking` blocks where models emit "
           "them. Qwen2.5-7B appears twice: **0-shot** and **2-shot** (`--n-shots 2`). Scores are the model's "
           "overall Persian-eval mean (0–1); `✓/✗` is whether it got this specific question right.\n")

for task in ORDER:
    task_samples = [s for k, s in samples.items() if k[0] == task]
    best = None
    best_score = 99
    for per_model in task_samples:
        if len(per_model) < 4:
            continue
        frac = sum(1 for v in per_model.values() if v["hit"]) / len(per_model)
        sc = abs(frac - 0.5)
        if sc < best_score:
            best_score = sc
            best = per_model
    if best is None:
        continue
    # reference sample (non-2shot) gives the shared prompt/gold
    ref = None
    for name, s in best.items():
        if "(2-shot)" not in name:
            ref = s
            break
    prompt, gold = ref["prompt"], ref["gold"]

    out.append(f"#### {TASK_LABEL.get(task, task)}\n")
    out.append("**Input:**\n\n```\n" + prompt + "\n```\n")
    out.append(f"**Gold:** `{gold}`\n")
    out.append("")
    out.append("| Model | Overall mean | This question | Output (abridged) |")
    out.append("|---|---|---|---|")
    for name in sorted(best, key=lambda n: means[n], reverse=True):
        v = best[name]
        mark = "✅" if v["hit"] else "❌"
        oc = clip(v.get("output") or v.get("pred"), 110).replace("|", "\\|")
        out.append(f"| **{name}** | {means[name]:.3f} | {mark} | `{oc}` |")
    out.append("")
    out.append("**Why it's tricky:** " + TASK_NOTE.get(task, "") + "\n")

md = "\n".join(out)
with open("docs/reports/persian_sample_questions.md", "w") as fh:
    fh.write(md)
print(md)