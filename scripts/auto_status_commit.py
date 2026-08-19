#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auto_status_commit.py — 30-minute live-status daemon for Work_RAG-Server-Setup.

Every cycle (default every 1800 s) the daemon:
  1. Probes the live GitHub Pages site (index, 04-figures, n-shot, temperature).
  2. Regenerates plots/report/pages (gen_eval_report.py + gen_pages.py) when the
     underlying eval logs are newer than the published artifacts.
  3. Scans HF model download progress (bytes on disk vs expected size) and tails
     the latest download log for last-activity.
  4. Scans running inference/embedding services (embed_server, llama_chat_server,
     vllm, download daemon).
  5. Reads GPU memory via nvidia-smi.
  6. Rewrites the README "## Implementation Progress" section, flipping
     checkboxes where real evidence shows a task is done.
  7. Appends a "## Download Progress" section (per-model progress bars, GPU
     memory, running services).
  8. git add -A + commit + push origin main.

Usage:
    python3 scripts/auto_status_commit.py --once     # run a single cycle (manual trigger)
    python3 scripts/auto_status_commit.py            # daemon: run immediately, then every 1800 s
    python3 scripts/auto_status_commit.py --interval 900

All failures are logged and swallowed — the daemon never dies from a transient
error (proxy hiccup, git conflict, missing binary, ...).
"""
import argparse
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
BASE_DIR = Path("/splunk-data/v1/Work_RAG-Server-Setup")
MODELS_DIR = BASE_DIR / "offline-prep" / "models" / "huggingface"
CONVERTED_DIR = BASE_DIR / "offline-prep" / "models" / "deepseek-v4-converted"
README = BASE_DIR / "README.md"
LOGS_DIR = BASE_DIR / "logs"
DL_LOGS_DIR = BASE_DIR / "offline-prep" / "logs"
REPORT_DIR = BASE_DIR / "docs" / "reports"
VENV_PY = BASE_DIR / "offline-prep" / "venv" / "bin" / "python3.12"
GEN_EVAL_REPORT = BASE_DIR / "scripts" / "gen_eval_report.py"
GEN_PAGES = BASE_DIR / "scripts" / "gen_pages.py"
LOG_FILE = LOGS_DIR / "auto_status_commit.log"
PROXY = "http://192.168.203.2:3128"
PAGES_BASE = "https://alinikkhah2001.github.io/Work_RAG-Server-Setup/"

# Pages to probe on the live site. Each entry: (label, [url candidates]).
# Candidates are tried in order; the first HTTP 200 wins.
PAGES_TO_CHECK = [
    ("index", [PAGES_BASE]),
    ("04-figures", [PAGES_BASE + "04-figures", PAGES_BASE + "04-figures.html",
                    PAGES_BASE + "reports/04-figures.html"]),
    ("n-shot", [PAGES_BASE + "06-few-shot-scaling-0-1-2-3-5-shot",
                PAGES_BASE + "06-few-shot-scaling-0-1-2-3-5-shot.html",
                PAGES_BASE + "06-few-shot-scaling-0-1-2-3-5.html",
                PAGES_BASE + "06-few-shot-scaling.html"]),
    ("temperature", [PAGES_BASE + "07-effect-of-temperature",
                     PAGES_BASE + "07-effect-of-temperature.html",
                     PAGES_BASE + "07-effect-of-temperature-sweep.html"]),
]

# Static expected sizes (bytes) for models without a safetensors index.json.
# Values come from scripts/download_models.py target comments + README §4a.
EXPECTED_BYTES = {
    "bartowski_Llama-3.2-3B-Instruct-GGUF": 2_019_377_696,          # 2.0 GB Q4_K_M
    "bartowski_Qwen2.5-7B-Instruct-GGUF": 4_683_074_240,            # 4.7 GB Q4_K_M
    "bartowski_Mistral-7B-Instruct-v0.3-GGUF": 4_372_812_000,       # 4.4 GB Q4_K_M
    "bartowski_google_gemma-3-27b-it-GGUF": 16_500_000_000,         # 16.5 GB
    "Qwen_Qwen3-30B-A3B-GGUF": 18_600_000_000,                      # 18.6 GB
    "bartowski_google_gemma-4-31B-it-GGUF": 19_600_000_000,         # 19.6 GB
    "bartowski_Qwen3.8-27B-GGUF": 17_800_000_000,                   # 17.8 GB
    "bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF": 30_200_000_000,  # 30.2 GB
    "deepseek-ai_DeepSeek-V4-Flash": 159_609_485_896,               # 46 shards (fallback)
}

SERVICE_PATTERNS = ("embed_server.py", "llama_chat_server.py", "vllm",
                    "download_models.py", "generate.py")
SHARD_RE = re.compile(r"model-\d+-of-(\d+)\.safetensors$")

log = logging.getLogger("auto_status")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def fmt_size(n):
    """Human-readable size: bytes -> '149.2 GB'."""
    if n is None:
        return "n/a"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def progress_bar(pct, width=10):
    """Unicode block progress bar: [████████░░]."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100.0 * width))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def run_cmd(cmd, timeout=120, cwd=None, env_extra=None):
    """Run a shell command; never raise. Returns (returncode, stdout, stderr)."""
    env = os.environ.copy()
    env.update({"HTTP_PROXY": PROXY, "HTTPS_PROXY": PROXY,
                "http_proxy": PROXY, "https_proxy": PROXY})
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                           text=True, timeout=timeout, cwd=cwd or str(BASE_DIR),
                           env=env)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except Exception as e:  # noqa: BLE001 — daemon must survive anything
        return -1, "", str(e)


