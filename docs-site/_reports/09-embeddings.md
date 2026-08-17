---
title: "Embedding model comparison (Persian retrieval)"
nav_order: 9
---

## 4d. Embedding model comparison (Persian retrieval)

A 6-document Persian retrieval benchmark (`scripts/test_embeddings.py`) checks top-1 retrieval for 6 queries across three locally-served embedders. All reach top-1 correctness; scores differ in **confidence margin** (cosine of the retrieved doc):

| Embedder | Dim | Top-1 acc | Mean top-1 cosine | Batch latency |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | 384 | 1.0 | **0.898** | 0.14 s |
| `BAAI/bge-m3` | 1024 | 1.0 | 0.646 | 0.27 s |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 1.0 | 0.555 | 0.09 s |

**Takeaway:** all three embedders retrieve the correct Persian document; `multilingual-e5-small` gives the widest separation between correct/incorrect docs (highest cosine), while `paraphrase-multilingual-MiniLM` is fastest. `bge-m3` (1024-dim, strongest multilingual coverage) is the safe choice when corpus similarity is low. Embedders are served OpenAI-compatible on `:8001` (e5-small), `:8002` (bge-m3), `:8003` (paraphrase-multilingual).

---

