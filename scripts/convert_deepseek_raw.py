#!/usr/bin/env python3
"""Raw safetensors parser for DeepSeek-V4-Flash (torch 2.4 compatible).

Bypasses safetensors library dtype handling. F8_E8M0 tensors are loaded as uint8.
F8_E4M3 (float8) tensors are loaded as int8. All other dtypes use standard torch mapping.
"""
import json, os, struct, shutil, mmap
from glob import glob
from argparse import ArgumentParser

import torch

# Safetensors dtype name → (torch dtype, bytes_per_element)
DTYPE_MAP = {
    "F64": (torch.float64, 8), "F32": (torch.float32, 4), "F16": (torch.float16, 2),
    "BF16": (torch.bfloat16, 2), "I64": (torch.int64, 8), "I32": (torch.int32, 4),
    "I16": (torch.int16, 2), "I8": (torch.int8, 1), "U8": (torch.uint8, 1),
    "BOOL": (torch.bool, 1), "C64": (torch.complex64, 8),
    "U64": (torch.uint64, 8), "U32": (torch.uint32, 4), "U16": (torch.uint16, 2),
    # FP8 types stored as raw bytes (reinterpreted as uint8/int8)
    "F8_E8M0": (torch.uint8, 1),
    "F8_E4M3": (torch.int8, 1),  # reinterpret as int8 for storage
    "F8_E5M2": (torch.int8, 1),
    "F8_E4M3FNUZ": (torch.int8, 1),
    "F8_E5M2FNUZ": (torch.int8, 1),
}

def load_raw_safetensors(path):
    """Load a safetensors file, bypassing dtype restrictions."""
    tensors = {}
    with open(path, "rb") as f:
        header_len = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(header_len))
        data_start = 8 + header_len
        for name, info in header.items():
            if name == "__metadata__":
                continue
            dtype_str = info["dtype"]
            shape = info["shape"]
            begin, end = info["data_offsets"]
            offset = data_start + begin
            n_bytes = end - begin
            torch_dtype, bpe = DTYPE_MAP.get(dtype_str, (torch.uint8, 1))
            numel = n_bytes // bpe
            f.seek(offset)
            raw = f.read(n_bytes)
            t = torch.frombuffer(raw, dtype=torch.uint8).clone()
            if torch_dtype != torch.uint8:
                t = t.view(torch_dtype)
            if shape:
                t = t.reshape(shape)
            tensors[name] = t
    return tensors


mapping = {
    "embed_tokens": ("embed", 0), "input_layernorm": ("attn_norm", None),
    "post_attention_layernorm": ("ffn_norm", None), "q_proj": ("wq", 0),
    "q_a_proj": ("wq_a", None), "q_a_layernorm": ("q_norm", None),
    "q_b_proj": ("wq_b", 0), "kv_a_proj_with_mqa": ("wkv_a", None),
    "kv_a_layernorm": ("kv_norm", None), "kv_b_proj": ("wkv_b", 0),
    "o_proj": ("wo", 1), "gate_proj": ("w1", 0), "down_proj": ("w2", 1),
    "up_proj": ("w3", 0), "lm_head": ("head", 0),
    "embed": ("embed", 0), "wq_b": ("wq_b", 0),
    "wo_a": ("wo_a", 0), "wo_b": ("wo_b", 1), "head": ("head", 0),
    "attn_sink": ("attn_sink", 0), "weights_proj": ("weights_proj", 0),
}