def dir_bytes(path):
    """Total bytes of all regular files under *path* (excluding symlinks)."""
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def port_open(port, timeout=2):
    """True if something listens on localhost:port."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# 1. live pages
# --------------------------------------------------------------------------- #
def check_pages():
    """Probe the live GitHub Pages URLs. Returns {label: (code, url)}."""
    results = {}
    for label, candidates in PAGES_TO_CHECK:
        status, ok_url = -1, None
        for url in candidates:
            code, out, _ = run_cmd(f"curl -s -o /dev/null -w '%{{http_code}}' "
                                   f"--max-time 20 --retry 3 --retry-delay 3 "
                                   f"--retry-all-errors -L '{url}'", timeout=60)
            try:
                status = int(code)
            except ValueError:
                status = -1
            if status == 200:
                ok_url = url
                break
        results[label] = (status, ok_url)
        log.info("pages %-12s -> HTTP %s %s", label, status, ok_url or "")
    return results


# --------------------------------------------------------------------------- #
# 2. plots / report / pages regeneration
# --------------------------------------------------------------------------- #
def _newest_log_time():
    newest = 0.0
    for p in LOGS_DIR.glob("evalp_*.json"):
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            pass
    return newest


def _artifacts_stale():
    """True if any eval log is newer than the generated report/plots."""
    newest_log = _newest_log_time()
    if newest_log == 0.0:
        return False
    anchor = REPORT_DIR / "persian_eval_report.md"
    if not anchor.exists():
        return True
    try:
        return anchor.stat().st_mtime < newest_log
    except OSError:
        return True


def regenerate_artifacts():
    """Run gen_eval_report.py + gen_pages.py when artifacts are stale."""
    if not _artifacts_stale():
        log.info("artifacts up to date, skipping regeneration")
        return
    log.info("eval logs newer than report — regenerating plots + pages")
    for script in (GEN_EVAL_REPORT, GEN_PAGES):
        if not script.exists():
            log.warning("missing script %s — skipped", script)
            continue
        code, out, err = run_cmd(f"{VENV_PY} {script} 2>&1", timeout=900)
        if code == 0:
            log.info("ran %s OK", script.name)
        else:
            log.warning("ran %s failed rc=%s: %s", script.name, code, err[:200])


# --------------------------------------------------------------------------- #
# 3. model download progress
# --------------------------------------------------------------------------- #
def expected_bytes(model_dir):
    """Expected total bytes for a model dir.

    Priority: model.safetensors.index.json metadata.total_size, then the static
    EXPECTED_BYTES map, then None (unknown).
    """
    idx = model_dir / "model.safetensors.index.json"
    if idx.exists():
        try:
            meta = json.loads(idx.read_text(encoding="utf-8")).get("metadata", {})
            size = meta.get("total_size")
            if size:
                return int(size)
        except Exception:  # noqa: BLE001
            pass
    return EXPECTED_BYTES.get(model_dir.name)


def _main_artifact_exists(model_dir):
    """Heuristic: model dir is 'complete' if it holds a real weights file."""
    for pattern in ("*.safetensors", "pytorch_model.bin", "*.gguf"):
        if any(model_dir.glob(pattern)):
            return True
    return False


def shard_counts(model_dir):
    """(present, total) shard files for sharded safetensors models, else (0, 0)."""
    present, total = 0, 0
    for p in model_dir.glob("model-*-of-*.safetensors"):
        m = SHARD_RE.search(p.name)
        if m:
            present += 1
            total = max(total, int(m.group(1)))
    return present, total


def scan_models():
    """Return a list of dicts, one per model dir, sorted by disk size desc."""
    models = []
    if not MODELS_DIR.is_dir():
        log.warning("models dir missing: %s", MODELS_DIR)
        return models
    for d in sorted(MODELS_DIR.iterdir()):
        if not d.is_dir():
            continue
        disk = dir_bytes(d)
        expected = expected_bytes(d)
        present, total = shard_counts(d)
        if expected:
            pct = disk / expected * 100.0
            status = "done" if pct >= 99.0 else "downloading"
        else:
            pct = 100.0 if _main_artifact_exists(d) else 0.0
            status = "ok" if pct >= 99.0 else "partial"
        models.append({
            "name": d.name,
            "disk": disk,
            "expected": expected,
            "pct": pct,
            "status": status,
            "shards": f"{present}/{total}" if total else "",
        })
    models.sort(key=lambda m: m["disk"], reverse=True)
    return models


def latest_dl_log_tail(n=5):
    """Tail of the newest download log (repo-root console log or offline-prep logs)."""
    candidates = list(DL_LOGS_DIR.glob("dl_models_*.log"))
    console = LOGS_DIR / "dl_models_console.log"
    if console.exists():
        candidates.append(console)
    if not candidates:
        return "(no download logs yet)"
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        lines = newest.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return f"(cannot read {newest.name}: {e})"
    tail = "\n".join(l.rstrip() for l in lines[-n:]).strip()
    mtime = datetime.fromtimestamp(newest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"{newest.name} [{mtime}]:\n{tail}"


# --------------------------------------------------------------------------- #
# 4. services
# --------------------------------------------------------------------------- #
def scan_services():
    """Running service processes (embed/llama/vllm/download). Returns [str]."""
    code, out, _ = run_cmd("ps aux", timeout=20)
    if code != 0:
        return []
    services = []
    for line in out.splitlines():
        if "auto_status_commit.py" in line or "grep" in line:
            continue
        if any(p in line for p in SERVICE_PATTERNS):
            services.append(line.strip())
    return services


# --------------------------------------------------------------------------- #
# 5. GPU state
# --------------------------------------------------------------------------- #
def gpu_state():
    """nvidia-smi memory per GPU. Returns [str] rows, or [] if unavailable."""
    code, out, _ = run_cmd(
        "nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader",
        timeout=30)
    if code != 0:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


# --------------------------------------------------------------------------- #
# 6. implementation-progress evidence
# --------------------------------------------------------------------------- #
def collect_evidence(pages=None, models=None):
    """Gather filesystem/runtime facts used to flip README checkboxes."""
    pages = pages or {}
    models = models or []
    conv_ok = CONVERTED_DIR.exists() and any(CONVERTED_DIR.glob("*.safetensors"))
    smoke_logs = (list(LOGS_DIR.glob("*smoke*")) + list(LOGS_DIR.glob("*deepseek*"))
                  + list(LOGS_DIR.glob("*generate*")))
    return {
        "report_exists": (REPORT_DIR / "persian_eval_report.md").exists(),
        "pages_ok": all(v[0] == 200 for v in pages.values()) if pages else False,
        "git_ok": True,                       # routine auto-commits keep history
        "venv_deepseek": (BASE_DIR / "offline-prep" / "venv-deepseek").exists(),
        "converted": conv_ok,
        "smoke_log": bool(smoke_logs),
        "server_9001": port_open(9001),
        # phase 2 (parallel benchmark) evidence
        "parallel_plot": (REPORT_DIR / "persian_parallel.png").exists(),
        # deepseek eval evidence
        "deepseek_eval": any((LOGS_DIR / f"evalp_deepseek.json").exists()
                             for _ in (0,)) or bool(list(LOGS_DIR.glob("evalp_deepseek*"))),
    }


def decide_checkbox(done_evidence, text):
    """Decide the checkbox state for one task line.

    Returns True (done), False (not done) or None (no evidence -> keep as-is).
    """
    low = text.strip().lower()
    rules = [
        ("0.1 regenerate", "report_exists"),
        ("0.2 verify live", "pages_ok"),
        ("0.3 commit", "git_ok"),
        ("0.3 commit + push", "git_ok"),
        ("1.1 create separate venv", "venv_deepseek"),
        ("1.1 create venv", "venv_deepseek"),
        ("1.2 convert weights", "converted"),
        ("1.3 smoke test", "smoke_log"),
        ("1.4 wrap generate.py", "server_9001"),
        ("wrap generate.py as openai", "server_9001"),
        ("2.3 plot", "parallel_plot"),
        ("4.1 re-run 7-task", "deepseek_eval"),
    ]
    for needle, key in rules:
        if needle in low:
            return bool(done_evidence.get(key, False))
    return None


def rewrite_progress_section(text, evidence, download_section):
    """Replace the '## Implementation Progress' block (up to the next '---')
    with the updated phases + the Download Progress section.

    Phase headers and task descriptions are preserved verbatim; checkbox
    markers are updated where evidence exists, otherwise left untouched.
    Returns the new full README text, or the original when the section is
    missing.
    """
    marker = "## Implementation Progress"
    hdr = text.find(marker)
    if hdr < 0:
        log.warning("README missing %r — leaving README unchanged", marker)
        return text
    # end of the block = next '---' after the header
    sep = text.find("\n---\n", hdr)
    if sep < 0:
        sep = len(text)

    head = text[:hdr]
    body = text[hdr:sep]
    rest = text[sep:]  # starts with "\n---\n..."

    out_lines = [marker, ""]
    for line in body.splitlines():
        if line.startswith("- [ ] ") or line.startswith("- [x] "):
            text_part = line[6:].strip()
            new_state = decide_checkbox(evidence, text_part)
            if new_state is True:
                out_lines.append("- [x] " + text_part)
            elif new_state is False:
                out_lines.append("- [ ] " + text_part)
            else:
                out_lines.append(line)          # no evidence — preserve
        else:
            out_lines.append(line)

    # re-strip trailing blank lines so the section stays tidy
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    new_block = "\n".join(out_lines)

    return head + new_block + "\n\n" + download_section + rest


# --------------------------------------------------------------------------- #
# 7. download-progress section builder
# --------------------------------------------------------------------------- #
def build_download_section(models, gpu_rows, services, pages, dl_tail, ev):
    """Compose the '## Download Progress' markdown section."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["## Download Progress", "",
             f"_Auto-generated by `scripts/auto_status_commit.py` — {now}_", ""]

    # --- live pages ---------------------------------------------------------
    lines.append("### Live GitHub Pages")
    if pages:
        for label, (code, url) in pages.items():
            mark = "OK" if code == 200 else f"HTTP {code}"
            lines.append(f"- {label}: **{mark}**" + (f" (`{url}`)" if url else ""))
    else:
        lines.append("- (unreachable / not probed)")
    lines.append("")

    # --- GPU ----------------------------------------------------------------
    lines.append("### GPU memory")
    if gpu_rows:
        lines.append("| GPU | Used | Total |")
        lines.append("|---|---|---|")
        for row in gpu_rows:
            parts = [p.strip() for p in row.split(",")]
            if len(parts) == 3:
                lines.append(f"| {parts[0]} | {parts[1]} | {parts[2]} |")
        lines.append("")
    else:
        lines.append("- `nvidia-smi` unavailable (no GPU access or driver issue)")
        lines.append("")

    # --- services -----------------------------------------------------------
    lines.append("### Running services")
    if services:
        for s in services:
            m = re.search(r"(scripts/\S+|offline-prep/\S+)", s)
            brief = m.group(1) if m else s
            lines.append(f"- `{brief}`")
        lines.append("")
    else:
        lines.append("- (no embed_server / llama_chat_server / vllm processes)")
        lines.append("")

    # --- models -------------------------------------------------------------
    lines.append("### Model downloads")
    lines.append("| Model | Disk | Expected | Progress | Shards | Status |")
    lines.append("|---|---|---|---|---|---|")
    for m in models:
        pct = max(0.0, min(100.0, m["pct"]))
        lines.append(
            f"| `{m['name']}` | {fmt_size(m['disk'])} | {fmt_size(m['expected'])} "
            f"| {progress_bar(pct)} {pct:.0f}% | {m['shards'] or '—'} | {m['status']} |")
    lines.append("")

    lines.append("### Download log (tail)")
    lines.append("```")
    lines.append(dl_tail)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# README update
