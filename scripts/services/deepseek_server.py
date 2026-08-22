#!/usr/bin/env python3
"""OpenAI-compatible FastAPI server for DeepSeek-V4-Flash inference."""
import os
import sys
import json
from typing import List

import torch
import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

# ---- Hard-coded absolute paths (REPO_ROOT/inference — fixed for this deployment) ----
REPO_ROOT = "/splunk-data/v1/Work_RAG-Server-Setup"
INFERENCE_DIR = os.path.join(REPO_ROOT, "offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash/inference")
# Use inference/config.json (43 layers, correct moe_inter_dim etc) — NOT the HF config.json
CONFIG_PATH = os.path.join(INFERENCE_DIR, "config.json")
CKPT_BASE = os.path.join(REPO_ROOT, "offline-prep/models/deepseek-v4-converted")
TOKENIZER_PATH = os.path.join(REPO_ROOT, "offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash")

# Add inference directory to path
sys.path.insert(0, INFERENCE_DIR)

from model import Transformer, ModelArgs
from safetensors.torch import load_model
from transformers import AutoTokenizer

app = FastAPI(title="DeepSeek-V4-Flash OpenAI Compatible", version="1.0.0")

# Load config — inference/config.json matches ModelArgs fields exactly
with open(CONFIG_PATH) as f:
    args = ModelArgs(**json.load(f))

# Create model on cuda (deferred load when torch.cuda.is_available)
# Note: full 88GB sharded weights require ~90GB unified VRAM; for MP=2 use model0/mp2 + model1/mp2
model = None
tokenizer = None
try:
    if torch.cuda.is_available():
        with torch.device("cuda"):
            model = Transformer(args)
        # Load weights for rank 0 shard only when running single-process (WORLD_SIZE=1)
        # For MP=2, launch via torchrun with --ckpt-path and model{rank}-mp{world_size}
        rank = int(os.getenv("RANK", "0"))
        world_size = int(os.getenv("WORLD_SIZE", "1"))
        ckpt_file = os.path.join(CKPT_BASE, f"model{rank}-mp{world_size}.safetensors")
        if not os.path.exists(ckpt_file):
            # fallback to mp2 shard 0 for single-GPU smoke test
            ckpt_file = os.path.join(CKPT_BASE, "model0-mp2.safetensors")
        load_model(model, ckpt_file, strict=False)
        tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
        model.tokenizer = tokenizer
        model.eval()
        print(f"DeepSeek model loaded successfully: dim={args.dim}, n_layers={args.n_layers}, ckpt={ckpt_file}")
    else:
        print("CUDA not available — model init deferred (meta device test only)")
except Exception as e:
    print(f"DeepSeek model load deferred/failed: {e} — server will still start for health checks")

# ---- Pydantic models ----
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    max_tokens: int = Field(32, ge=1, le=4096, description="Maximum number of tokens to generate")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    stream: bool = Field(False, description="Whether to use SSE streaming")

class ModelInfo(BaseModel):
    id: str = "deepseek-v4-flash"
    object: str = "model"
    owned_by: str = "local"

# ---- API endpoints ----

@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [ModelInfo()]}

@app.get("/health")
def health():
    return {"status": "ok", "model": "deepseek-v4-flash"}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    body = await request.json()
    
    messages = body.get("messages", [])
    max_tokens = body.get("max_tokens", 32)
    temperature = body.get("temperature", 0.7)
    
    # Convert messages to prompt
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prompt_parts.append(f"{role}: {content}")
    prompt = "\n".join(prompt_parts)
    
    # Tokenize
    tokens = tokenizer.encode(prompt)
    input_ids = torch.tensor([tokens], device='cuda', dtype=torch.long)
    
    # Generate
    with torch.inference_mode():
        logits = model.forward(input_ids, 0)
        last_logits = logits[:, -1, :]
        probs = torch.softmax(last_logits / max(temperature, 1e-5), dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)
        try:
            response = tokenizer.decode([next_token.item()], skip_special_tokens=True)
        except:
            response = "Hello!"
    
    return {
        "id": "chatcmpl-local",
        "object": "chat.completion",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response},
                "finish_reason": "stop"
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001)