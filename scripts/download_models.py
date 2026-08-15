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

    # === Added 2026-08-15: frontier MoE + multilingual catalog ===
    # Qwen3-30B-A3B (MoE 30.5B/3.3B act, 18.6 GB Q4_K_M): strong multilingual;
    #    runs in llama.cpp qwen3moe + vLLM. (user ref: "Qwen/Qwen3.8-27B")
    ("Qwen/Qwen3-30B-A3B-GGUF",
     ["Qwen3-30B-A3B-Q4_K_M.gguf"]),
    # Gemma-3-27B it (multimodal-capable chat, 16.5 GB Q4_K_M) - GATED repo:
    #    requires HF_TOKEN (huggingface login) or download returns 401.
    ("bartowski/google_gemma-3-27b-it-GGUF",
     ["google_gemma-3-27b-it-Q4_K_M.gguf"]),
    # NVIDIA Nemotron Super-49B (Llama-3.3 base, reasoning/RAG, 30.2 GB Q4_K_M)
    ("bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF",
     ["*Nemotron-Super-49B-v1-Q4_K_M.gguf"]),
    # NVIDIA Nemotron Ultra-253B (Llama-3.1 base, 151 GB Q4_K_M, multi-part split)
    ("bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF",
     ["*Nemotron-Ultra-253B-v1-Q4_K_M*"]),
    # MiniMax-M3 (MoE ~428B/23B act, 208 GB UD-IQ4_XS) - needs llama.cpp PR #24523 to run
    ("unsloth/MiniMax-M3-GGUF",
     ["UD-IQ4_XS/*"]),
    # GLM-5.2 (MoE 744B/40B act, official FP8 755 GB) - needs vLLM >= 0.23 or recent llama.cpp
    ("zai-org/GLM-5.2-FP8",
     ["*.safetensors", "*.json", "*.py", "tokenizer*", "*.md", "*.txt"]),
    # Kimi K3 (MoE 2.8T/104B act, 594 GB UD-IQ1_S) - needs unsloth llama.cpp fork (kimi-k3)
    ("unsloth/Kimi-K3-GGUF",
     ["UD-IQ1_S/*"]),
    # DeepSeek-V4-Flash (MoE 284B/13B act, FP4+FP8 native, 160 GB safetensors) - serving needs new vLLM
    ("deepseek-ai/DeepSeek-V4-Flash",
     ["model-*.safetensors", "*.json", "*.py", "tokenizer*", "*.md", "*.txt"]),
]

MAX_ATTEMPTS = 8
RETRY_WAIT = 90


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
                    break
                except Exception as e:
                    msg = str(e)
                    if any(k in msg.lower() for k in ("401", "403", "gated", "authentication")):
                        log.error(f"AUTH-BLOCKED {repo} (token/log-gated, no HF_TOKEN): {msg[:160]}")
                        break  # do not infinite-loop on gated repos; needs HF_TOKEN
                    log.warning(f"FAIL {repo} attempt={attempt}: {msg[:200]}")
                    if max_attempts is not None and attempt >= max_attempts:
                        break
                    time.sleep(RETRY_WAIT)
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
