# Project Context - H200 RAG + DeepSeek-V4-Flash

## Environment
- ai-gpu1 2xH200 143GB, proxy 192.168.203.2:3128, dir /splunk-data/v1/Work_RAG-Server-Setup
- Main venv offline-prep/venv py3.12 torch2.8, dedicated venv offline-prep/venv-deepseek py3.12 torch2.9.1+cu128 transformers5.15.1 tilelang0.1.13 triton3.5.1
- Converted DeepSeek: offline-prep/models/deepseek-v4-converted model0/1-mp2.safetensors 88G x2 (I8+scale), HF original 149GB 46 shards
- GPUs currently freed 5GB/6MB (Gemma 5 stopped), ready for DeepSeek 2xH200
- Daemons: download PID1540875, auto_commit PID2009361 (push to AliNikkhah2001/Work_RAG-Server-Setup), Gemma 5x 8080-84 was healthy before stop

## Current Status
- DONE: torch2.8->2.9.1 dedicated env, import OK, identified Float4 copy bug - checkpoint I8 [2048,2048]+scale F8_E8M0 vs model float4_e2m1fn_x2, copy_ not implemented even in 2.9.1
- DONE: Diagnosed header: routed experts I8+scale, shared F8_E4M3, inference config expert_dtype fp4
- IN_PROGRESS: job_25b3d37a fix-bf16-convert - dequant I8+scale to bf16 [2048,2048] for routed experts, save to offline-prep/models/deepseek-v4-bf16 with fixed config (dtype bf16 expert_dtype null), ~10min for 176GB
- PENDING: torchrun --nproc_per_node=2 with bf16 checkpoint + fixed config, test question "Hello explain quantum" and Persian, wrap as FastAPI 9001, benchmark, regenerate README
- PENDING: restart Gemma 5 after DeepSeek test

## Pending Tasks
- Wait fix-bf16-convert done, verify ls -lh bf16 dir, run torchrun with dedicated venv and fixed config, ask test questions
- If bf16 works, benchmark DeepSeek vs Gemma, update download queue (Qwen72B 478GB trim), ensure models downloading in background
- Restart Gemma 5x supervisor, update docs/history

## Notes
- Test cmd: /splunk-data/v1/Work_RAG-Server-Setup/offline-prep/venv-deepseek/bin/torchrun --nproc_per_node=2 inference/generate.py --ckpt-path bf16 --config bf16/config.json --input-file /tmp/deepseek_input.txt --max-new-tokens 64
- Patch attempt with mtp filter failed (all experts need fix), direct float4 copy works small but I8->float4 fails
- Fix script /tmp/fix_experts3.py does I8*scale->bf16 for routed only, keep shared as is
