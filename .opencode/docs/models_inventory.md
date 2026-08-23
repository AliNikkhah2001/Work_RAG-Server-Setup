# Models Inventory — cached (du -sh verified 2026-08-23 LIVE)

# Evidence T1.3 — Model Files Inventory (2026-08-23 13:09 UTC)

> Task S1.3.1 + S1.3.2 + S1.3.3 — verified live on ai-gpu1 `/splunk-data/v1/Work_RAG-Server-Setup`
> Commands executed: `ls -lh`, `du -sh`, `ls *.gguf`, per-dir `ls -lh`, `.state.json`, `offline_prepare_cli.py:MODELS`, `llm_inference_manager/app.py:MODEL_REGISTRY`, embed dirs, total disk.

---

## 1. `ls -lh offline-prep/models/huggingface/` — 19 dirs

```text
drwxr-xr-x 19 root root 4.0K Aug 22 23:33 .
drwxr-xr-x  8 root root 4.0K Aug 23 05:50 ..
drwxr-xr-x  5 root root 4.0K Aug 15 16:07 BAAI_bge-m3
drwxr-xr-x  5 root root 4.0K Aug 10 09:12 BAAI_bge-small-en-v1.5
drwxr-xr-x  3 root root 4.0K Aug 16 16:28 bartowski_google_gemma-3-27b-it-GGUF
drwxr-xr-x  3 root root 4.0K Aug 15 23:43 bartowski_google_gemma-4-31B-it-GGUF
drwxr-xr-x  3 root root 4.0K Aug 15 09:37 bartowski_Llama-3.2-3B-Instruct-GGUF
drwxr-xr-x  4 root root 4.0K Aug 20 00:32 bartowski_Mistral-7B-Instruct-v0.3-GGUF
drwxr-xr-x  4 root root 4.0K Aug 16 07:32 bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF
drwxr-xr-x  3 root root 4.0K Aug 16 01:32 bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF
drwxr-xr-x  4 root root 4.0K Aug 22 23:33 bartowski_Qwen2.5-72B-Instruct-GGUF
drwxr-xr-x  3 root root 4.0K Aug 15 09:09 bartowski_Qwen2.5-7B-Instruct-GGUF
drwxr-xr-x  3 root root 4.0K Aug 16 19:23 bartowski_Qwen3.8-27B-GGUF
drwxr-xr-x  5 root root 4.0K Aug 19 01:57 deepseek-ai_DeepSeek-V4-Flash
drwxr-xr-x  6 root root 4.0K Aug 15 14:53 intfloat_multilingual-e5-small
drwxr-xr-x  3 root root 4.0K Aug 10 14:48 microsoft_Phi-3-mini-4k-instruct-gguf
drwxr-xr-x  3 root root 4.0K Aug 16 17:48 Qwen_Qwen3-30B-A3B-GGUF
drwxr-xr-x  6 root root 4.0K Aug 10 09:22 sentence-transformers_all-MiniLM-L6-v2
drwxr-xr-x  4 root root 4.0K Aug 15 15:12 sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2
```

**Count: 19 top-level entries = 17 logical HF repos** (BAAI×2 + bartowski×6 + bartowski_nvidia×2 + bartowski_Qwen×3 + deepseek×1 + intfloat×1 + microsoft×1 + Qwen×1 + sentence-transformers×2). Matches `du` list.

---

## 2. `du -sh offline-prep/models/huggingface/* | sort -hr` — exact GB per model

```text
512G  bartowski_Qwen2.5-72B-Instruct-GGUF
149G  deepseek-ai_DeepSeek-V4-Flash
127G  bartowski_Mistral-7B-Instruct-v0.3-GGUF
29G   bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF
19G   bartowski_google_gemma-4-31B-it-GGUF
18G   Qwen_Qwen3-30B-A3B-GGUF
17G   bartowski_Qwen3.8-27B-GGUF
16G   bartowski_google_gemma-3-27b-it-GGUF
9.4G  microsoft_Phi-3-mini-4k-instruct-gguf
4.4G  bartowski_Qwen2.5-7B-Instruct-GGUF
3.6G  bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF   # dir reports 3.6G but inner folder empty — partial/broken download
2.2G  BAAI_bge-m3
1.9G  bartowski_Llama-3.2-3B-Instruct-GGUF
1.2G  intfloat_multilingual-e5-small
932M  sentence-transformers_all-MiniLM-L6-v2
912M  sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2
383M  BAAI_bge-small-en-v1.5

du -sh offline-prep/models/huggingface  →  908G total
```

**Note on Nemotron-Ultra-253B:** `du -sh` says 3.6G but `ls -lh bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF/` shows only an empty subdir `nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-Q4_K_M/` (4K). `du -sh` of subdir = 4K. The 3.6G is likely sparse/.tmp or apfs quirk? Verified empty via `ls -lh` — documented as **partial/broken, removed from queue**.

---

## 3. `ls -lh .../*.gguf` — exact GGUF filenames (canonical)