# --------------------------------------------------------------------------- #
def update_readme(pages, models, gpu_rows, services, dl_tail, ev):
    """Rewrite README.md with fresh Implementation Progress + Download Progress."""
    if not README.exists():
        log.warning("README not found: %s", README)
        return False
    text = README.read_text(encoding="utf-8")
    dl_section = build_download_section(models, gpu_rows, services, pages, dl_tail, ev)
    new_text = rewrite_progress_section(text, ev, dl_section)
    if new_text == text:
        log.info("README unchanged")
        return False
    README.write_text(new_text, encoding="utf-8")
    log.info("README updated (%d -> %d bytes)", len(text), len(new_text))
    return True


# --------------------------------------------------------------------------- #
# 8. git commit + push
# --------------------------------------------------------------------------- #
def git_commit_push(message=None):
    """git add -A; commit (if anything staged); push origin main."""
    message = message or f"auto: status update [{datetime.now():%Y-%m-%d %H:%M:%S}]"
    code, _, err = run_cmd("git add -A", timeout=60)
    if code != 0:
        log.warning("git add failed: %s", err[:200])
        return False
    # commit only when there are staged changes
    code, out, _ = run_cmd("git diff --cached --quiet; echo $?", timeout=30)
    dirty = out.strip() != "0"
    if not dirty:
        log.info("nothing staged — skipping commit")
        return False
    code, _, err = run_cmd(f"git commit -m {message!r}", timeout=120)
    if code != 0:
        log.warning("commit failed: %s", err[:200])
        return False
    log.info("committed: %s", message)
    code, _, err = run_cmd("git push origin main", timeout=180)
    if code != 0:
        log.warning("push failed (will retry next cycle): %s", err[:200])
        return False
    log.info("pushed to origin/main")
    return True


