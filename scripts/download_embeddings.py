#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resilient download of multilingual/Persian embedding models (SentenceTransformer).
Skips onnx/openvino dirs; retries until complete."""
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
MODELS_DIR = BASE / "models" / "huggingface"
LOG_DIR = BASE / "logs"

EMBEDDING_MODELS = [
    "intfloat/multilingual-e5-small",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "BAAI/bge-m3",
]

# only files SentenceTransformer actually loads at runtime
ALLOW = ["model.safetensors", "pytorch_model.bin", "config.json", "tokenizer*",
         "sentence_bert_config.json", "modules.json", "1_Pooling/*",
         "special_tokens_map.json", "vocab*", "spiece.model", "*.model",
         "generation_config.json", "added_tokens.json", "tokenizer_config.json",
         "sentencepiece.bpe.model", "merges.txt", "README.md"]


def main():
    from huggingface_hub import snapshot_download

    log = logging.getLogger("emb")
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_DIR / f"dl_emb_{datetime.now():%Y%m%d_%H%M}.log")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(fh)

    for repo in EMBEDDING_MODELS:
        dest = MODELS_DIR / repo.replace("/", "_")
        dest.mkdir(parents=True, exist_ok=True)
        attempt = 0
        while True:
            attempt += 1
            log.info(f"START {repo} attempt={attempt}")
            try:
                snapshot_download(repo_id=repo, local_dir=str(dest),
                                  allow_patterns=ALLOW,
                                  proxies={"http": PROXY, "https": PROXY},
                                  max_workers=2)
                log.info(f"OK {repo}")
                break
            except Exception as e:
                log.warning(f"FAIL {repo} attempt={attempt}: {str(e)[:160]}")
                time.sleep(60)


if __name__ == "__main__":
    main()