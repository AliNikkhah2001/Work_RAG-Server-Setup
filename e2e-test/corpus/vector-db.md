# Vector Databases Compared

Milvus uses segmented storage with HNSW and IVF indexes; it separates storage (object store)
from compute (query nodes). Qdrant is written in Rust, supports payload filtering, and uses
HNSW with a quantized payload. pgvector extends PostgreSQL with `vector` type and HNSW/IVFFlat
indexes; it supports exact kNN via sequential scan. Redis Stack adds VSS (vector similarity
search) with FLAT and HNSW. FAISS is a library, not a server. hnswlib parameters: M=16,
efConstruction=200, efSearch varies at query time.
