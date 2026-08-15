#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live progress dashboard for the RAG setup.

Shows:
  1. Model download progress bars (size, %, MB/s, attempt count)
  2. Local service health (llama.cpp, embeddings, vLLM, Open WebUI, vector DBs)
  3. Plan completion % (parsed from docs/plan.md checkboxes)

Usage:
  python scripts/progress_report.py --once      # single render
  python scripts/progress_report.py --watch     # refresh every --interval sec
"""
import argparse
import json
import os
import re
import socket
import time
import urllib.request
from pathlib import Path

ROOT = Path("/splunk-data/v1/Work_RAG-Server-Setup")
MODELS = ROOT / "offline-prep" / "models" / "huggingface"
LOGS = ROOT / "offline-prep" / "logs"
PLAN = ROOT / "docs" / "plan.md"

TARGETS = [
    {"repo": "bartowski/Qwen2.5-7B-Instruct-GGUF", "file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
     "size": 4683074240, "label": "Qwen2.5-7B Q4_K_M"},
    {"repo": "bartowski/Llama-3.2-3B-Instruct-GGUF", "file": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
     "size": 2019377696, "label": "Llama-3.2-3B Q4_K_M"},
    {"repo": "bartowski/Mistral-7B-Instruct-v0.3-GGUF", "file": "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
     "size": 4372812000, "label": "Mistral-7B Q4_K_M"},
    {"repo": "bartowski/Qwen2.5-72B-Instruct-GGUF", "file": "Qwen2.5-72B-Instruct-Q4_K_M.gguf",
     "size": 47400000000, "label": "Qwen2.5-72B Q4_K_M"},
    {"repo": "bartowski/Qwen2.5-72B-Instruct-GGUF",
     "file": "Qwen2.5-72B-Instruct-Q8_0/Qwen2.5-72B-Instruct-Q8_0-00001-of-00002.gguf",
     "size": 40000000000, "label": "Qwen2.5-72B Q8_0 (1/2)"},
    {"repo": "bartowski/Qwen2.5-72B-Instruct-GGUF",
     "file": "Qwen2.5-72B-Instruct-Q8_0/Qwen2.5-72B-Instruct-Q8_0-00002-of-00002.gguf",
     "size": 37300000000, "label": "Qwen2.5-72B Q8_0 (2/2)"},

    {"repo": "Qwen/Qwen3-30B-A3B-GGUF", "file": "Qwen3-30B-A3B-Q4_K_M.gguf",
     "size": 18600000000, "label": "Qwen3-30B-A3B Q4_K_M"},
    {"repo": "bartowski/google_gemma-3-27b-it-GGUF", "file": "google_gemma-3-27b-it-Q4_K_M.gguf",
     "size": 16550000000, "label": "Gemma-3-27B Q4_K_M (gated)"},
    {"repo": "bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF",
     "file": "Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf",
     "size": 30220000000, "label": "Nemotron Super-49B Q4_K_M"},
    {"repo": "bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF",
     "file": "Llama-3_1-Nemotron-Ultra-253B-v1-Q4_K_M-00001-of-00006.gguf",
     "size": 150940000000, "label": "Nemotron Ultra-253B Q4_K_M"},
    {"repo": "unsloth/MiniMax-M3-GGUF",
     "file": "UD-IQ4_XS/MiniMax-M3-UD-IQ4_XS-00002-of-00006.gguf",
     "size": 207500000000, "label": "MiniMax-M3 UD-IQ4_XS"},
    {"repo": "zai-org/GLM-5.2-FP8", "file": "model-00001-of-00141.safetensors",
     "size": 755600000000, "label": "GLM-5.2 FP8"},
    {"repo": "unsloth/Kimi-K3-GGUF", "file": "UD-IQ1_S/Kimi-K3-UD-IQ1_S-00002-of-00014.gguf",
     "size": 594000000000, "label": "Kimi K3 UD-IQ1_S"},
    {"repo": "deepseek-ai/DeepSeek-V4-Flash", "file": "model-00001-of-00046.safetensors",
     "size": 159600000000, "label": "DeepSeek-V4-Flash"},
]

SERVICES = [
    ("embeddings", 8001, "http://127.0.0.1:8001/health"),
    ("llama.cpp", 8080, "http://127.0.0.1:8080/health"),
    ("vllm", 8000, "http://127.0.0.1:8000/v1/models"),
    ("open-webui", 13000, "http://127.0.0.1:13000"),
    ("milvus", 19530, None),
    ("qdrant", 16333, "http://127.0.0.1:16333/healthz"),
    ("pgvector", 15432, None),
    ("redis", 16379, None),
    ("grafana", 13001, "http://127.0.0.1:13001/api/health"),
    ("prometheus", 19090, "http://127.0.0.1:19090/prometheus/-/healthy"),
    ("otel-collector", 14318, None),
    ("gpu-exporter", 9101, "http://127.0.0.1:9101/metrics"),
]


def http_ok(url: str, timeout: float = 3.0) -> bool:
    if url is None:
        return False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def port_open(port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False


def model_bytes(t: dict) -> int:
    d = MODELS / t["repo"].replace("/", "_")
    final = d / t["file"]
    if final.exists():
        return final.stat().st_size
    best = 0
    dl = d / ".cache" / "huggingface" / "download"
    if dl.is_dir():
        for p in dl.iterdir():
            if p.is_file() and p.suffix == ".incomplete":
                best = max(best, p.stat().st_size)
    return best


def download_attempts(t: dict) -> dict:
    counts = {"ok": 0, "fail": 0, "giveup": 0, "start": 0}
    logs = sorted(LOGS.glob("dl_models_*.log"))
    if not logs:
        return counts
    pat = re.compile(
        rf"\[(INFO|WARNING|ERROR)\] (OK|FAIL|GIVEUP|START) {re.escape(t['repo'])}")
    for line in logs[-1].read_text(errors="ignore").splitlines():
        m = pat.search(line)
        if not m:
            continue
        st, kind = m.group(1), m.group(2)
        if kind == "OK":
            counts["ok"] += 1
        elif kind == "FAIL":
            counts["fail"] += 1
        elif kind == "GIVEUP":
            counts["giveup"] = 1
        elif kind == "START":
            counts["start"] += 1
    return counts


def plan_status() -> dict:
    if not PLAN.exists():
        return {"pct": 0, "lines": []}
    done = total = 0
    rows = []
    current_p = None
    for line in PLAN.read_text().splitlines():
        if re.match(r"^## P\d", line):
            current_p = line.strip(" #")
        m = re.match(r"- \[(x| )\] (.*)", line)
        if m:
            total += 1
            checked = m.group(1) == "x"
            done += checked
            rows.append({"p": current_p or "?", "done": checked, "text": m.group(2)})
    pct = int(100 * done / total) if total else 0
    return {"pct": pct, "done": done, "total": total, "rows": rows}


def bar(fraction: float, width: int = 22) -> str:
    filled = int(round(fraction * width))
    return "█" * filled + "░" * (width - filled)


def render(prev_sizes=None, dt: float = 0.0):
    now = time.time()
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f" RAG SETUP DASHBOARD   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'='*60}")

    sizes = {}
    lines.append("\n[MODEL DOWNLOADS]")
    for t in TARGETS:
        b = model_bytes(t)
        sizes[t["file"]] = b
        frac = min(1.0, b / t["size"])
        state = "OK" if frac >= 1.0 else ("DL" if b > 0 else "wait")
        speed = ""
        if prev_sizes and b > 0 and prev_sizes.get(t["file"], 0) >= 0 and dt > 0:
            mbps = (b - prev_sizes.get(t["file"], 0)) / dt / 1e6
            speed = f" {mbps:5.1f} MB/s" if mbps > 0 else ""
        attempts = download_attempts(t)
        label = f"{t['label']:<18}"
        lines.append(
            f" {bar(frac)} {frac*100:5.1f}%  {state:<4} {b/1e9:5.2f}/{t['size']/1e9:.2f} GB"
            f"{speed}  fails={attempts['fail']}  {label}")

    lines.append("\n[SERVICES]")
    for name, port, url in SERVICES:
        up = http_ok(url) if url else port_open(port)
        lines.append(f"  {'UP ' if up else 'DOWN'}  :{port:<5} {name}")

    ps = plan_status()
    lines.append(f"\n[PLAN]  {ps['pct']}% complete ({ps['done']}/{ps['total']} deliverables)")
    return "\n".join(lines), sizes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="refresh continuously")
    ap.add_argument("--once", action="store_true", help="single render")
    ap.add_argument("--interval", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    prev = None
    while True:
        t0 = time.time()
        text, sizes = render(prev, dt=args.interval if args.watch else 2.0)
        if args.json:
            ps = plan_status()
            print(json.dumps({"sizes": sizes, "plan_pct": ps["pct"]}, indent=2))
        else:
            print("\033c" if args.watch else "", end="")
            print(text)
        if args.once or (args.json and not args.watch):
            break
        prev = sizes
        elapsed = time.time() - t0
        time.sleep(max(0.5, args.interval - elapsed))
        if args.watch and elapsed > args.interval:
            pass


if __name__ == "__main__":
    main()
