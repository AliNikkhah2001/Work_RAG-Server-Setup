#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vanilla vs improved prompt comparison, run live for full (untruncated) Q&A.

For each of the 7 Persian tasks, pick the *same tricky sample* the sample-questions
report highlights, then ask a strong model (Gemma-4-31B) and an error-prone model
(Mistral-7B) the question twice: once with the raw dataset prompt (vanilla), once
with the improved 4-component Persian template (ROLE/CONTEXT/CONSTRAINTS/OUTPUT
FORMAT). Full untruncated model answers are written to a markdown doc so the
effect of prompt engineering is directly readable.
"""
import argparse
import json
import glob
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_persian import improved_prompt, strip_think, score  # noqa: E402

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "reports"
ORDER = ["fa_arc", "fa_mc", "fa_math", "fa_sentiment", "fa_entail", "fa_ner", "fa_rc"]

TASK_LABEL = {
    "fa_arc": "ARC — elementary science (multiple choice)",
    "fa_mc": "Parsinlu multiple choice (analogy/grammar)",
    "fa_math": "Persian math word problem",
    "fa_sentiment": "Sentiment analysis",
    "fa_entail": "Natural language entailment",
    "fa_ner": "Named entity recognition (Persian tokens)",
    "fa_rc": "Reading comprehension",
}

MODELS = {
    "gemma4": ("Gemma-4-31B", "offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf"),
    "mistral": ("Mistral-7B", "offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"),
}


def load_all():
    samples = defaultdict(dict)
    for f in list(LOG_DIR.glob("evalp_*.json")) + list(LOG_DIR.glob("logs/evalp_*.json")):
        if "smoke" in f.name or "improved" in f.name or "2shot" in f.name:
            continue
        d = json.load(open(f))
        m = Path(d["model"]).stem
        for r in d["results"]:
            for i, s in enumerate(r["samples"]):
                samples[(r["task"], i)][m] = s
    return samples


def pick_tricky(task, samples):
    task_samples = [per for k, per in samples.items() if k[0] == task]
    best, best_score = None, 99
    for per in task_samples:
        if len(per) < 4:
            continue
        frac = sum(1 for v in per.values() if v["hit"]) / len(per)
        sc = abs(frac - 0.5)
        if sc < best_score:
            best_score, best = sc, per
    if best is None:
        return None
    for name, s in best.items():
        return s["prompt"], s["gold"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--out", default="docs/reports/persian_prompt_compare.md")
    args = ap.parse_args()

    from llama_cpp import Llama
    samples = load_all()

    lines = []
    lines.append("### 4e. Prompt engineering — vanilla vs improved, full Q&A\n")
    lines.append("For each task, the *same tricky question* is asked twice on a strong model "
                 "(Gemma-4-31B) and an error-prone model (Mistral-7B): first with the raw dataset "
                 "prompt (**vanilla**), then with an improved Persian prompt built from the "
                 "4-component framework — **ROLE** (شما …), **CONTEXT** (what the task is), "
                 "**CONSTRAINTS** (what not to write: no prose, no explanation, single answer), "
                 "**OUTPUT FORMAT** (the exact shape the scorer expects). Answers are shown in full "
                 "(untruncated). `✓/✗` = model hit the gold answer.\n")

    for task in ORDER:
        picked = pick_tricky(task, samples)
        if picked is None:
            continue
        prompt, gold = picked
        lines.append(f"\n#### {TASK_LABEL.get(task, task)}\n")
        lines.append(f"**Gold:** `{gold}`\n")
        lines.append("\n<details>\n<summary>Shared tricky input</summary>\n\n```\n"
                     + prompt + "\n```\n</details>\n")

        for key, (label, model_path) in MODELS.items():
            llm = Llama(model_path=model_path, n_ctx=8192, n_gpu_layers=-1, verbose=False)
            for style in ("vanilla", "improved"):
                msg = prompt if style == "vanilla" else improved_prompt(task, prompt)
                out = llm.create_chat_completion(
                    messages=[{"role": "user", "content": msg}],
                    max_tokens=args.max_tokens, temperature=0.0)
                text = strip_think((out["choices"][0]["message"]["content"] or "").strip())
                ex = {"kind": {"fa_arc": "mc", "fa_mc": "mc", "fa_math": "open",
                               "fa_sentiment": "label", "fa_entail": "label",
                               "fa_ner": "ner", "fa_rc": "open"}[task],
                      "gold": gold, "gold_norm": gold}
                hit, pred = score(task, ex, text)
                mark = "✅" if hit else "❌"
                lines.append(f"\n**{label} — {style.title()}** {mark}\n")
                lines.append(f"> Pred: `{pred}`\n")
                lines.append("```\n" + text.strip() + "\n```\n")
            llm.close()

    md = "\n".join(lines)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)
    print(f"wrote {out_path} ({len(md)} bytes)")


if __name__ == "__main__":
    main()
