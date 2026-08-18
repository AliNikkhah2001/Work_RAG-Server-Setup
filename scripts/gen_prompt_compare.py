#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vanilla vs improved prompt comparison, run live for full (untruncated) Q&A,
rendered as RTL-friendly markdown with the two prompts shown side by side.

For each of the 7 Persian tasks, pick the *same tricky sample* (the row where
the models disagree most), then ask a strong model (Gemma-4-31B) and an
error-prone model (Mistral-7B) the question twice: once with the raw dataset
prompt (vanilla), once with the improved 4-component Persian template
(ROLE/CONTEXT/CONSTRAINTS/OUTPUT FORMAT). Full untruncated answers are written
to a markdown doc so the effect of prompt engineering is directly readable.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from llama_cpp import Llama

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
    for f in LOG_DIR.glob("evalp_*.json"):
        if "smoke" in f.name or "improved" in f.name or "shot" in f.name or "temp" in f.name:
            continue
        d = json.load(open(f))
        m = Path(d["model"]).stem
        for r in d["results"]:
            for i, s in enumerate(r["samples"]):
                samples[(r["task"], i)][m] = s
    return samples


def pick_tricky(task, samples):
    """Return (task, index) of the tricky sample for a task — the row where the
    models disagree most (fraction of correct answers closest to 0.5)."""
    best, best_score = None, 99
    for k, per in samples.items():
        if k[0] != task or len(per) < 4:
            continue
        frac = sum(1 for v in per.values() if v["hit"]) / len(per)
        sc = abs(frac - 0.5)
        if sc < best_score:
            best_score, best = sc, k
    return best


def full_rows(task):
    """Load the full (untruncated) dataset rows for a task, via the eval loader."""
    from eval_persian import build_loader, LOADERS
    get = build_loader()
    rows = LOADERS[task](get, None)
    for ex in rows:
        ex["_task"] = task
    return rows


def htmlesc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def md_quote(s):
    """Collapse long lines into a <pre> block that preserves RTL ordering."""
    s = htmlesc(s.strip())
    return f"<pre dir=\"rtl\" lang=\"fa\">{s}</pre>"


def rtl_cell(s, maxlen=400):
    s = htmlesc(str(s).strip())
    if len(s) > maxlen:
        s = s[:maxlen] + " …"
    return f"<div dir=\"rtl\" lang=\"fa\">{s}</div>"


def answer_block(text):
    text = htmlesc(text.strip())
    return f"<pre dir=\"rtl\" lang=\"fa\" style=\"background:#f6f6f6;padding:8px;\">{text}</pre>"


def build(lines, args, samples):
    intro = [
        "### 4e. Prompt engineering — vanilla vs improved, full Q&A",
        "",
        "For each task, the *same tricky question* is asked twice on a strong model "
        "(Gemma-4-31B) and an error-prone model (Mistral-7B): first with the raw dataset "
        "prompt (**vanilla**), then with an improved Persian prompt built from the "
        "4-component framework. Answers are shown in full (untruncated) with RTL layout. "
        "`✅/❌` = model hit the gold answer.",
        "",
    ]
    lines.extend(intro)

    # ---- explain the prompt-engineering format ----
    lines.append("#### The prompt-engineering format (4-component framework)")
    lines.append("")
    lines.append("Every improved prompt wraps the **same question** with a short Persian "
                 "instruction built from four components. Together they pin down *who the "
                 "model is*, *what the task is*, *what it must not do*, and *the exact output "
                 "shape* the scorer accepts:")
    lines.append("")
    lines.append("| Component | Purpose | Persian example |")
    lines.append("|---|---|---|")
    lines.append("| **ROLE** | who the model is (task identity) | `شما یک متخصص ریاضی هستید` (you are a math expert) |")
    lines.append("| **CONTEXT** | what the task is / what is given | `مسئله را قدم‌به‌قدم حل می‌کنید` (you solve step-by-step) |")
    lines.append("| **CONSTRAINTS** | what NOT to do (no prose, no explanation, one answer) | `بعد از پاسخ نهایی هیچ عدد دیگری ننویسید` (nothing after the final answer) |")
    lines.append("| **OUTPUT FORMAT** | the exact shape the scorer expects | `[پاسخ نهایی] عدد` (final-answer block) |")
    lines.append("")
    lines.append("The 7 templates (one per task, 35–52 Persian words each) are defined in "
                 "`IMPROVED_TEMPLATES` in `scripts/eval_persian.py`. The same question is "
                 "then fed to the model either **bare** (vanilla) or **prefixed with the "
                 "template** (improved):")
    lines.append("")
    lines.append("```text")
    lines.append("improved_prompt(task, question) = IMPROVED_TEMPLATES[task] + \"\\n\" + question")
    lines.append("```")
    lines.append("")
    for task in ORDER:
        picked = pick_tricky(task, samples)
        if picked is None:
            continue
        t, idx = picked
        rows = full_rows(t)
        if idx >= len(rows):
            continue
        ex = rows[idx]
        prompt = ex["prompt"]
        gold = ex.get("gold") or ex.get("raw_gold")
        improved = improved_prompt(task, prompt)
        lines.append(f"\n#### {TASK_LABEL.get(task, task)}\n")
        lines.append(f"**Gold:** {rtl_cell(gold)}\n")
        lines.append("")
        lines.append("<table><thead><tr><th style=\"width:50%\">Vanilla prompt</th>"
                     "<th style=\"width:50%\">Improved prompt (ROLE/CONTEXT/CONSTRAINTS/OUTPUT FORMAT)</th></tr></thead><tbody>")
        lines.append("<tr><td style=\"vertical-align:top\">")
        lines.append(md_quote(prompt))
        lines.append("</td><td style=\"vertical-align:top\">")
        lines.append(md_quote(improved))
        lines.append("</td></tr></tbody></table>")
        lines.append("")

        for key, (label, model_path) in MODELS.items():
            llm = Llama(model_path=model_path, n_ctx=8192, n_gpu_layers=-1, verbose=False)
            for style in ("vanilla", "improved"):
                msg = prompt if style == "vanilla" else improved
                out = llm.create_chat_completion(
                    messages=[{"role": "user", "content": msg}],
                    max_tokens=args.max_tokens, temperature=0.0)
                text = strip_think((out["choices"][0]["message"]["content"] or "").strip())
                exx = {"kind": {"fa_arc": "mc", "fa_mc": "mc", "fa_math": "open",
                                "fa_sentiment": "label", "fa_entail": "label",
                                "fa_ner": "ner", "fa_rc": "open"}[task],
                       "gold": gold, "gold_norm": str(gold)}
                hit, pred = score(task, exx, text)
                mark = "✅" if hit else "❌"
                lines.append(f"**{label} — {style.title()}** {mark}\n")
                lines.append(f"> Pred: `{pred}`\n")
                lines.append(answer_block(text))
                lines.append("")
            llm.close()
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--out", default="docs/reports/persian_prompt_compare.md")
    args = ap.parse_args()

    samples = load_all()

    lines = []
    md = build(lines, args, samples)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)
    print(f"wrote {out_path} ({len(md)} bytes)")


if __name__ == "__main__":
    main()