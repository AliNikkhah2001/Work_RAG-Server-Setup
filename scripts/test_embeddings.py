#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare embedding models on a small Persian retrieval benchmark.

Each query has a target doc; we embed corpus+queries and check whether the
target is the top-1 and what the top-1 cosine score is.
"""
import json
import time

import requests

BASE = [
    "سرویس RAG سازمانی بر روی دو کارت گرافیک NVIDIA H200 با حافظه 143 گیگابایت اجرا می‌شود.",
    "مدل تولید پاسخ پیش‌فرض Gemma-4-31B است که از طریق llama.cpp سرو می‌شود.",
    "پایگاه‌های برداری موجود عبارتند از: Milvus، Qdrant و pgvector.",
    "ترافیک خروجی از طریق پروکسی Squid در آدرس 192.168.203.2:3128 عبور می‌کند.",
    "مدل embedding چندزبانه multilingual-e5-small بردارهای 384 بعدی تولید می‌کند.",
    "سرویس LightRAG روی پورت 9621 اجرا شده و به مدل زبانی و embedding متصل است.",
]

QUERIES = [
    ("کدام کارت‌های گرافیکی در سرویس استفاده می‌شوند؟", 0),
    ("مدل تولید پاسخ چیست؟", 1),
    ("چه پایگاه‌های برداری در دسترس هستند؟", 2),
    ("آدرس پروکسی خروجی چیست؟", 3),
    ("embedding چه ابعادی دارد؟", 4),
    ("سرویس LightRAG روی کدام پورت است؟", 5),
]


def embed(port, text):
    r = requests.post(f"http://localhost:{port}/v1/embeddings",
                      json={"input": text}, timeout=30)
    return r.json()["data"][0]["embedding"]


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def run(port, label):
    t0 = time.time()
    docs = [embed(port, d) for d in BASE]
    q_emb = [embed(port, q) for q, _ in QUERIES]
    hits = 0
    top1_score = 0.0
    per_q = []
    for i, (q, target) in enumerate(QUERIES):
        sims = [cosine(q_emb[i], d) for d in docs]
        ranked = sorted(range(len(docs)), key=lambda j: sims[j], reverse=True)
        hit = ranked[0] == target
        hits += int(hit)
        top1_score += sims[ranked[0]]
        per_q.append({"q": q[:40], "target": target, "top1": ranked[0], "hit": hit,
                      "score": round(sims[ranked[0]], 4)})
    secs = time.time() - t0
    print(json.dumps({"embedder": label, "port": port, "top1_acc": hits / len(QUERIES),
                      "mean_top1_score": round(top1_score / len(QUERIES), 4),
                      "secs": round(secs, 2), "per_q": per_q}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    run(8001, "multilingual-e5-small (384d)")
    run(8002, "bge-m3 (1024d)")
    run(8003, "paraphrase-multilingual-MiniLM-L12-v2 (384d)")