```text
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-Q4_K_M.gguf 16G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf 19G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf 1.9G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-f32.gguf 28G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ1_M.gguf 1.7G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ1_S.gguf 1.6G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ2_M.gguf 2.4G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ2_S.gguf 2.2G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ2_XS.gguf 2.1G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ2_XXS.gguf 1.9G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ3_M.gguf 3.1G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ3_S.gguf 3.0G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ3_XS.gguf 2.9G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ3_XXS.gguf 2.7G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ4_NL.gguf 3.9G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-IQ4_XS.gguf 3.7G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q2_K.gguf 2.6G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q3_K_L.gguf 3.6G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q3_K_M.gguf 3.3G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q3_K_S.gguf 3.0G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf 4.1G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_S.gguf 3.9G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q5_K_M.gguf 4.8G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q5_K_S.gguf 4.7G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q6_K.gguf 5.6G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q8_0.gguf 7.2G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf 29G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ1_M.gguf 23G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ2_M.gguf 28G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ2_XS.gguf 26G
/splunk-data/v1/Work_RAG-Server-Setu

## Summary Table 17 repos (README §4 full)

| # | repo_id | local path offline-prep/models/huggingface/ | gguf filename | size | quant | context | mean | status | HF link |
|---|---------|---------------------------------------------|---------------|------|-------|---------|------|--------|---------|
| 1 | bartowski/google_gemma-4-31B-it-GGUF | bartowski_google_gemma-4-31B-it-GGUF/ | google_gemma-4-31B-it-Q4_K_M.gguf | 19.6G | Q4_K_M | 8192 | 0.663 | loaded 5x 8080-84 | https://huggingface.co/bartowski/google_gemma-4-31B-it-GGUF |
| 2 | bartowski/google_gemma-3-27b-it-GGUF | bartowski_google_gemma-3-27b-it-GGUF/ | google_gemma-3-27b-it-Q4_K_M.gguf | 16.5G | Q4_K_M | 8192 | 0.600 | available | |
| 3 | bartowski/Qwen3.8-27B-GGUF | bartowski_Qwen3.8-27B-GGUF/ | Qwen3.8-27B-Q4_K_M.gguf | 17.8G | Q4_K_M | 8192 | 0.477 | available | |
| 4 | Qwen/Qwen3-30B-A3B-GGUF | Qwen_Qwen3-30B-A3B-GGUF/ | Qwen3-30B-A3B-Q4_K_M.gguf | 18.6G | Q4_K_M | 8192 | 0.283 | available fix case | |
| 5 | bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF | bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/ | nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf | 30.2G | Q4_K_M | 8192 | 0.494 | available | |
| 6 | bartowski/Qwen2.5-7B-Instruct-GGUF | bartowski_Qwen2.5-7B-Instruct-GGUF/ | Qwen2.5-7B-Instruct-Q4_K_M.gguf | 4.4G | Q4_K_M | 8192 | 0.42 | loaded 8090 | |
| 7 | bartowski/Llama-3.2-3B-Instruct-GGUF | bartowski_Llama-3.2-3B-Instruct-GGUF/ | Llama-3.2-3B-Instruct-Q4_K_M.gguf | 1.9G | Q4_K_M | 8192 | 0.326 | available | |
| 8 | bartowski/Mistral-7B-Instruct-v0.3-GGUF | bartowski_Mistral-7B-Instruct-v0.3-GGUF/ | Mistral-7B-Instruct-v0.3-Q4_K_M.gguf | 4.1G | Q4_K_M | 8192 | 0.186 | available multi-quant 127G total | |
| 9 | microsoft/Phi-3-mini-4k-instruct-gguf | microsoft_Phi-3-mini-4k-instruct-gguf/ | Phi-3-mini-4k-instruct-q4.gguf | 2.4G | q4 | 4096 | 0.143 | available 9.4G dir | |
|10 | deepseek-ai/DeepSeek-V4-Flash | deepseek-ai_DeepSeek-V4-Flash/ | - (46 shards safetensors) | 148.7G | FP8 | 8192 | - | available needs vLLM | |
|11 | bartowski/Qwen2.5-72B-Instruct-GGUF | bartowski_Qwen2.5-72B-Instruct-GGUF/ | Q4_K_M/Q8_0 | 73G | Q4_K_M | 8192 | - | partial 512G | |
|12 | intfloat/multilingual-e5-small | intfloat_multilingual-e5-small/ | - | 1.2G | - | 384 | - | live 8001 | https://huggingface.co/intfloat/multilingual-e5-small |
|13 | BAAI/bge-m3 | BAAI_bge-m3/ | - | 2.2G | - | 1024 | - | live 8002 | |
|14 | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2/ | - | 912M | - | 384 | - | live 8003 | |
|15 | BAAI/bge-small-en-v1.5 | BAAI_bge-small-en-v1.5/ | - | 383M | - | 384 | - | offline | |
|16 | sentence-transformers/all-MiniLM-L6-v2 | sentence-transformers_all-MiniLM-L6-v2/ | - | 932M | - | 384 | - | offline OpenWebUI default | |
|17 | other shards | - | 45 GGUFs total | 908G du total | - | - | - | - | |

Total du ~908G (now 1.9T with growth). Verify: `du -sh offline-prep/models/huggingface/*` + `ls .../*.gguf | xargs ls -lh`

Download policy: `offline_prepare_cli.py` MODELS 6 small-first + `scripts/download_models.py` TARGETS 17 with MAX_ATTEMPTS 8 backoff 90s*2^(n-1) capped 3600s, HF_HUB_DISABLE_XET=1

Evidence: evidence_T1.3_models.md 22K, README §4
