# Retrieval-Augmented Generation (RAG)

RAG combines an information retrieval system with a large language model. Documents are split
into chunks, embedded into vectors, and stored in a vector database. At query time, the query is
embedded and approximate nearest neighbor search (e.g., HNSW) retrieves the top-k chunks. Those
chunks are injected into the LLM prompt as context. Chunk size typically ranges 300-800 tokens;
chunk overlap of 10-20% improves boundary recall. Reranking models can reorder retrieved chunks
by semantic relevance. Evaluation metrics include hit rate, MRR, and faithfulness.