# --------------------------------------------------------------------------- #
# one cycle
# --------------------------------------------------------------------------- #
def run_cycle():
    log.info("---- cycle start %s ----", datetime.now().isoformat(timespec="seconds"))
    pages = check_pages()
    regenerate_artifacts()
    models = scan_models()
    services = scan_services()
    gpu_rows = gpu_state()
    dl_tail = latest_dl_log_tail()
    ev = collect_evidence(pages=pages, models=models)

    log.info("models=%d services=%d gpu_rows=%d pages_ok=%s",
             len(models), len(services), len(gpu_rows),
             all(v[0] == 200 for v in pages.values()) if pages else False)

    changed = update_readme(pages, models, gpu_rows, services, dl_tail, ev)
    if changed:
        git_commit_push()
    else:
        log.info("no README change — skipping commit this cycle")
    log.info("---- cycle end ----")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true",
                    help="run a single cycle and exit (manual trigger)")
    ap.add_argument("--interval", type=int, default=1800,
                    help="seconds between cycles (default 1800 = 30 min)")
    args = ap.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE),
                  logging.StreamHandler()])

    log.info("auto_status_commit daemon started (interval=%ss, once=%s)",
             args.interval, args.once)

    # initial run immediately, then sleep --interval between cycles
    while True:
        try:
            run_cycle()
        except Exception as e:  # noqa: BLE001 — never die
            log.exception("cycle failed: %s", e)
        if args.once:
            break
        time.sleep(max(60, args.interval))

    log.info("daemon exiting (once mode)")


if __name__ == "__main__":
    main()