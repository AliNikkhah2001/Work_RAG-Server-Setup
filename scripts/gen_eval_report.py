#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a comprehensive Persian-eval report (Markdown + creative PNG plots)
from logs/evalp_*.json produced by scripts/eval_persian.py.

Plots produced:
  - persian_mean.png        : ranked bar of mean accuracy
  - persian_by_task.png     : grouped per-task bars
  - persian_scatter.png     : model size (GB on disk) vs mean accuracy (bubble = params)
  - persian_radar.png       : radar chart grouped by ability categories
  - persian_radar_family.png: one radar per model family (grouped)
  - persian_speed.png       : tokens/sec and avg secs/task per model
  - persian_spider.png      : per-task spider (7 axes) per model

Usage:
  python scripts/gen_eval_report.py [--out docs/reports/persian_eval_report.md]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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

# Ability groupings for radar charts
ABILITY_GROUPS = {
    "Reasoning & Knowledge": ["fa_arc", "fa_mc", "fa_math"],
    "Language Understanding": ["fa_sentiment", "fa_entail"],
    "Information Extraction": ["fa_ner", "fa_rc"],
}

# Model metadata: stem of the GGUF file -> (params B, disk GB of the used quant, family, color)
MODEL_META = {
    "google_gemma-4-31B-it-Q4_K_M": (31, 19.6, "Gemma-4", "#d62728"),
    "google_gemma-3-27b-it-Q4_K_M": (27, 16.5, "Gemma-3", "#ff9896"),
    "Qwen3.8-27B-Q4_K_M": (27, 17.8, "Qwen3.8", "#1f77b4"),
    "Qwen3-30B-A3B-Q4_K_M": (30, 18.6, "Qwen3-MoE", "#aec7e8"),
    "nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M": (49, 30.2, "Nemotron", "#2ca02c"),
    "Qwen2.5-7B-Instruct-Q4_K_M": (7, 4.4, "Qwen2.5", "#ff7f0e"),
    "Llama-3.2-3B-Instruct-Q4_K_M": (3.2, 1.9, "Llama-3.2", "#8c564b"),
    "Mistral-7B-Instruct-v0.3-Q4_K_M": (7, 4.4, "Mistral", "#17becf"),
    "Phi-3-mini-4k-instruct-q4": (3.8, 2.4, "Phi-3", "#9467bd"),
}

FAMILY_COLOR = {
    "Gemma-4": "#d62728", "Gemma-3": "#ff9896", "Qwen3.8": "#1f77b4",
    "Qwen3-MoE": "#aec7e8", "Nemotron": "#2ca02c", "Qwen2.5": "#ff7f0e",
    "Llama-3.2": "#8c564b", "Mistral": "#17becf", "Phi-3": "#9467bd",
}


def load_results():
    data = {}
    for p in sorted(LOG_DIR.glob("evalp_*.json")) + sorted(LOG_DIR.glob("logs/evalp_*.json")):
        if "smoke" in p.name:
            continue
        with open(p) as f:
            d = json.load(f)
        model = Path(d["model"]).stem
        if "2shot" in p.name or "nshot" in p.name:
            model = f"{model} (2-shot)"
        elif "0shot" in p.name:
            model = f"{model} (0-shot)"
        if "improved" in p.name:
            model = f"{model} (improved)"
        accs = {r["task"]: r["acc"] for r in d["results"]}
        samples = {r["task"]: r["samples"] for r in d["results"]}
        secs = {r["task"]: r.get("secs") for r in d["results"]}
        tok_sec = {r["task"]: r.get("tok_sec") for r in d["results"]}
        data[model] = {"mean": d["overall_mean"], "accs": accs, "samples": samples,
                       "secs": secs, "tok_sec": tok_sec}
    return data


def meta_of(model_stem):
    return MODEL_META.get(model_stem, (None, None, "Unknown", "#999999"))


def bench_key(model_stem):
    k = model_stem.replace(" (2-shot)", "").replace(" (improved)", "").lower()
    for short, full in [("gemma-4", "gemma-4-31b"), ("gemma-3", "gemma-3-27b"),
                        ("nemotron", "nemotron-49b"), ("qwen3.8", "qwen3.8-27b"),
                        ("qwen2.5", "qwen2.5-7b"), ("llama-3.2", "llama3.2-3b"),
                        ("qwen3-30b", "qwen3-30b"), ("mistral", "mistral-7b"),
                        ("phi-3", "phi3-mini")]:
        if short in k:
            return full
    return None


