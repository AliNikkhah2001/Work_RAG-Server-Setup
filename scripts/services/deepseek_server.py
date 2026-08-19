#!/usr/bin/env python3
"""OpenAI-compatible FastAPI server for DeepSeek-V4-Flash inference."""
import os
import sys
import json
import torch

# ---- Hard-coded absolute paths ----
# These paths are fixed for this deployment
REPO_ROOT = "/splunk-data/v1/Work_RAG-Server-Setup"
INFERENCE_DIR = os.path.join(REPO_ROOT, "offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash/inference")
CONFIG_PATH = os.path.join(REPO_ROOT, "offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash/config.json")
CKPT_BASE = os.path.join(REPO_ROOT, "offline-prep/models/deepseek-v4-converted")
TOKENIZER_PATH = os.path.join(REPO_ROOT, "offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash")

# Add inference directory to path
sys.path.insert(0, INFERENCE_DIR)

from model import Transformer, ModelArgs
from safetensors.torch import load_model as sl
from transformers import AutoTokenizer

# Load config
with open(CONFIG_PATH) as f:
    args = ModelArgs(**json.load(f))

# Create model on cuda
model = Transformer(args)

# Load weights
load_model(model, os.path.join(CKPT_BASE, "model0-mp2.safetensors"), strict=False)

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)

model.tokenizer = tokenizer
model.eval()
print(f"DeepSeek model loaded successfully: dim={args.dim}, n_layers={args.n_layers}")

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