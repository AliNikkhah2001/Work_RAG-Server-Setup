#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a comprehensive Persian-eval report: Markdown + high-res PNG plots +
interactive Plotly HTML charts, from logs/evalp_*.json.

Plots produced (both PNG and interactive Plotly HTML):
  - persian_mean          : ranked bar of mean accuracy (vanilla + improved paired)
  - persian_by_task       : grouped per-task bars
  - persian_scatter       : model size (GB) vs mean accuracy (bubble = params)
  - persian_radar         : ability-group radar (all models)
  - persian_radar_family  : one radar per model family
  - persian_speed         : tokens/sec and avg secs/task per model
  - persian_spider        : per-task (7-axis) spider per model
  - persian_improvement   : vanilla vs improved-prompting mean accuracy
  - persian_nshot         : 0/1/2/3/5-shot curve (per model, when data exists)
  - persian_temperature   : temperature sweep (when data exists)

Color scheme: every model gets ONE color used everywhere (vanilla AND improved);
same model family shares similar shades. Improved is drawn with a hatch/edge so the
pair is visually distinct while the model color stays consistent.
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

ABILITY_GROUPS = {
    "Reasoning & Knowledge": ["fa_arc", "fa_mc", "fa_math"],
    "Language Understanding": ["fa_sentiment", "fa_entail"],
    "Information Extraction": ["fa_ner", "fa_rc"],
}

# ---------------------------------------------------------------------------
# Model metadata — full detail for the report's "Models" section. Keyed by the
# GGUF filename stem as stored in the eval JSON (Path(model).stem).
# ---------------------------------------------------------------------------
MODEL_META = {
    "google_gemma-4-31B-it-Q4_K_M": {
        "name": "Gemma 4 31B IT", "family": "Gemma",
        "creator": "Google DeepMind", "license": "Apache 2.0",
        "type": "Dense decoder-only (multimodal: text+image)",
        "params": 31, "active": 31, "disk": 19.6, "ctx": "256K",
        "arch": "60 layers, hybrid sliding-window+global attention, GQA, p-RoPE, 262K vocab",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/google/gemma-4-31B",
        "color": "#C62828",
    },
    "google_gemma-3-27b-it-Q4_K_M": {
        "name": "Gemma 3 27B IT", "family": "Gemma",
        "creator": "Google DeepMind", "license": "Gemma Terms of Use",
        "type": "Dense decoder-only (multimodal: text+image)",
        "params": 27, "active": 27, "disk": 16.5, "ctx": "128K",
        "arch": "Gemma 3 transformer, GQA, sliding window (SWA), 256K vocab",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/google/gemma-3-27b-it",
        "color": "#F5A3A3",
    },
    "Qwen3.8-27B-Q4_K_M": {
        "name": "Qwen3.8-27B", "family": "Qwen",
        "creator": "Alibaba (Qwen team)", "license": "Apache 2.0",
        "type": "Dense decoder-only VLM (text+image+video), thinking mode",
        "params": 27, "active": 27, "disk": 17.8, "ctx": "262K (→1M)",
        "arch": "64 layers, GQA 24/4 heads, Gated-DeltaNet linear attention interleaved with full attention",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/Qwen/Qwen3.8-27B",
        "color": "#1565C0",
    },
    "Qwen3-30B-A3B-Q4_K_M": {
        "name": "Qwen3-30B-A3B", "family": "Qwen",
        "creator": "Alibaba (Qwen team)", "license": "Apache 2.0",
        "type": "Mixture-of-Experts decoder-only (3B active), thinking mode",
        "params": 30, "active": 3, "disk": 18.6, "ctx": "128K",
        "arch": "MoE (A3B = 3B active of 30B), GQA, thinking mode",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/Qwen/Qwen3-30B-A3B",
        "color": "#90CAF9",
    },
    "nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M": {
        "name": "Nemotron Super 49B v1", "family": "Nemotron",
        "creator": "NVIDIA", "license": "NVIDIA Open Model + Llama 3.3 Community",
        "type": "Dense decoder-only reasoning model (Llama-3.3-70B derivative, NAS)",
        "params": 49, "active": 49, "disk": 30.2, "ctx": "128K",
        "arch": "Llama-3.3-70B-Instruct customized via Neural Architecture Search",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/nvidia/Llama-3_3-Nemotron-Super-49B-v1",
        "color": "#2E7D32",
    },
    "Qwen2.5-7B-Instruct-Q4_K_M": {
        "name": "Qwen2.5-7B Instruct", "family": "Qwen",
        "creator": "Alibaba (Qwen team)", "license": "Apache 2.0",
        "type": "Dense decoder-only Instruct",
        "params": 7.6, "active": 7.6, "disk": 4.4, "ctx": "32K",
        "arch": "28 layers, GQA 28/4 heads, SwiGLU, RoPE",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "color": "#42A5F5",
    },
    "Llama-3.2-3B-Instruct-Q4_K_M": {
        "name": "Llama 3.2 3B Instruct", "family": "Llama",
        "creator": "Meta AI", "license": "Llama 3.2 Community License",
        "type": "Dense decoder-only Instruct",
        "params": 3.2, "active": 3.2, "disk": 1.9, "ctx": "128K",
        "arch": "Llama 3.2 transformer, GQA",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
        "color": "#8E6A3E",
    },
    "Mistral-7B-Instruct-v0.3-Q4_K_M": {
        "name": "Mistral 7B Instruct v0.3", "family": "Mistral",
        "creator": "Mistral AI", "license": "Apache 2.0",
        "type": "Dense decoder-only Instruct",
        "params": 7.3, "active": 7.3, "disk": 4.4, "ctx": "32K",
        "arch": "32 layers, GQA 8/8 heads, Sliding Window Attention, SwiGLU",
        "weights": "GGUF Q4_K_M", "run": "GPU", "link": "https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3",
        "color": "#00ACC1",
    },
    "Phi-3-mini-4k-instruct-q4": {
        "name": "Phi-3 Mini 4K Instruct", "family": "Phi-3",
        "creator": "Microsoft", "license": "MIT",
        "type": "Dense decoder-only Instruct",
        "params": 3.8, "active": 3.8, "disk": 2.4, "ctx": "4K",
        "arch": "32 layers, GQA 32/4 heads, 4K context",
        "weights": "GGUF q4", "run": "GPU", "link": "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct",
        "color": "#AB47BC",
    },
}