def load_speed_bench():
    bench = {}
    p = Path("logs/speed_bench.json")
    if p.exists():
        try:
            raw = json.loads(p.read_text())
            for name, v in raw.items():
                if isinstance(v, dict) and v.get("tok_sec"):
                    bench[name] = v["tok_sec"]
        except Exception:
            pass
    return bench


def group_accuracy(accs):
    out = {}
    for cat, tasks in ABILITY_GROUPS.items():
        vals = [accs.get(t) for t in tasks if accs.get(t) is not None]
        out[cat] = float(np.mean(vals)) if vals else 0.0
    return out


def build_report(data, out_path):
    models = sorted(data, key=lambda m: data[m]["mean"], reverse=True)
    lines = []
    lines.append("# Persian LLM Evaluation Report\n")
    lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M UTC}\n")
    lines.append("## Models (sorted by mean accuracy)\n")
    lines.append("| Model | Family | Params | Size | Mean | "
                 + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
    lines.append("|---|" + "---|" * (len(TASK_NAMES) + 4))
    for m in models:
        params, size, fam, _ = meta_of(m)
        pf = f"{params}B" if params else "?"
        sf = f"{size}G" if size else "?"
        row = f"| {m} | {fam} | {pf} | {sf} | {data[m]['mean']:.3f} |"
        for t in TASK_NAMES:
            a = data[m]["accs"].get(t)
            row += f" {a:.3f} |" if a is not None else " — |"
        lines.append(row)

    lines.append("\n## Ability-group scores (radar chart data)\n")
    lines.append("| Model | " + " | ".join(ABILITY_GROUPS) + " |")
    lines.append("|---|" + "---|" * len(ABILITY_GROUPS))
    for m in models:
        ga = group_accuracy(data[m]["accs"])
        lines.append(f"| {m} | " + " | ".join(f"{ga[c]:.3f}" for c in ga) + " |")

    lines.append("\n## Figures\n")
    lines.append("- **persian_mean.png** — ranked mean accuracy.\n")
    lines.append("- **persian_by_task.png** — accuracy per task across models.\n")
    lines.append("- **persian_scatter.png** — model size (disk GB) vs mean accuracy; "
                 "bubble size = parameter count.\n")
    lines.append("- **persian_radar.png** — ability-group profile per model (all on one axis).\n")
    lines.append("- **persian_radar_family.png** — per-family radar profiles.\n")
    lines.append("- **persian_speed.png** — tokens/sec and latency per task.\n")
    lines.append("- **persian_spider.png** — per-task (7-axis) spider per model.\n")

    lines.append("\n## Improved prompting vs vanilla\n")
    lines.append("For every model we re-ran the full 7-task suite using **improved Persian "
                 "prompts** (4-component framework: ROLE + CONTEXT + CONSTRAINTS + OUTPUT "
                 "FORMAT, kept under ~80 tokens per task) instead of the raw dataset prompts. "
                 "Deliberate output-format constraints in Persian were added because the "
                 "scorers expect a strict shape (letter, option number, final-answer block, "
                 "one label, tuple list, short span).\n")
    improved = sorted((m for m in data if "(improved)" in m),
                      key=lambda m: data[m]["mean"], reverse=True)
    if improved:
        base = {m.replace(" (improved)", ""): data[m] for m in improved}
        lines.append("| Model | vanilla mean | improved mean | Δ |")
        lines.append("|---|--:|--:|--:|")
        for m in improved:
            v = data.get(m.replace(" (improved)", ""))
            if not v:
                continue
            imp = data[m]["mean"]
            lines.append(f"| {m.replace(' (improved)', '')} | {v['mean']:.3f} | {imp:.3f} | "
                         f"{imp - v['mean']:+.3f} |")
        lines.append("\n### Per-task deltas (improved − vanilla)\n")
        lines.append("| Model | " + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
        lines.append("|---|" + "---|" * len(TASK_NAMES))
        for m in improved:
            v = data.get(m.replace(" (improved)", ""))
            if not v:
                continue
            row = [m.replace(" (improved)", "")]
            for t in TASK_NAMES:
                vi = data[m]["accs"].get(t)
                vv = v["accs"].get(t)
                row.append(f"{vi - vv:+.2f}" if vi is not None and vv is not None else "—")
            lines.append("| " + " | ".join(row) + " |")

    lines.append("\n## Same question, all models (first example per task)\n")
    lines.append("The same test prompt was sent to every model. Gold answers and per-model outputs "
                 "show *why* scores differ (format-following, Persian fluency, reasoning quality).\n")
    for t in TASK_NAMES:
        lines.append(f"\n### {TASK_LABELS.get(t, t)}\n")
        gold = None
        outs = []
        for m in models:
            smps = data[m]["samples"].get(t)
            if not smps:
                continue
            s = smps[0]
            if gold is None:
                gold = s["gold"]
                lines.append(f"- **Prompt**: {s['prompt'][:250]}\n- **Gold**: {gold}\n")
            outs.append((m, s))
        for m, s in outs:
            lines.append(f"- **{m}** (hit {'✅' if s['hit'] else '❌'}): `{s['output'][:160]}`")
        if not outs:
            lines.append("- *(no samples)*")

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
    means = [data[m]["mean"] for m in models]

    # ---- 1. ranked mean bar ----
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(range(n_models), means, color=[meta_of(m)[3] for m in models])
    ax.set_xticks(range(n_models))
    ax.set_xticklabels([m.split("-")[0] for m in models], rotation=20, ha="right")
    ax.set_ylabel("Mean accuracy")
    ax.set_title("Persian eval — mean accuracy by model")
    for b, v in zip(bars, means):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.3f}", ha="center", fontsize=8)
    ax.set_ylim(0, max(means) * 1.15)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_mean.png", dpi=140)
    plt.close(fig)

    # ---- 2. grouped per-task bars ----
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(TASK_NAMES))
    width = 0.8 / max(n_models, 1)
    for i, m in enumerate(models):
        vals = [data[m]["accs"].get(t) or 0 for t in TASK_NAMES]
        ax.bar(x + i * width, vals, width, label=m, color=meta_of(m)[3])
    ax.set_xticks(x + width * (n_models - 1) / 2)
    ax.set_xticklabels([TASK_LABELS[t] for t in TASK_NAMES], rotation=15, ha="right")
    ax.set_ylabel("Accuracy")
    ax.set_title("Persian eval — per-task accuracy by model")
    ax.legend(fontsize=7, ncol=2)
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_by_task.png", dpi=140)
    plt.close(fig)

    # ---- 3. scatter: disk size vs mean, bubble = params ----
    fig, ax = plt.subplots(figsize=(10, 6))
    for m in models:
        params, size, fam, color = meta_of(m)
        if not size:
            continue
        ax.scatter(size, data[m]["mean"], s=(params or 3) * 60, alpha=0.7,
                   color=color, edgecolors="black", label=fam)
        ax.annotate(f"{m.split('-')[0]} ({params}B)", (size, data[m]["mean"]),
                    textcoords="offset points", xytext=(6, 6), fontsize=7)
    ax.set_xlabel("Model size on disk (GB, Q4_K_M)")
    ax.set_ylabel("Mean Persian accuracy")
    ax.set_title("Accuracy vs model size (bubble area = parameter count)")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_scatter.png", dpi=140)
    plt.close(fig)

    # ---- 4. radar chart: ability groups (all models) ----
    cats = list(ABILITY_GROUPS.keys())
    n_cats = len(cats)
    angles = np.linspace(0, 2 * np.pi, n_cats, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    for m in models:
        ga = group_accuracy(data[m]["accs"])
        vals = [ga[c] for c in cats] + [ga[cats[0]]]
        _, _, fam, color = meta_of(m)
        ax.plot(angles, vals, label=m, color=color, linewidth=1.2)
        ax.fill(angles, vals, color=color, alpha=0.08)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cats, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_title("Ability-group radar (all models)", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_radar.png", dpi=140)
    plt.close(fig)

    # ---- 5. radar per family (subplots) ----
    families = {}
    for m in models:
        _, _, fam, _ = meta_of(m)
        families.setdefault(fam, []).append(m)
    fams = sorted(families)
    cols = 3
    rows = int(np.ceil(len(fams) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows),
                             subplot_kw=dict(polar=True))
    axes = np.atleast_1d(axes).ravel()
    for i, fam in enumerate(fams):
        ax = axes[i]
        for m in families[fam]:
            ga = group_accuracy(data[m]["accs"])
            vals = [ga[c] for c in cats] + [ga[cats[0]]]
            ax.plot(angles, vals, label=m, color=meta_of(m)[3], linewidth=1.5)
            ax.fill(angles, vals, color=meta_of(m)[3], alpha=0.15)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([c.split()[0] for c in cats], fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_title(fam, pad=18, fontsize=11)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.05), fontsize=6)
    for j in range(len(fams), len(axes)):
        axes[j].axis("off")
    fig.suptitle("Ability-group radar by model family", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_radar_family.png", dpi=140)
    plt.close(fig)

    # ---- 6. speed: tokens/sec + seconds/task ----
    bench = load_speed_bench()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    toks = []
    secs_per = []
    for m in models:
        tv = [v for v in data[m]["tok_sec"].values() if v]
        sv = [v for v in data[m]["secs"].values() if v]
        ts = float(np.mean(tv)) if tv else 0
        if not ts:
            ts = bench.get(bench_key(m)) or 0
        toks.append(ts)
        secs_per.append(float(np.mean(sv)) if sv else 0)
    x = np.arange(n_models)
    ax1.bar(x, toks, color=[meta_of(m)[3] for m in models])
    ax1.set_xticks(x)
    ax1.set_xticklabels([m.split("-")[0] for m in models], rotation=30, ha="right", fontsize=7)
    ax1.set_ylabel("tokens/sec")
    ax1.set_title("Generation speed (tokens/sec)")
    ax2.bar(x, secs_per, color=[meta_of(m)[3] for m in models])
    ax2.set_xticks(x)
    ax2.set_xticklabels([m.split("-")[0] for m in models], rotation=30, ha="right", fontsize=7)
    ax2.set_ylabel("seconds per task (50 ex)")
    ax2.set_title("Latency per task")
    fig.tight_layout()
    fig.savefig(out_dir / "persian_speed.png", dpi=140)
    plt.close(fig)

    # ---- 7. improvement: vanilla vs improved grouped bar ----
    improved = [m for m in models if "(improved)" in m]
    if improved:
        pairs = [(m.replace(" (improved)", ""), m) for m in improved
                 if m.replace(" (improved)", "") in data]
        pairs.sort(key=lambda pr: data[pr[1]]["mean"], reverse=True)
        if pairs:
            fig, ax = plt.subplots(figsize=(11, 5))
            names = [pr[0].replace("_", "-") for pr in pairs]
            n = len(pairs)
            x = np.arange(n)
            w = 0.38
            vv = [data[pr[0]]["mean"] for pr in pairs]
            iv = [data[pr[1]]["mean"] for pr in pairs]
            ax.bar(x - w / 2, vv, w, label="vanilla", color="#9aa0a6")
            ax.bar(x + w / 2, iv, w, label="improved", color="#2e7d32")
            for i, (a, b) in enumerate(zip(vv, iv)):
                ax.text(i - w / 2, a + 0.008, f"{a:.3f}", ha="center", fontsize=7)
                ax.text(i + w / 2, b + 0.008, f"{b:.3f}", ha="center", fontsize=7,
                        color="#2e7d32", fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(names, rotation=25, ha="right", fontsize=8)
            ax.set_ylabel("Mean accuracy (7 Persian tasks)")
            ax.set_title("Improved prompting (ROLE/CONTEXT/CONSTRAINTS/OUTPUT FORMAT) vs vanilla")
            ax.legend(fontsize=8)
            ax.set_ylim(0, max(max(vv), max(iv)) * 1.2)
            fig.tight_layout()
            fig.savefig(out_dir / "persian_improvement.png", dpi=140)
            plt.close(fig)

    # ---- 8. per-task spider (7 axes) per model ----    n_task = len(TASK_NAMES)
    t_angles = np.linspace(0, 2 * np.pi, n_task, endpoint=False).tolist()
    t_angles += t_angles[:1]
    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    for m in models:
        vals = [data[m]["accs"].get(t) or 0 for t in TASK_NAMES]
        vals += vals[:1]
        _, _, fam, color = meta_of(m)
        ax.plot(t_angles, vals, label=m, color=color, linewidth=1.2)
        ax.fill(t_angles, vals, color=color, alpha=0.06)
    ax.set_xticks(t_angles[:-1])
    ax.set_xticklabels([TASK_LABELS[t] for t in TASK_NAMES], fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_title("Per-task spider (7 Persian tasks)", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_spider.png", dpi=140)
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
