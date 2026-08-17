---
layout: default
title: Persian LLM Benchmark & Prompt Engineering Report
nav_order: 1
---

# Work RAG Server Setup — Persian LLM Benchmark Report

Self-hosted GGUF models (2× H200 NVL) evaluated on a **7-task Persian suite**
(PersBench): ARC multiple-choice, Parsinlu MC, math, sentiment, entailment, NER
and reading comprehension — plus generation-speed benchmarks and a
**prompt-engineering study** (n-shot + 4-component ROLE/CONTEXT/CONSTRAINTS/
OUTPUT FORMAT templates).

## Summary

- **Best model:** Gemma-4-31B Q4_K_M — mean **0.663** vanilla, **0.820** with improved prompting.
- **Improved prompting helps every model**: +0.046 … +0.223 mean accuracy; the largest gains are on format-strict tasks (reading comprehension, NER, entailment) and on the previously error-prone models.
- **Thinking-mode fix mattered**: Qwen3.8-27B went 0.169 → 0.477 after `strip_think` + `max_tokens=400`.
- **Speed vs accuracy are independent axes**: Phi-3-mini is fastest (226.6 tok/s) but weakest; Nemotron-49B is slowest (45.6 tok/s) and mid-ranked.

## Table of contents

The report is a multipage site: each section below is a separate page read
automatically from the dedicated report folders.

{% assign pages = site.reports | sort: "nav_order" %}
<ol>
{% for p in pages %}
  <li><a href="{{ p.url | relative_url }}">{{ p.title }}</a></li>
{% endfor %}
</ol>

## How to reproduce

```bash
export HF_HUB_OFFLINE=1
offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model <path.gguf> \
    --limit 50 --chat --max-tokens 400 --out evalp_<name>.json
offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model <path.gguf> \
    --limit 50 --chat --prompt-style improved --out evalp_<name>_improved.json
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json
offline-prep/venv/bin/python3.12 scripts/gen_prompt_compare.py
offline-prep/venv/bin/python3.12 scripts/gen_eval_report.py
offline-prep/venv/bin/python3.12 scripts/gen_pages.py   # rebuild this site
```

## Navigation

Use the sidebar to jump between the benchmark, per-task samples, the
prompt-engineering study and the work history.