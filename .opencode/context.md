# Project Context - H200 RAG + DeepSeek-V4-Flash

## Environment
- ai-gpu1 2xH200 143GB, proxy 192.168.203.2:3128, dir /splunk-data/v1/Work_RAG-Server-Setup
- Venvs: offline-prep/venv py3.12 torch2.8, offline-prep/venv-deepseek py3.12 torch2.9.1+cu128 transformers5.15.1 tilelang0.1.13
- DeepSeek: HF 149GB 46 shards, converted 88G x2 (I8+scale), bf16 attempt 154G x2 OOM 134GB >139GB, now packing to float4 88G
- GPUs freed 5GB/6MB, Daemons: download PID1540875, auto_commit PID2009361

## Current Status
- DONE: dedicated venv, import OK, diagnosed I8->float4 copy bug, bf16 conversion done 154GB but OOM on H200, int8 patch also OOM at init (139GB)
- IN_PROGRESS: job_eebe9feb pack-float4 - reinterpret I8 [2048,2048] as float4_e2m1fn_x2 [2048,2048] via view, keep 88GB, use original inference config fp4, expect to fit 88GB per GPU
- PENDING: torchrun with float4 checkpoint, test questions, wrap FastAPI 9001, benchmark, regenerate README
- PENDING: restart Gemma 5x 8080-84 after DeepSeek test

## Pending Tasks
- Wait pack-float4 done, verify ls -lh float4 dir, test torchrun with dedicated venv
- If float4 works, run questions, benchmark, update downloads (Qwen72B 478GB trim)
- Restart Gemma, update docs

## Notes
- Test cmd: torchrun --nproc_per_node=2 inference/generate.py --ckpt-path deepseek-v4-float4 --config deepseek-v4-float4/config.json --input-file /tmp/deepseek_input.txt --max-new-tokens 32
- Model uses 43 layers, 256 experts, topk6, need 2 GPUs for 88GB each
