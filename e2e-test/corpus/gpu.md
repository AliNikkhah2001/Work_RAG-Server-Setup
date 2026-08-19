# NVIDIA GPU Architecture

NVIDIA H100 has 132 SMs, 80 GB HBM3 memory at 3.35 TB/s bandwidth, and FP8 tensor core support.
The H200 doubles memory to 141 GB HBM3e. CUDA Cores execute FP32; Tensor Cores accelerate
matrix multiply for FP16/BF16/FP8. VRAM is managed via CUDA contexts; `nvidia-smi` shows
per-process memory. FlashAttention avoids materializing the full attention matrix, cutting
memory from O(N^2) to O(N). vLLM uses PagedAttention to achieve near-zero KV-cache waste.
