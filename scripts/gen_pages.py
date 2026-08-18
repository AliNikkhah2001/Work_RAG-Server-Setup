#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the GitHub Pages multipage report site (docs-site/) from the dedicated
report folders (docs/reports/, docs/history/, README.md).

Sections are read dynamically from their source folders, then emitted as Jekyll
collection pages under docs-site/_reports/ (one file per page). The Jekyll index
page then lists every page from the collection automatically. Plots are copied
from docs/reports/ into docs-site/assets/plots/.

Run: offline-prep/venv/bin/python3.12 scripts/gen_pages.py
"""
import re
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC_REPORTS = BASE / "docs" / "reports"
SRC_HISTORY = BASE / "docs" / "history"
SITE = BASE / "docs-site"
PAGES_DIR = SITE / "_reports"
PLOTS_DIR = SITE / "assets" / "plots"
README = BASE / "README.md"

TASKS = {
    "fa_arc": "Persian ARC (MC)",
    "fa_mc": "Parsinlu MC",
    "fa_math": "Math",
    "fa_sentiment": "Sentiment",
    "fa_entail": "Entailment",
    "fa_ner": "NER",
    "fa_rc": "Reading Comp.",
}

PLOT_EXPLAIN = {
    "persian_mean.png": "Ranked mean accuracy across the 7 Persian tasks. **Each model has one "
                        "color** used consistently: solid bar = vanilla prompts, hatched bar = "
                        "improved prompting of the *same* model. Gemma-4-31B leads; small models "
                        "collapse.",
    "persian_by_task.png": "Per-task accuracy by model. Format-strict tasks (NER, entailment) "
                           "spread models most; Gemma-4 is 1.0 on NER.",
    "persian_scatter.png": "Model size on disk vs mean accuracy, bubble = parameter count. "
                           "Size helps but is not sufficient (Qwen3-30B-A3B MoE trails dense models).",
    "persian_radar.png": "Ability-group radar (Reasoning & Knowledge, Language Understanding, "
                         "Information Extraction). Gemma models fill the largest polygon.",
    "persian_radar_family.png": "Per-family radar profiles — Gemma vs Qwen vs Nemotron vs Llama "
                                "vs Mistral vs Phi. Models in the same family share similar shades.",
    "persian_speed.png": "Generation speed (tokens/sec) and latency per task. Phi-3-mini is "
                         "fastest, Nemotron-49B slowest.",
    "persian_spider.png": "Per-task 7-axis spider per model — a round spider is balanced; spikes "
                          "show task-specific strength.",
    "persian_improvement.png": "Vanilla vs improved prompting (4-component Persian templates): "
                               "every model improves, most on format-strict tasks. Same color = "
                               "same model; hatched bar = improved.",
    "persian_nshot.png": "Few-shot scaling: mean accuracy at 0 / 1 / 2 / 3 / 5 in-context "
                         "exemplars per task (Qwen2.5-7B).",
    "persian_temperature.png": "Effect of sampling temperature (0.0 → 1.0) on mean accuracy "
                               "(Qwen2.5-7B).",
}

PLOT_PAT = re.compile(r"!\[([^\]]*)\]\((docs/reports/[^)]+\.png)\)")
PLOT_PAT2 = re.compile(r"([\w-]+\.png)")


def front_matter(title, order):
    return (f"---\ntitle: \"{title}\"\nnav_order: {order}\n---\n\n")


def copy_plots():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    for p in SRC_REPORTS.glob("*.png"):
        shutil.copy2(p, PLOTS_DIR / p.name)
        print(f"plot -> {PLOTS_DIR / p.name}")
    itv = SRC_REPORTS / "interactive"
    itv_out = PLOTS_DIR / "interactive"
    if itv.exists():
        itv_out.mkdir(parents=True, exist_ok=True)
        for p in itv.glob("*.html"):
            shutil.copy2(p, itv_out / p.name)
            print(f"interactive -> {itv_out / p.name}")


def rewrite_plot_links(text):
    def repl(m):
        alt = m.group(1)
        fname = Path(m.group(2)).name
        return f"![{alt}]({{{{ '/assets/plots/{fname}' | relative_url }}}})"
    return PLOT_PAT.sub(repl, text)


def figures_page():
    """Build the Figures body: embed every plot with an explanation, plus an
    interactive Plotly iframe next to each static image."""
    out = []
    for name, explain in PLOT_EXPLAIN.items():
        if not (SRC_REPORTS / name).exists():
            continue
        out.append(f"## {name}\n")
        out.append(f"![{name}]({{{{ '/assets/plots/{name}' | relative_url }}}})\n")
        itv = SRC_REPORTS / "interactive" / f"{Path(name).stem}.html"
        if itv.exists():
            out.append(
                f"<iframe src=\"{{{{ '/assets/plots/interactive/{Path(name).stem}.html' | relative_url }}}}\" "
                f"width=\"100%\" height=\"600\" frameborder=\"0\" "
                f"title=\"Interactive {name}\"></iframe>\n")
        out.append(f"{explain}\n")
    return "\n".join(out)


def split_eval_report():
    """Split persian_eval_report.md into per-section pages (## headers)."""
    text = (SRC_REPORTS / "persian_eval_report.md").read_text()
    parts = re.split(r"^(## .*)$", text, flags=re.M)
    # parts: [preamble, hdr1, body1, hdr2, body2, ...]
    pages = []
    i = 1
    while i < len(parts):
        hdr = parts[i].strip()
        body = parts[i + 1].strip()
        title = hdr[3:].strip()
        pages.append((title, body))
        i += 2
    return pages


def page_md(title, body, order):
    b = rewrite_plot_links(body)
    return front_matter(title, order) + b + "\n"


def build():
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    copy_plots()

    # 1. main eval report -> one page per ## section
    sections = split_eval_report()
    for order, (title, body) in enumerate(sections, start=1):
        slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", title).strip("-").lower()
        slug = re.sub(r"-{2,}", "-", slug) or f"page-{order}"
        if title == "Figures":
            body = figures_page()
        (PAGES_DIR / f"{order:02d}-{slug}.md").write_text(page_md(title, body, order))
        print(f"page: {title!r}")

    # remove stale pages from earlier report versions (extra/renamed sections)
    current = {f"{order:02d}-{re.sub(r'-{2,}', '-', re.sub(r'[^\w\u0600-\u06FF]+', '-', t).strip('-').lower()):s}.md"
               for order, (t, _) in enumerate(sections, start=1)}
    for fixed in ("07-sample-questions.md", "08-prompt-engineering-qa.md", "09-embeddings.md"):
        current.add(fixed)
    for p in PAGES_DIR.glob("*.md"):
        if p.name not in current:
            p.unlink()
            print(f"stale page removed: {p.name}")

    # 2. sample questions (already a self-contained md)
    sq = (SRC_REPORTS / "persian_sample_questions.md").read_text()
    (PAGES_DIR / "07-sample-questions.md").write_text(
        front_matter("Sample questions — one tricky prompt per category", 7)
        + rewrite_plot_links(sq) + "\n")
    print("page: Sample questions")

    # 3. prompt-engineering Q&A compare
    pc = (SRC_REPORTS / "persian_prompt_compare.md").read_text()
    (PAGES_DIR / "08-prompt-engineering-qa.md").write_text(
        front_matter("Prompt engineering — vanilla vs improved full Q&A", 8)
        + rewrite_plot_links(pc) + "\n")
    print("page: Prompt engineering Q&A")

    # 4. embeddings comparison (from README §4d if present)
    readme = README.read_text()
    m = re.search(r"## 4d\. Embedding model comparison.*?(?=\n## 5\.)", readme, re.S)
    if m:
        (PAGES_DIR / "09-embeddings.md").write_text(
            front_matter("Embedding model comparison (Persian retrieval)", 9)
            + rewrite_plot_links(m.group(0)) + "\n")
        print("page: Embeddings")

    # 5. history -> condensed one page per session file
    for order, p in enumerate(sorted(SRC_HISTORY.glob("*.md")), start=10):
        if p.name == "README.md":
            continue
        body = p.read_text()
        title = body.splitlines()[0].lstrip("# ").strip()
        (PAGES_DIR / f"{order:02d}-history-{p.stem}.md").write_text(
            front_matter(title, order) + body + "\n")
        print(f"page: {title!r}")


if __name__ == "__main__":
    build()