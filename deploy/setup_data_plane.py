#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the RAG vector collections across all vector stores.

- Milvus  : rag_docs collection, dim 384, COSINE   (localhost:19530)
- Qdrant  : rag_docs collection, dim 384, Cosine   (localhost:16333)
- pgvector: rag_docs table + embedding vector(384) (localhost:15432)

Idempotent: existing collections/tables are reused.
"""
import json

DIM = 384

results = {}


def setup_milvus():
    from pymilvus import connections, utility, Collection, CollectionSchema, FieldSchema, DataType
    connections.connect(alias="default", host="127.0.0.1", port="19530")
    if utility.has_collection("rag_docs"):
        return "exists"
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    schema = CollectionSchema(fields, description="RAG docs")
    Collection(name="rag_docs", schema=schema).create_index(
        "embedding", {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}})
    return "created"


def setup_qdrant():
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance
    client = QdrantClient(host="127.0.0.1", port=16333)
    if client.collection_exists("rag_docs"):
        return "exists"
    client.create_collection("rag_docs", vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
    return "created"


def setup_pgvector():
    import psycopg2
    conn = psycopg2.connect(host="127.0.0.1", port=15432, user="postgres",
                            password="testpass", dbname="postgres", connect_timeout=5)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS rag_docs ("
            "id BIGSERIAL PRIMARY KEY, content TEXT, embedding vector(%s))" % DIM)
    conn.close()
    return "created"


def main():
    for name, fn in [("milvus", setup_milvus), ("qdrant", setup_qdrant), ("pgvector", setup_pgvector)]:
        try:
            results[name] = fn()
            print(f"  {name:<9} OK  ({results[name]})")
        except Exception as e:
            results[name] = f"FAIL: {str(e)[:100]}"
            print(f"  {name:<9} FAIL  {str(e)[:100]}")
    with open("deploy/data_plane_status.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
