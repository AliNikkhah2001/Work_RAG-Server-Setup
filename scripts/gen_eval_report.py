#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a detailed Persian-eval report (Markdown + PNG plots) from
logs/evalp_*.json produced by scripts/eval_persian.py.

Usage:
  python scripts/gen_eval_report.py [--out docs/reports/persian_eval_report.md]
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent.parent
LOG_DIR = BASE / "logs"
REPORT_DIR = BASE / "docs" / "reports"

TASK_NAMES = ["fa_arc", "fa_mc", "fa_math", "fa_sentiment", "fa_entail", "fa_ner", "fa_rc"]
TASK_LABELS = {
    "fa_arc": "Persian ARC (MC)",
    "fa_mc": "Parsinlu MC",
    "fa_math": "Persian Math",
    "fa_sentiment": "Sentiment",
    "fa_entail": "Entailment",
    "fa_ner": "NER",
    "fa_rc": "Reading Comp.",
}


def load_results():
    data = {}
    for p in sorted(LOG_DIR.glob("evalp_*.json")):
        if "smoke" in p.name:
            continue
        with open(p) as f:
            d = json.load(f)
        model = Path(d["model"]).stem
        accs = {r["task"]: r["acc"] for r in d["results"]}
        samples = {r["task"]: r["samples"] for r in d["results"]}
        data[model] = {"mean": d["overall_mean"], "accs": accs, "samples": samples}
    return data


def build_report(data, out_path):
    models = sorted(data, key=lambda m: data[m]["mean"], reverse=True)
    lines = []
    lines.append("# Persian LLM Evaluation Report\n")
    lines.append(f"Generated: {__import__('datetime').datetime.now():%Y-%m-%d %H:%M UTC}\n")
    lines.append("## Models (sorted by mean accuracy)\n")
    lines.append("| Model | Mean | " + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
    lines.append("|---|" + "---|" * (len(TASK_NAMES) + 1))
    for m in models:
        row = f"| {m} | {data[m]['mean']:.3f} |"
        for t in TASK_NAMES:
            a = data[m]["accs"].get(t)
            row += f" {a:.3f} |" if a is not None else " — |"
        lines.append(row)

    lines.append("\n## Per-model samples\n")
    for m in models:
        lines.append(f"\n### {m} (mean {data[m]['mean']:.3f})\n")
        for t in TASK_NAMES:
            smps = data[m]["samples"].get(t)
            if not smps:
                continue
            lines.append(f"\n#### {TASK_LABELS.get(t, t)} — acc {data[m]['accs'].get(t)}\n")
            shown = 0
            for s in smps:
                if shown >= 2:
                    break
                shown += 1
                lines.append(f"- **Prompt**: {s['prompt'][:200]}")
                lines.append(f"  - **Gold**: {s['gold'][:120]}")
                lines.append(f"  - **Pred**: {s['pred'][:80]}")
                lines.append(f"  - **Output**: {s['output'][:200]}")
                lines.append(f"  - **Hit**: {'✅' if s['hit'] else '❌'}")
    return "\n".join(lines)


def make_plots(data, out_dir):
    models = sorted(data, key=lambda m: data[m]["mean"], reverse=True)
    n_models = len(models)
    fig, ax = plt.subplots(figsize=(10, 5))
    means = [data[m]["mean"] for m in models]
    bars = ax.bar(range(n_models), means, color="steelblue")
    ax.set_xticks(range(n_models))
    ax.set_xticklabels(models, rotation=20, ha="right")
    ax.set_ylabel("Mean accuracy")
    ax.set_title("Persian eval — mean accuracy by model")
    for b, v in zip(bars, means):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.3f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_mean.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(TASK_NAMES))
    width = 0.8 / max(n_models, 1)
    for i, m in enumerate(models):
        vals = [data[m]["accs"].get(t) or 0 for t in TASK_NAMES]
        ax.bar([xi + i * width for xi in x], vals, width, label=m)
    ax.set_xticks([xi + width * (n_models - 1) / 2 for xi in x])
    ax.set_xticklabels([TASK_LABELS[t] for t in TASK_NAMES], rotation=15, ha="right")
    ax.set_ylabel("Accuracy")
    ax.set_title("Persian eval — per-task accuracy by model")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_by_task.png", dpi=140)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPORT_DIR / "persian_eval_report.md"))
    args = ap.parse_args()
    data = load_results()
    if not data:
        print("no evalp_*.json results found")
        return
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_report(data, out_path))
    make_plots(data, out_path.parent)
    print(f"wrote {out_path}")
    print(f"plots in {out_path.parent}")
    for m, d in sorted(data.items(), key=lambda kv: kv[1]["mean"], reverse=True):
        print(f"  {d['mean']:.3f}  {m}")


if __name__ == "__main__":
    main()