def main(hf_path, save_path, n_experts, mp):
    from safetensors.torch import save_file
    torch.set_num_threads(8)
    n_local_experts = n_experts // mp
    state_dicts = [{} for _ in range(mp)]

    for fp in sorted(glob(os.path.join(hf_path, "*.safetensors"))):
        print(f"Loading {os.path.basename(fp)}...")
        tensors = load_raw_safetensors(fp)
        for name, param in tensors.items():
            if name.startswith("model."):
                name = name[len("model."):]
            if name.startswith("mtp.") and ("emb" in name or name.endswith("head.weight")):
                continue
            name = name.replace("self_attn", "attn").replace("mlp", "ffn")
            name = name.replace("weight_scale_inv", "scale").replace("e_score_correction_bias", "bias")
            key = name.split(".")[-1] if any(x in name for x in ["hc", "attn_sink", "tie2eid", "ape"]) else name.split(".")[-2]
            new_key, dim = mapping.get(key, (key, None))
            name = name.replace(key, new_key)
            for i in range(mp):
                new_param = param
                if "experts" in name and "shared_experts" not in name:
                    idx = int(name.split(".")[-3])
                    if idx < i * n_local_experts or idx >= (i + 1) * n_local_experts:
                        continue
                elif dim is not None:
                    shard_size = param.size(dim) // mp
                    new_param = param.narrow(dim, i * shard_size, shard_size).contiguous()
                state_dicts[i][name] = new_param

    os.makedirs(save_path, exist_ok=True)
    for i in range(mp):
        names = list(state_dicts[i].keys())
        for name in names:
            if name.endswith("wo_a.weight") and name in state_dicts[i]:
                weight = state_dicts[i][name]
                scale_key = name.replace("weight", "scale")
                if scale_key in state_dicts[i]:
                    scale = state_dicts[i].pop(scale_key)
                    # Dequant wo_a: fp4 weight (as uint8) + scale (as uint8=F8_E8M0) → bf16
                    try:
                        state_dicts[i][name] = dequant_wo_a(weight, scale)
                    except Exception as e:
                        print(f"  wo_a dequant failed ({e}), keeping as uint8")
        # Filter out tensors that can't be saved (remove unsupported dtypes)
        saved = {}
        for k, v in state_dicts[i].items():
            try:
                # Convert F8_E8M0 (uint8) scales to float32 for saving
                if v.dtype == torch.uint8 and "scale" in k:
                    saved[k] = v.float()
                elif v.dtype == torch.int8 or v.dtype == torch.uint8:
                    saved[k] = v  # int8/uint8 are supported by safetensors
                else:
                    saved[k] = v
            except Exception as e:
                print(f"  skip {k}: {e}")
        save_file(saved, os.path.join(save_path, f"model{i}-mp{mp}.safetensors"))
        print(f"  Saved model{i}-mp{mp}.safetensors ({len(saved)} tensors)")

    for file in ["tokenizer.json", "tokenizer_config.json"]:
        old, new = os.path.join(hf_path, file), os.path.join(save_path, file)
        if os.path.exists(old):
            shutil.copyfile(old, new)
    print("Done!")


def dequant_wo_a(weight, scale):
    """Dequantize wo_a: uint8 packed FP4 → bf16."""
    FP4_TABLE = torch.tensor([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0,
                               0.0, -0.5, -1.0, -1.5, -2.0, -3.0, -4.0, -6.0])
    x = weight.view(torch.uint8)
    low = x & 0x0F
    high = (x >> 4) & 0x0F
    x = torch.stack([FP4_TABLE[low.long()], FP4_TABLE[high.long()]], dim=-1).flatten(2)
    out_dim, in_dim_orig = weight.size()
    in_dim = in_dim_orig * 2
    fp8_block_size = 128
    fp4_block_size = 32
    bOut, bIn = out_dim // fp8_block_size, in_dim // fp8_block_size
    x = x.view(bOut, fp8_block_size, bIn, fp8_block_size).transpose(1, 2)
    sc = scale.float().view(bOut, fp8_block_size, bIn, -1).transpose(1, 2).flatten(2)
    scale_max = sc.amax(dim=-1, keepdim=True) / 64.0
    offset = sc / scale_max
    offset = offset.unflatten(-1, (fp8_block_size, -1)).repeat_interleave(fp4_block_size, dim=-1)
    x = (x * offset).transpose(1, 2).reshape(out_dim, in_dim)
    return x.bfloat16()


if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("--hf-ckpt-path", required=True)
    p.add_argument("--save-path", required=True)
    p.add_argument("--n-experts", type=int, required=True)
    p.add_argument("--model-parallel", type=int, required=True)
    a = p.parse_args()
    assert a.n_experts % a.model_parallel == 0
    main(a.hf_ckpt_path, a.save_path, a.n_experts, a.model_parallel)