# Vanilla-eval GGUF stems (from the plain evalp_*.json files)
VANILLA_STEMS = {
    "google_gemma-4-31B-it-Q4_K_M",
    "google_gemma-3-27b-it-Q4_K_M",
    "Qwen3.8-27B-Q4_K_M",
    "Qwen3-30B-A3B-Q4_K_M",
    "nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M",
    "Qwen2.5-7B-Instruct-Q4_K_M",
    "Llama-3.2-3B-Instruct-Q4_K_M",
    "Mistral-7B-Instruct-v0.3-Q4_K_M",
    "Phi-3-mini-4k-instruct-q4",
}

# For n-shot / temperature runs, the model stem is the same but the file name
# carries the variant tag. We keep one canonical "model key" = vanilla stem.
# Families -> one base hue, models in the family get shades of it.
FAMILY_COLORS = {
    "Gemma": "#C62828",
    "Qwen": "#1565C0",
    "Nemotron": "#2E7D32",
    "Llama": "#8E6A3E",
    "Mistral": "#00ACC1",
    "Phi-3": "#AB47BC",
}


def meta_of(stem):
    return MODEL_META.get(stem, {
        "name": stem, "family": "?", "creator": "?", "license": "?",
        "type": "?", "params": None, "active": None, "disk": None, "ctx": "?",
        "arch": "?", "weights": "?", "run": "?", "link": "?", "color": "#999999"})


def model_stem(model_key):
    """Strip (variant) suffixes from a loaded model key to get the GGUF stem."""
    for suf in (" (improved)", " (2-shot)", " (1-shot)", " (3-shot)", " (5-shot)",
                " (0-shot)", " (temp0.2)", " (temp0.5)", " (temp0.8)", " (temp1)"):
        model_key = model_key.replace(suf, "")
    return model_key


def load_results():
    """Load all evalp_*.json; key = GGUF stem + optional (variant) suffix."""
    data = {}
    for p in sorted(LOG_DIR.glob("evalp_*.json")):
        if "smoke" in p.name:
            continue
        with open(p) as f:
            d = json.load(f)
        stem = Path(d["model"]).stem
        variants = []
        if "improved" in p.name:
            variants.append("improved")
        n_shots = d.get("n_shots", 0) or 0
        if n_shots:
            variants.append(f"{n_shots}-shot")
        else:
            # older files: infer shot count from the filename
            for tag in ("1shot", "2shot", "3shot", "5shot"):
                if f"_{tag}" in p.name or f"-{tag}" in p.name:
                    variants.append(f"{tag[0]}-shot")
                    break
        temp = d.get("temperature", 0.0) or 0.0
        if temp and temp > 0:
            variants.append(f"temp{temp:g}")
        elif not temp and not n_shots:
            # older files: infer variant from the filename (temp02/temp05/...)
            for tag, val in [("temp02", 0.2), ("temp05", 0.5), ("temp08", 0.8),
                             ("temp10", 1.0), ("temp02", 0.2)]:
                if tag in p.name:
                    variants.append(f"temp{val:g}")
                    break
        key = stem + "".join(f" ({v})" for v in variants)
        accs = {r["task"]: r["acc"] for r in d["results"]}
        samples = {r["task"]: r["samples"] for r in d["results"]}
        secs = {r["task"]: r.get("secs") for r in d["results"]}
        tok_sec = {r["task"]: r.get("tok_sec") for r in d["results"]}
        data[key] = {"mean": d["overall_mean"], "accs": accs, "samples": samples,
                     "secs": secs, "tok_sec": tok_sec,
                     "prompt_style": d.get("prompt_style", "vanilla"),
                     "n_shots": d.get("n_shots", 0), "temperature": d.get("temperature", 0.0)}
    return data


