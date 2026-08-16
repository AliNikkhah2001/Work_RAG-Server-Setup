#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download the bigger Persian eval datasets (ParsBench suite + Persian-MMLU) into
the datasets cache, with retries. Handles legacy script-based datasets and
caches them as parquet in ~/.cache/huggingface/datasets."""
import os
import time
import logging
from datetime import datetime
from pathlib import Path

PROXY = "http://192.168.203.2:3128"
os.environ.update({"HTTP_PROXY": PROXY, "HTTPS_PROXY": PROXY,
                   "http_proxy": PROXY, "https_proxy": PROXY,
                   "HF_HUB_DISABLE_XET": "1", "HF_HUB_ENABLE_HF_TRANSFER": "0"})

BASE = Path("/splunk-data/v1/Work_RAG-Server-Setup/offline-prep")

DATASETS = [
    # ParsBench suite (Persian LLM eval, alpaca-style rows: instruction/input/output)
    ("ParsBench/parsinlu-multiple-choice-alpaca-style", None),
    ("ParsBench/persian-math-alpaca-style", None),
    ("ParsBench/persian-ner-alpaca-style", None),
    ("ParsBench/pnsummary-alpaca-style", None),
    ("ParsBench/farstail-entailment-alpaca-style", None),
    ("ParsBench/persian-conjnli-entailment-alpaca-style", None),
    ("ParsBench/parsinlu-entailment-alpaca-style", None),
    ("ParsBench/parsinlu-sentiment-analysis-alpaca-style", None),
    ("ParsBench/parsinlu-reading-comprehension-alpaca-style", None),
    # NB: parsinlu-machine-translation-en-fa is a ~1GB JSONL that fails pyarrow
    # generation ("block_size ... too large to convert to int32_t") — excluded.
    # Persian MMLU
    ("Mohammadreza/persian-mmlu-categorized", None),
]


def main():
    from datasets import load_dataset
    log = logging.getLogger("peval")
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(BASE / "logs" / f"dl_persian_eval_{datetime.now():%Y%m%d_%H%M}.log")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(fh)

    for name, cfg in DATASETS:
        attempt = 0
        while True:
            attempt += 1
            log.info(f"START {name} cfg={cfg} attempt={attempt}")
            try:
                d = load_dataset(name, cfg)
                s = next(iter(d.values()))
                log.info(f"OK {name} sizes={ {k: len(v) for k, v in d.items()} } cols={list(s[0].keys())}")
                break
            except Exception as e:
                log.warning(f"FAIL {name} attempt={attempt}: {str(e)[:160]}")
                time.sleep(60)


if __name__ == "__main__":
    main()