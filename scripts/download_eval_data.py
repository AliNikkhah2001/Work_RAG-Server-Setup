#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download eval datasets + Persian/multilingual embedding models through the Squid proxy.

Datasets are cached to offline-prep/datasets via the datasets library cache.
Embedding models go to offline-prep/models/huggingface/<repo_with_underscores>.
"""
import os
from pathlib import Path

PROXY = "http://192.168.203.2:3128"
os.environ.update({"HTTP_PROXY": PROXY, "HTTPS_PROXY": PROXY,
                   "http_proxy": PROXY, "https_proxy": PROXY,
                   "HF_HUB_DISABLE_XET": "1", "HF_HUB_ENABLE_HF_TRANSFER": "0"})

BASE = Path("/splunk-data/v1/Work_RAG-Server-Setup/offline-prep")
MODELS_DIR = BASE / "models" / "huggingface"

CONVENTIONAL_DATASETS = [
    ("openai/gsm8k", "main"),                     # arithmetic reasoning (en)
    ("cais/mmlu", "abstract_algebra"),            # knowledge MC (en, 1 subject for speed)
    ("cais/mmlu", "computer_security"),
    ("cais/mmlu", "high_school_mathematics"),
    ("allenai/arc-easy", None),                   # commonsense reasoning (en)
]

PERSIAN_DATASETS = [
    ("community-datasets/parsinlu_reading_comprehension", None),  # reading comp (fa)
    ("MatinaAI/persian_arc", "ARC-Easy"),         # commonsense reasoning (fa)
]

# Multilingual / Persian-capable embedding models (SentenceTransformer format)
EMBEDDING_MODELS = [
    "intfloat/multilingual-e5-small",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "BAAI/bge-m3",
]


def main():
    from datasets import load_dataset
    from huggingface_hub import snapshot_download

    print("=== conventional datasets ===")
    for name, cfg in CONVENTIONAL_DATASETS:
        try:
            d = load_dataset(name, cfg)
            print("OK", name, cfg, {k: len(v) for k, v in d.items()})
        except Exception as e:
            print("ERR", name, cfg, str(e)[:160])

    print("=== persian datasets ===")
    for name, cfg in PERSIAN_DATASETS:
        try:
            d = load_dataset(name, cfg)
            print("OK", name, cfg, {k: len(v) for k, v in d.items()})
        except Exception as e:
            print("ERR", name, cfg, str(e)[:160])

    print("=== embedding models ===")
    for repo in EMBEDDING_MODELS:
        dest = MODELS_DIR / repo.replace("/", "_")
        try:
            snapshot_download(repo_id=repo, local_dir=str(dest),
                              proxies={"http": PROXY, "https": PROXY}, max_workers=2)
            print("OK", repo)
        except Exception as e:
            print("ERR", repo, str(e)[:160])


if __name__ == "__main__":
    main()