def bench_key(model_key):
    stem = model_stem(model_key).lower()
    for short, full in [("gemma-4", "gemma-4-31b"), ("gemma-3", "gemma-3-27b"),
                        ("nemotron", "nemotron-49b"), ("qwen3.8", "qwen3.8-27b"),
                        ("qwen2.5", "qwen2.5-7b"), ("llama-3.2", "llama3.2-3b"),
                        ("qwen3-30b", "qwen3-30b"), ("mistral", "mistral-7b"),
                        ("phi-3", "phi3-mini")]:
        if short in stem:
            return full
    return None


def load_speed_bench():
    bench = {}
    p = LOG_DIR / "speed_bench.json"
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


def base_stem(key):
    for suf in (" (improved)", " (2-shot)", " (1-shot)", " (3-shot)", " (5-shot)",
                " (0-shot)", " (temp0.2)", " (temp0.5)", " (temp0.8)", " (temp1)"):
        key = key.replace(suf, "")
    return key


def vanilla_pairs(data):
    """Return [(stem, vanilla_key, improved_key)] sorted by improved mean desc."""
    pairs = []
    for k in data:
        if "(improved)" not in k:
            continue
        stem = base_stem(k)
        vk = stem
        if vk in data:
            pairs.append((stem, vk, k))
    pairs.sort(key=lambda pr: data[pr[2]]["mean"], reverse=True)
    return pairs


