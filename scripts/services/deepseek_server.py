#!/usr/bin/env python3
"""OpenAI-compatible FastAPI server for DeepSeek-V4-Flash inference."""
import os
import sys
import json
import torch

# Add the inference directory to path (absolute path based on script location)
INFERENCE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, INFERENCE_DIR)

from model import Transformer, ModelArgs
from safetensors.torch import load_model as sl
from transformers import AutoTokenizer

# Model configuration - absolute paths
CONFIG_PATH = os.path.join(INFERENCE_DIR, 'config.json')
CKPT_BASE = os.path.join('/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/deepseek-v4-converted')
TOKENIZER_PATH = os.path.join('/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash')

# Load config
with open(CONFIG_PATH) as f:
    args = ModelArgs(**json.load(f))

# Create model on cuda
model = Transformer(args)

# Load weights
load_model(model, os.path.join(CKPT_BASE, 'model0-mp2.safetensors'), strict=False)

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)

model.tokenizer = tokenizer
model.eval()
print(f"DeepSeek model loaded successfully: dim={args.dim}, n_layers={args.n_layers}")