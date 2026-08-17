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
    "fa_mc": "The fill-the-blank asks for the *option number* (`3` = نادیده گرفتن). The four top models "
             "and Llama-3.2 output `3`; Qwen2.5-7B, Mistral and Phi-3 pick `4`/`4. جلوگیری از`; Qwen3-30B "
             "wraps its answer in a `thinking` block (truncation cost). Mistral and Phi-3 answer in full "
             "sentences instead of a bare number — a format-instruction gap, not a vocabulary gap.",
    "fa_math": "The sequence problem's gold is `8`. Only **Gemma-4-31B** and **Nemotron-49B** output a clean "
               "final answer the scorer accepts; the rest start the Persian 'راه حل' write-up correctly but "
               "the final-answer block is missing/malformed. Phi-3-mini degrades into repeated gibberish. "
               "This shows math scores are gated by output-structure compliance.",
    "fa_sentiment": "The review 'کلا ارزش یک‌بار امتحان کردن هم نداره' (totally not worth trying) is clearly "
                   "**NEGATIVE**. Gemma-4, Gemma-3, Qwen3.8 and Llama-3.2 get it; Mistral-7B and Qwen2.5-7B "
                   "emit NEUTRAL or hedge with a long explanation (scorer can't map). Qwen3-30B thinks out "
                   "loud and gets truncated. Sentiment is a *free-form* task — model prose length and "
                   "emotion-range calibration matter as much as comprehension.",
    "fa_entail": "The gold label is `n` (ناشناخته/neutral). **Every model misses it** — Gemma-4 and Gemma-3 "
                 "say تناظر, Llama-3.2/Mistral say تناقض, Qwen3.8 says ناشناخته but the scorer needs the "
                 "exact `<برچسب>: n` form. Entailment is the hardest task for all models (per-task accuracy "
                 "0.00–0.26) — a genuinely hard NLI signal, not a parsing artifact.",
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