def format_size(gb):
    return f"{gb:.1f} GB" if gb else "?"


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------
def build_report(data, out_path):
    models = sorted(data, key=lambda m: data[m]["mean"], reverse=True)
    L = []
    L.append("# Persian LLM Evaluation Report\n")
    L.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M UTC}\n")

    # ---- Models summary ----
    L.append("## Models (sorted by mean accuracy)\n")
    L.append("| Model | Creator | Type | Params (active) | Size on disk | Context | "
             "Weights | Mean | " + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
    L.append("|---|" + "---|" * (len(TASK_NAMES) + 8))
    for m in models:
        if "(improved)" in m or "shot" in m or "temp" in m:
            continue
        meta = meta_of(m)
        pf = f"{meta['params']}B"
        if meta.get("active") and meta["active"] != meta["params"]:
            pf += f" ({meta['active']}B act.)"
        row = (f"| [{meta['name']}]({meta['link']}) | {meta['creator']} | {meta['type']} | "
               f"{pf} | {format_size(meta['disk'])} | {meta['ctx']} | {meta['weights']} | "
               f"{data[m]['mean']:.3f} |")
        for t in TASK_NAMES:
            a = data[m]["accs"].get(t)
            row += f" {a:.3f} |" if a is not None else " — |"
        L.append(row)

    # ---- Model detail section ----
    L.append("\n## Model details — architecture, creator, license, deployment\n")
    L.append("All nine models were downloaded from the Hugging Face Hub as **GGUF** weight files, "
             "quantized with llama.cpp (Q4_K_M unless noted), and run **offline on the same "
             "2× H200 NVL GPU box** via llama-cpp-python (GPU offload, `n_gpu_layers=-1`). "
             "Nothing ran on CPU. The 7-task Persian eval is single-pass, temperature 0.0, "
             "max_tokens 400 (needed so Qwen3-style thinking blocks are not truncated).\n")
    L.append("| Property | " + " | ".join(f"[{meta_of(m)['name']}]({meta_of(m)['link']})" for m in models if "shot" not in m and "temp" not in m and "improved" not in m) + " |")
    L.append("|---|" + "---|" * sum(1 for m in models if "shot" not in m and "temp" not in m and "improved" not in m))
    props = [
        ("Creator", lambda meta: meta["creator"]),
        ("License", lambda meta: meta["license"]),
        ("Architecture", lambda meta: meta["type"]),
        ("Params / active", lambda meta: f"{meta['params']}B / {meta['active']}B"),
        ("Context window", lambda meta: meta["ctx"]),
        ("Key arch notes", lambda meta: meta["arch"]),
        ("Weights format", lambda meta: meta["weights"]),
        ("Disk size", lambda meta: format_size(meta["disk"])),
        ("Hardware", lambda meta: meta["run"]),
    ]
    for pname, fn in props:
        cells = [fn(meta_of(m)) for m in models if "shot" not in m and "temp" not in m and "improved" not in m]
        L.append("| " + pname + " | " + " | ".join(cells) + " |")

    # ---- Ability groups ----
    L.append("\n## Ability-group scores (radar chart data)\n")
    L.append("| Model | " + " | ".join(ABILITY_GROUPS) + " |")
    L.append("|---|" + "---|" * len(ABILITY_GROUPS))
    for m in models:
        if "shot" in m or "temp" in m or "improved" in m:
            continue
        ga = group_accuracy(data[m]["accs"])
        L.append(f"| {m} | " + " | ".join(f"{ga[c]:.3f}" for c in ga) + " |")

    # ---- Figures ----
    L.append("\n## Figures\n")
    L.append("- **persian_mean.png** — ranked mean accuracy, vanilla vs improved paired.\n")
    L.append("- **persian_by_task.png** — accuracy per task across models.\n")
    L.append("- **persian_scatter.png** — model size (disk GB) vs mean accuracy; bubble = params.\n")
    L.append("- **persian_radar.png** — ability-group profile per model.\n")
    L.append("- **persian_radar_family.png** — per-family radar profiles.\n")
    L.append("- **persian_speed.png** — tokens/sec and latency per task.\n")
    L.append("- **persian_spider.png** — per-task (7-axis) spider per model.\n")
    L.append("- **persian_improvement.png** — vanilla vs improved-prompting mean accuracy.\n")
    L.append("- **persian_nshot.png** — few-shot scaling (0/1/2/3/5-shot).\n")
    L.append("- **persian_temperature.png** — temperature sweep (0.0→1.0).\n")
    L.append("\nInteractive (Plotly) versions of every chart: `docs/reports/interactive/<name>.html`.\n")

    # ---- Improved prompting ----
    L.append("\n## Improved prompting vs vanilla\n")
    L.append("Every model was re-run on the full 7-task suite with **improved Persian prompts** "
             "(4-component framework: ROLE + CONTEXT + CONSTRAINTS + OUTPUT FORMAT, kept under "
             "~80 tokens per task). The scorers expect a strict output shape (letter, option number, "
             "final-answer block, one label, tuple list, short span), and the improved templates "
             "pin exactly that shape in Persian.\n")
    pairs = vanilla_pairs(data)
    if pairs:
        L.append("| Model | Family | vanilla mean | improved mean | Δ |")
        L.append("|---|--:|--:|--:|--:|")
        for stem, vk, ik in pairs:
            meta = meta_of(stem)
            L.append(f"| {meta['name']} | {meta['family']} | {data[vk]['mean']:.3f} | "
                     f"{data[ik]['mean']:.3f} | {data[ik]['mean'] - data[vk]['mean']:+.3f} |")
        L.append("\n### Per-task deltas (improved − vanilla)\n")
        L.append("| Model | " + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
        L.append("|---|" + "---|" * len(TASK_NAMES))
        for stem, vk, ik in pairs:
            row = [meta_of(stem)["name"]]
            for t in TASK_NAMES:
                vi = data[ik]["accs"].get(t)
                vv = data[vk]["accs"].get(t)
                row.append(f"{vi - vv:+.2f}" if vi is not None and vv is not None else "—")
            L.append("| " + " | ".join(row) + " |")

    # ---- n-shot section ----
    nshot_models = sorted({base_stem(k) for k in data if any(f"({n}-shot)" in k for n in (1, 2, 3, 5))})
    if nshot_models:
        L.append("\n## Few-shot scaling (0/1/2/3/5-shot)\n")
        L.append("Same task prompts, N correct in-task exemplars prepended before the question. "
                 "Numbers below are the mean over the 7 tasks; see `persian_nshot.png`.\n")
        for stem in nshot_models:
            meta = meta_of(stem)
            L.append(f"\n### {meta['name']}\n")
            L.append("| Shots | Mean | " + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
            L.append("|---|--:|" + "---|" * len(TASK_NAMES))
            for n in (0, 1, 2, 3, 5):
                key = stem if n == 0 else f"{stem} ({n}-shot)"
                if key not in data:
                    continue
                L.append(f"| {n} | {data[key]['mean']:.3f} |" + " | ".join(
                    f"{data[key]['accs'].get(t):.3f}" if data[key]['accs'].get(t) is not None else " —"
                    for t in TASK_NAMES) + " |")
    else:
        L.append("\n## Few-shot scaling\n\n_(no n-shot runs found yet)_\n")

    # ---- temperature section ----
    temp_models = sorted({base_stem(k) for k in data if any(f"temp{t:g}" in k for t in (0.2, 0.5, 0.8, 1.0))})
    if temp_models:
        L.append("\n## Effect of temperature\n")
        L.append("Same prompts re-run at increasing sampling temperature (greedy 0.0 baseline → "
                 "0.2 / 0.5 / 0.8 / 1.0). Higher temperature = more diverse (but less reproducible) "
                 "answers; label/format tasks typically degrade while reasoning tasks can benefit "
                 "slightly. See `persian_temperature.png`.\n")
        for stem in temp_models:
            meta = meta_of(stem)
            L.append(f"\n### {meta['name']}\n")
            L.append("| T | Mean | " + " | ".join(TASK_LABELS[t] for t in TASK_NAMES) + " |")
            L.append("|---|--:|" + "---|" * len(TASK_NAMES))
            for t in (0.0, 0.2, 0.5, 0.8, 1.0):
                key = stem if t == 0.0 else f"{stem} (temp{t:g})"
                if key not in data:
                    continue
                L.append(f"| {t:g} | {data[key]['mean']:.3f} |" + " | ".join(
                    f"{data[key]['accs'].get(t):.3f}" if data[key]['accs'].get(t) is not None else " —"
                    for t in TASK_NAMES) + " |")
    else:
        L.append("\n## Effect of temperature\n\n_(no temperature runs found yet)_\n")

    # ---- Same question ----
    L.append("\n## Same question, all models (first example per task)\n")
    L.append("The same test prompt was sent to every model. Gold answers and per-model outputs "
             "show *why* scores differ (format-following, Persian fluency, reasoning quality).\n")
    for t in TASK_NAMES:
        L.append(f"\n### {TASK_LABELS.get(t, t)}\n")
        gold = None
        outs = []
        for m in models:
            if "shot" in m or "temp" in m or "improved" in m:
                continue
            smps = data[m]["samples"].get(t)
            if not smps:
                continue
            s = smps[0]
            if gold is None:
                gold = s["gold"]
                L.append(f"- **Prompt**: {s['prompt'][:250]}\n- **Gold**: {gold}\n")
            outs.append((m, s))
        for m, s in outs:
            L.append(f"- **{m}** (hit {'✅' if s['hit'] else '❌'}): `{s['output'][:160]}`")
        if not outs:
            L.append("- *(no samples)*")

    # ---- Per-model samples ----
    L.append("\n## Per-model samples\n")
    for m in models:
        if "shot" in m or "temp" in m or "improved" in m:
            continue
        L.append(f"\n### {m} (mean {data[m]['mean']:.3f})\n")
        for t in TASK_NAMES:
            smps = data[m]["samples"].get(t)
            if not smps:
                continue
            L.append(f"\n#### {TASK_LABELS.get(t, t)} — acc {data[m]['accs'].get(t)}\n")
            shown = 0
            for s in smps:
                if shown >= 2:
                    break
                shown += 1
                L.append(f"- **Prompt**: {s['prompt'][:200]}")
                L.append(f"  - **Gold**: {s['gold'][:120]}")
                L.append(f"  - **Pred**: {s['pred'][:80]}")
                L.append(f"  - **Output**: {s['output'][:200]}")
                L.append(f"  - **Hit**: {'✅' if s['hit'] else '❌'}")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "figure.dpi": 200,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
})


def short_label(key):
    stem = base_stem(key)
    return meta_of(stem)["name"]


def color_of(key):
    return meta_of(base_stem(key))["color"]


INTERACTIVE_DIR = None


def set_interactive_dir(d):
    global INTERACTIVE_DIR
    INTERACTIVE_DIR = Path(d)


def write_interactive(name, fig_mpl, traces, layout):
    """Best-effort interactive Plotly export of a matplotlib figure."""
    if INTERACTIVE_DIR is None:
        return
    try:
        import plotly.graph_objects as go
        fig = go.Figure(data=traces, layout=layout)
        (INTERACTIVE_DIR / f"{name}.html").write_text(fig.to_html(full_html=False,
                                                                  include_plotlyjs="cdn"))
    except Exception as e:
        print(f"  [plotly] {name}: {e}")


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
def make_plots(data, out_dir):
    vanilla = sorted((k for k in data if base_stem(k) in VANILLA_STEMS and not any(
        s in k for s in ("(improved)", "-shot", "temp"))), key=lambda m: data[m]["mean"], reverse=True)
    pairs = vanilla_pairs(data)
    all_keys = vanilla + [k for _, _, k in pairs]

    # ---- 1. ranked mean bar (vanilla + improved paired, same model color) ----
    n = len(all_keys)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, k in enumerate(all_keys):
        imp = "(improved)" in k
        c = color_of(k)
        bars = ax.bar(i, data[k]["mean"], color=c, alpha=0.92 if not imp else 0.55,
                      edgecolor=c, hatch="//" if imp else None)
        ax.text(i, data[k]["mean"] + 0.008, f"{data[k]['mean']:.3f}", ha="center", fontsize=7,
                fontweight="bold" if not imp else "normal")
    ax.set_xticks(range(n))
    ax.set_xticklabels([short_label(k) + (" ⇑" if "(improved)" in k else "") for k in all_keys],
                       rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("Mean accuracy (7 Persian tasks)")
    ax.set_title("Persian eval — mean accuracy (solid = vanilla, hatched = improved prompting)")
    ax.set_ylim(0, max(data[k]["mean"] for k in all_keys) * 1.18)
    handles = [plt.Rectangle((0, 0), 1, 1, color="#666666"),
               plt.Rectangle((0, 0), 1, 1, color="#666666", hatch="//", alpha=0.6)]
    ax.legend(handles, ["vanilla", "improved"], fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(out_dir / "persian_mean.png")
    write_interactive("persian_mean", fig, [
        {"x": [short_label(k) for k in all_keys],
         "y": [data[k]["mean"] for k in all_keys],
         "type": "bar", "name": "accuracy",
         "marker": {"color": [color_of(k) for k in all_keys]},
         "text": [f"{data[k]['mean']:.3f}" for k in all_keys], "textposition": "outside"}
    ], {"title": "Mean accuracy (hatched = improved)", "yaxis": {"range": [0, 1]}})
    plt.close(fig)

    # ---- 2. grouped per-task bars ----
    fig, ax = plt.subplots(figsize=(13, 6.5))
    x = np.arange(len(TASK_NAMES))
    width = 0.85 / max(len(vanilla), 1)
    for i, m in enumerate(vanilla):
        vals = [data[m]["accs"].get(t) or 0 for t in TASK_NAMES]
        ax.bar(x + i * width, vals, width, label=short_label(m), color=color_of(m))
    ax.set_xticks(x + width * (len(vanilla) - 1) / 2)
    ax.set_xticklabels([TASK_LABELS[t] for t in TASK_NAMES], rotation=12, ha="right", fontsize=8)
    ax.set_ylabel("Accuracy")
    ax.set_title("Persian eval — per-task accuracy by model")
    ax.legend(fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.set_ylim(0, 1.08)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_by_task.png")
    traces = []
    for i, m in enumerate(vanilla):
        traces.append({"x": [TASK_LABELS[t] for t in TASK_NAMES],
                       "y": [data[m]["accs"].get(t) or 0 for t in TASK_NAMES],
                       "type": "bar", "name": short_label(m),
                       "marker": {"color": color_of(m)}})
    write_interactive("persian_by_task", fig, traces, {"title": "Per-task accuracy by model",
                                                       "yaxis": {"range": [0, 1.05]}, "barmode": "group"})
    plt.close(fig)

    # ---- 3. scatter: disk size vs mean, bubble = params ----
    fig, ax = plt.subplots(figsize=(10, 6))
    for m in vanilla:
        meta = meta_of(m)
        if not meta["disk"]:
            continue
        ax.scatter(meta["disk"], data[m]["mean"], s=(meta["params"] or 3) * 90, alpha=0.75,
                   color=meta["color"], edgecolors="black", linewidths=1, label=meta["name"])
        ax.annotate(f"{meta['name']} ({meta['params']}B)", (meta["disk"], data[m]["mean"]),
                    textcoords="offset points", xytext=(6, 6), fontsize=7)
    ax.set_xlabel("Model size on disk (GB, Q4_K_M)")
    ax.set_ylabel("Mean Persian accuracy")
    ax.set_title("Accuracy vs model size (bubble area = parameter count)")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / "persian_scatter.png")
    write_interactive("persian_scatter", fig, [
        {"x": [meta_of(m)["disk"] for m in vanilla if meta_of(m)["disk"]],
         "y": [data[m]["mean"] for m in vanilla if meta_of(m)["disk"]],
         "mode": "markers+text", "type": "scatter",
         "text": [meta_of(m)["name"] for m in vanilla if meta_of(m)["disk"]],
         "marker": {"size": [meta_of(m)["params"] * 6 for m in vanilla if meta_of(m)["disk"]],
                    "color": [color_of(m) for m in vanilla if meta_of(m)["disk"]]}}
    ], {"title": "Accuracy vs disk size (bubble = params)"})
    plt.close(fig)

    # ---- 4. radar: ability groups ----
    cats = list(ABILITY_GROUPS.keys())
    n_cats = len(cats)
    angles = np.linspace(0, 2 * np.pi, n_cats, endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(8.5, 8.5), subplot_kw=dict(polar=True))
    for m in vanilla:
        ga = group_accuracy(data[m]["accs"])
        vals = [ga[c] for c in cats] + [ga[cats[0]]]
        ax.plot(angles, vals, label=short_label(m), color=color_of(m), linewidth=1.3)
        ax.fill(angles, vals, color=color_of(m), alpha=0.07)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cats, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_title("Ability-group radar (all models)", pad=22)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_radar.png")
    traces = []
    for m in vanilla:
        ga = group_accuracy(data[m]["accs"])
        vals = [ga[c] for c in cats] + [ga[cats[0]]]
        traces.append({"r": vals, "theta": cats + [cats[0]], "type": "scatterpolar",
                       "mode": "lines+markers", "name": short_label(m),
                       "line": {"color": color_of(m)}, "fill": "toself",
                       "fillcolor": color_of(m)})
    write_interactive("persian_radar", fig, traces, {"title": "Ability-group radar",
                                                     "polar": {"radialaxis": {"range": [0, 1]}}})
    plt.close(fig)

    # ---- 5. radar per family ----
    families = {}
    for m in vanilla:
        fam = meta_of(m)["family"]
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
            ax.plot(angles, vals, label=short_label(m), color=color_of(m), linewidth=1.5)
            ax.fill(angles, vals, color=color_of(m), alpha=0.15)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([c.split()[0] for c in cats], fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_title(fam, pad=18, fontsize=11)
        ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.05), fontsize=6)
    for j in range(len(fams), len(axes)):
        axes[j].axis("off")
    fig.suptitle("Ability-group radar by model family", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_radar_family.png")
    traces = []
    for m in vanilla:
        ga = group_accuracy(data[m]["accs"])
        vals = [ga[c] for c in cats] + [ga[cats[0]]]
        traces.append({"r": vals, "theta": cats + [cats[0]], "type": "scatterpolar",
                       "mode": "lines+markers", "name": short_label(m),
                       "line": {"color": color_of(m)}, "fill": "toself"})
    write_interactive("persian_radar_family", fig, traces, {"title": "Radar by family",
                                                            "polar": {"radialaxis": {"range": [0, 1]}}})
    plt.close(fig)

    # ---- 6. speed ----
    bench = load_speed_bench()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    toks, secs_per = [], []
    for m in vanilla:
        tv = [v for v in data[m]["tok_sec"].values() if v]
        sv = [v for v in data[m]["secs"].values() if v]
        ts = float(np.mean(tv)) if tv else 0
        if not ts:
            ts = bench.get(bench_key(m)) or 0
        toks.append(ts)
        secs_per.append(float(np.mean(sv)) if sv else 0)
    x = np.arange(len(vanilla))
    ax1.bar(x, toks, color=[color_of(m) for m in vanilla], edgecolor="black", linewidth=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels([short_label(m) for m in vanilla], rotation=30, ha="right", fontsize=7)
    ax1.set_ylabel("tokens/sec")
    ax1.set_title("Generation speed (tokens/sec)")
    ax2.bar(x, secs_per, color=[color_of(m) for m in vanilla], edgecolor="black", linewidth=0.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels([short_label(m) for m in vanilla], rotation=30, ha="right", fontsize=7)
    ax2.set_ylabel("seconds per task (50 ex)")
    ax2.set_title("Latency per task")
    fig.tight_layout()
    fig.savefig(out_dir / "persian_speed.png")
    write_interactive("persian_speed", fig, [
        {"x": [short_label(m) for m in vanilla], "y": toks, "type": "bar",
         "name": "tok/sec", "marker": {"color": [color_of(m) for m in vanilla]}},
        {"x": [short_label(m) for m in vanilla], "y": secs_per, "type": "bar",
         "name": "secs/task", "yaxis": "y2", "marker": {"color": "rgba(0,0,0,0.2)"}},
    ], {"title": "Speed (tok/s) and latency", "yaxis2": {"overlaying": "y", "side": "right"}})
    plt.close(fig)

    # ---- 7. improvement grouped bar ----
    if pairs:
        fig, ax = plt.subplots(figsize=(12, 5.5))
        names = [meta_of(pr[0])["name"] for pr in pairs]
        n = len(pairs)
        x = np.arange(n)
        w = 0.38
        vv = [data[pr[1]]["mean"] for pr in pairs]
        iv = [data[pr[2]]["mean"] for pr in pairs]
        ax.bar(x - w / 2, vv, w, label="vanilla", color=[color_of(pr[0]) for pr in pairs],
               alpha=0.75, edgecolor=[color_of(pr[0]) for pr in pairs])
        ax.bar(x + w / 2, iv, w, label="improved", color=[color_of(pr[0]) for pr in pairs],
               hatch="//", alpha=0.55, edgecolor=[color_of(pr[0]) for pr in pairs])
        for i, (a, b) in enumerate(zip(vv, iv)):
            ax.text(i - w / 2, a + 0.008, f"{a:.3f}", ha="center", fontsize=7)
            ax.text(i + w / 2, b + 0.008, f"{b:.3f}", ha="center", fontsize=7, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=25, ha="right", fontsize=8)
        ax.set_ylabel("Mean accuracy (7 Persian tasks)")
        ax.set_title("Improved prompting (ROLE/CONTEXT/CONSTRAINTS/OUTPUT FORMAT) vs vanilla — same color = same model")
        handles = [plt.Rectangle((0, 0), 1, 1, color="#666666"),
                   plt.Rectangle((0, 0), 1, 1, color="#666666", hatch="//", alpha=0.6)]
        ax.legend(handles, ["vanilla", "improved"], fontsize=8)
        ax.set_ylim(0, max(max(vv), max(iv)) * 1.2)
        fig.tight_layout()
        fig.savefig(out_dir / "persian_improvement.png")
        traces = []
        for i, (stem, vk, ik) in enumerate(pairs):
            c = color_of(stem)
            traces.append({"x": [meta_of(stem)["name"]], "y": [data[vk]["mean"]],
                           "type": "bar", "name": f"{meta_of(stem)['name']} (vanilla)",
                           "marker": {"color": c}, "opacity": 0.75})
            traces.append({"x": [meta_of(stem)["name"]], "y": [data[ik]["mean"]],
                           "type": "bar", "name": f"{meta_of(stem)['name']} (improved)",
                           "marker": {"color": c}, "opacity": 0.55})
        write_interactive("persian_improvement", fig, traces,
                          {"title": "Improved vs vanilla (same color = same model)",
                           "yaxis": {"range": [0, 1]}, "barmode": "group"})
        plt.close(fig)

    # ---- 8. per-task spider ----
    n_task = len(TASK_NAMES)
    t_angles = np.linspace(0, 2 * np.pi, n_task, endpoint=False).tolist()
    t_angles += t_angles[:1]
    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    for m in vanilla:
        vals = [data[m]["accs"].get(t) or 0 for t in TASK_NAMES]
        vals += vals[:1]
        ax.plot(t_angles, vals, label=short_label(m), color=color_of(m), linewidth=1.2)
        ax.fill(t_angles, vals, color=color_of(m), alpha=0.06)
    ax.set_xticks(t_angles[:-1])
    ax.set_xticklabels([TASK_LABELS[t] for t in TASK_NAMES], fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_title("Per-task spider (7 Persian tasks)", pad=22)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "persian_spider.png")
    traces = []
    for m in vanilla:
        vals = [data[m]["accs"].get(t) or 0 for t in TASK_NAMES] + [data[m]["accs"].get(TASK_NAMES[0]) or 0]
        traces.append({"r": vals, "theta": [TASK_LABELS[t] for t in TASK_NAMES] + [TASK_LABELS[TASK_NAMES[0]]],
                       "type": "scatterpolar", "mode": "lines+markers", "name": short_label(m),
                       "line": {"color": color_of(m)}, "fill": "toself"})
    write_interactive("persian_spider", fig, traces, {"title": "Per-task spider",
                                                      "polar": {"radialaxis": {"range": [0, 1]}}})
    plt.close(fig)

    # ---- 9. n-shot curve ----
    nshot_models = sorted({base_stem(k) for k in data
                           if any(f"({n}-shot)" in k for n in (1, 2, 3, 5))})
    if nshot_models:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for stem in nshot_models:
            xs, ys = [0], [data[stem]["mean"]]
            for n in (1, 2, 3, 5):
                k = f"{stem} ({n}-shot)"
                if k in data:
                    xs.append(n)
                    ys.append(data[k]["mean"])
            ax.plot(xs, ys, marker="o", label=meta_of(stem)["name"], color=meta_of(stem)["color"])
            ax.annotate(f"{meta_of(stem)['name']}: {ys[-1]:.3f}", (xs[-1], ys[-1]),
                        textcoords="offset points", xytext=(4, 4), fontsize=7)
        ax.set_xticks([0, 1, 2, 3, 5])
        ax.set_xlabel("Number of in-context exemplars (shots)")
        ax.set_ylabel("Mean accuracy (7 Persian tasks)")
        ax.set_title("Few-shot scaling")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "persian_nshot.png")
        write_interactive("persian_nshot", fig, [
            {"x": xs, "y": ys, "type": "scatter", "mode": "lines+markers",
             "name": meta_of(stem)["name"], "line": {"color": meta_of(stem)["color"]}}
            for stem in nshot_models for xs, ys in
            [([0] + [n for n in (1, 2, 3, 5) if f"{stem} ({n}-shot)" in data],
              [data[stem]["mean"]] + [data[f"{stem} ({n}-shot)"]["mean"] for n in (1, 2, 3, 5) if f"{stem} ({n}-shot)" in data])]
        ], {"title": "Few-shot scaling", "xaxis": {"dtick": 1}})
        plt.close(fig)

    # ---- 10. temperature sweep ----
    temp_models = sorted({base_stem(k) for k in data
                          if any(f"temp{t:g}" in k for t in (0.2, 0.5, 0.8, 1.0))})
    if temp_models:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for stem in temp_models:
            xs, ys = [0.0], [data[stem]["mean"]]
            for t in (0.2, 0.5, 0.8, 1.0):
                k = f"{stem} (temp{t:g})"
                if k in data:
                    xs.append(t)
                    ys.append(data[k]["mean"])
            ax.plot(xs, ys, marker="o", label=meta_of(stem)["name"], color=meta_of(stem)["color"])
        ax.set_xlabel("Sampling temperature")
        ax.set_ylabel("Mean accuracy (7 Persian tasks)")
        ax.set_title("Effect of temperature on accuracy")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "persian_temperature.png")
        write_interactive("persian_temperature", fig, [
            {"x": xs, "y": ys, "type": "scatter", "mode": "lines+markers",
             "name": meta_of(stem)["name"], "line": {"color": meta_of(stem)["color"]}}
            for stem in temp_models for xs, ys in
            [([0.0] + [t for t in (0.2, 0.5, 0.8, 1.0) if f"{stem} (temp{t:g})" in data],
              [data[stem]["mean"]] + [data[f"{stem} (temp{t:g})"]["mean"] for t in (0.2, 0.5, 0.8, 1.0) if f"{stem} (temp{t:g})" in data])]
        ], {"title": "Temperature sweep", "xaxis": {"dtick": 0.2}})
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
    set_interactive_dir(out_path.parent / "interactive")
    out_path.parent.joinpath("interactive").mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_report(data, out_path))
    make_plots(data, out_path.parent)
    print(f"wrote {out_path}")
    print(f"plots in {out_path.parent}")
    for k, d in sorted(data.items(), key=lambda kv: kv[1]["mean"], reverse=True):
        print(f"  {d['mean']:.3f}  {k}")


if __name__ == "__main__":
    main()
