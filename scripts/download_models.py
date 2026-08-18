#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proxy-resilient HuggingFace model downloader.

Disables the XET backend (which fails through the Squid proxy) and downloads
targeted quant files with retries + resume into offline-prep/models/huggingface.
"""
import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

PROXY = "http://192.168.203.2:3128"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ.update({"HTTP_PROXY": PROXY, "HTTPS_PROXY": PROXY,
                   "http_proxy": PROXY, "https_proxy": PROXY})

BASE = Path("/splunk-data/v1/Work_RAG-Server-Setup/offline-prep")
MODELS_DIR = BASE / "models" / "huggingface"
LOG_DIR = BASE / "logs"

# NOTE: the daemon ("--daemon", systemd rag-dl.service) walks TARGETS strictly top-to-bottom,
# ONE FILE at a time (each entry = a single logical file/quant), resuming any partials.
# Entries are ordered SMALLEST-FIRST by target size so quick wins land first.
TARGETS = [
    # --- already complete on disk -> instantly verified/skipped ---
    ("bartowski/Llama-3.2-3B-Instruct-GGUF",
     ["Llama-3.2-3B-Instruct-Q4_K_M.gguf"]),                                    #  2.0 GB done
    ("bartowski/Qwen2.5-7B-Instruct-GGUF",
     ["Qwen2.5-7B-Instruct-Q4_K_M.gguf"]),                                       #  4.7 GB done

    # --- pending queue (smallest first) ---
    ("bartowski/Mistral-7B-Instruct-v0.3-GGUF",
     ["Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"]),                                  #  4.4 GB
    ("bartowski/google_gemma-3-27b-it-GGUF",
     ["google_gemma-3-27b-it-Q4_K_M.gguf"]),                                     # 16.5 GB (gated)
    ("Qwen/Qwen3-30B-A3B-GGUF",
     ["Qwen3-30B-A3B-Q4_K_M.gguf"]),                                             # 18.6 GB
    ("bartowski/google_gemma-4-31B-it-GGUF",
     ["google_gemma-4-31B-it-Q4_K_M.gguf"]),                                     # 19.6 GB (gated)
    ("bartowski/Qwen3.8-27B-GGUF",
     ["Qwen3.8-27B-Q4_K_M.gguf"]),                                               # 17.8 GB (multimodal; bartowski quants incl. mmproj)
    ("bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF",
     ["*Nemotron-Super-49B-v1-Q4_K_M.gguf"]),                                    # 30.2 GB  (Nemotron 3 / Super)

    # --- resumed 2026-08-18: DeepSeek-V4-Flash (was excluded 2026-08-17 by >100GB
    # policy; partial 25/46 shards on disk — resume keeps completed shards) ---
    ("deepseek-ai/DeepSeek-V4-Flash",
     ["model-*.safetensors", "model.safetensors.index.json", "tokenizer*.json",
      "config.json", "generation_config.json", "README.md", "LICENSE"]),         # ~160 GB total
]

# EXCLUDED (>100 GB download size, policy 2026-08-17; DeepSeek-V4-Flash RE-INCLUDED 2026-08-18):
#   unsloth/MiniMax-M3-GGUF         ~208 GB  GGUF UD-IQ4_XS
#   unsloth/Kimi-K3-GGUF            ~594 GB  GGUF UD-IQ1_S
#   zai-org/GLM-5.2-FP8             ~755 GB  safetensors (FP8)
# (These three stay in the README as "excluded — >100 GB" reference entries.)

MAX_ATTEMPTS = 8
RETRY_WAIT = 90
BACKOFF_BASE = 90          # seconds before first brake
BACKOFF_MULT = 2.0         # exponential multiplier
BACKOFF_CAP = 3600         # max brake (1h) — never hammers the proxy forever
BACKOFF_JITTER = 0.3       # ±30% jitter


def backoff_wait(n_fail: int) -> float:
    """Exponential backoff (brake) with jitter: as failures accumulate, wait
    grows base*mult^(n_fail-1), capped, ±jitter. Never gives up."""
    import random
    base = BACKOFF_BASE * (BACKOFF_MULT ** (n_fail - 1))
    base = min(base, BACKOFF_CAP)
    jitter = random.uniform(1 - BACKOFF_JITTER, 1 + BACKOFF_JITTER)
    return base * jitter


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="download only this repo id (by substring match)")
    ap.add_argument("--daemon", action="store_true",
                    help="never give up: infinite retries + resume, auto-continue across failures/interrupts")
    args = ap.parse_args()

    targets = TARGETS
    if args.only:
        targets = [(r, p) for r, p in TARGETS if args.only in r]
        if not targets:
            print(f"No targets match {args.only}")
            return

    max_attempts = None if args.daemon else MAX_ATTEMPTS

    log = logging.getLogger("dl")
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_DIR / f"dl_models_{datetime.now():%Y%m%d_%H%M}.log")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(fh)

    from huggingface_hub import snapshot_download

    while True:  # outer guard: even a hard crash inside a target restarts it (used with systemd Restart=always)
        all_done = True
        for repo, patterns in targets:
            dest = MODELS_DIR / repo.replace("/", "_")
            dest.mkdir(parents=True, exist_ok=True)
            log.info(f"START {repo} -> {dest}  patterns={patterns}")
            ok = False
            attempt = 0
            consec_fails = 0
            while max_attempts is None or attempt < max_attempts:
                attempt += 1
                try:
                    snapshot_download(
                        repo_id=repo,
                        local_dir=str(dest),
                        allow_patterns=patterns,
                        proxies={"http": PROXY, "https": PROXY},
                        max_workers=2,
                    )
                    log.info(f"OK {repo} attempt={attempt}")
                    ok = True
                    consec_fails = 0
                    break
                except Exception as e:
                    msg = str(e)
                    # only genuine gating/401/403 → stop for this repo; do NOT treat
                    # proxy noise (IncompleteRead, Tunnel 500/503, Kerio pages) as auth.
                    if any(k in msg.lower() for k in ("401 client", "403 client",
                                                      "cannot access gated", "gated repo",
                                                      "not granted access", "access to model")):
                        log.error(f"AUTH-BLOCKED {repo} (token/log-gated, no HF_TOKEN): {msg[:160]}")
                        break  # do not infinite-loop on gated repos; needs HF_TOKEN
                    consec_fails += 1
                    brake = backoff_wait(consec_fails)
                    log.warning(f"FAIL {repo} attempt={attempt} consec={consec_fails} "
                                f"brake={brake:.0f}s: {msg[:180]}")
                    if max_attempts is not None and attempt >= max_attempts:
                        break
                    time.sleep(brake)
            if not ok and not args.daemon:
                log.error(f"GIVEUP {repo} after {max_attempts} attempts")
            all_done = all_done and ok
        if not args.daemon or (all_done and args.daemon):
            if args.daemon and all_done:
                log.info("ALL TARGETS OK — sleeping before re-verify pass")
                time.sleep(600)
                continue
            break
    log.info("ALL DONE")


if __name__ == "__main__":
    main()
