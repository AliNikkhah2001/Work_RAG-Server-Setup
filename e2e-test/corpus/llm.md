# LLM Inference Optimization

LLM inference is memory-bandwidth bound: generating one token reads the entire model weights.
KV cache stores past key/value tensors, growing linearly with sequence length. Techniques to
reduce memory: quantization (INT8/INT4, e.g., AWQ, GPTQ), speculative decoding (draft model +
verification), continuous batching in vLLM, and prefix caching. GQA (Grouped Query Attention)
reduces KV cache by sharing key/value heads. Context window limits total tokens; 4K context
means roughly 3000 tokens of prompt plus generated text. Temperature controls randomness:
lower = more deterministic.
