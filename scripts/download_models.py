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

TARGETS = [
    ("bartowski/Qwen2.5-7B-Instruct-GGUF",
     ["Qwen2.5-7B-Instruct-Q4_K_M.gguf"]),
    ("bartowski/Llama-3.2-3B-Instruct-GGUF",
     ["Llama-3.2-3B-Instruct-Q4_K_M.gguf"]),
    ("bartowski/Mistral-7B-Instruct-v0.3-GGUF",
     ["Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"]),
    # Large Persian-capable models (Qwen2.5-72B is a strong multilingual model)
    #   1) Q4_K_M single-file  ~49 GB  -> works in BOTH llama.cpp and vLLM
    #   2) Q8_0 (2 parts)      ~93 GB  -> llama.cpp only (splits not supported by vLLM)
    ("bartowski/Qwen2.5-72B-Instruct-GGUF",
     ["Qwen2.5-72B-Instruct-Q4_K_M.gguf",
      "Qwen2.5-72B-Instruct-Q8_0/Qwen2.5-72B-Instruct-Q8_0-00001-of-00002.gguf",
      "Qwen2.5-72B-Instruct-Q8_0/Qwen2.5-72B-Instruct-Q8_0-00002-of-00002.gguf"]),
]

MAX_ATTEMPTS = 8
RETRY_WAIT = 90


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="download only this repo id (by substring match)")
    args = ap.parse_args()

    targets = TARGETS
    if args.only:
        targets = [(r, p) for r, p in TARGETS if args.only in r]
        if not targets:
            print(f"No targets match {args.only}")
            return

    log = logging.getLogger("dl")
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_DIR / f"dl_models_{datetime.now():%Y%m%d_%H%M}.log")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(fh)

    from huggingface_hub import snapshot_download

    for repo, patterns in targets:
        dest = MODELS_DIR / repo.replace("/", "_")
        dest.mkdir(parents=True, exist_ok=True)
        log.info(f"START {repo} -> {dest}  patterns={patterns}")
        ok = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
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
                break
            except Exception as e:
                log.warning(f"FAIL {repo} attempt={attempt}: {str(e)[:200]}")
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_WAIT)
        if not ok:
            log.error(f"GIVEUP {repo} after {MAX_ATTEMPTS} attempts")
    log.info("ALL DONE")


if __name__ == "__main__":
    main()
