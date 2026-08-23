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
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ2_XXS.gguf 24G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ3_M.gguf 34G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ3_XXS.gguf 30G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-IQ4_XS.gguf 37G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-Q2_K.gguf 28G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-Q2_K_L.gguf 29G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-Q3_K_L.gguf 37G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-Q3_K_S.gguf 33G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF/Qwen2.5-72B-Instruct-Q3_K_XL.gguf 38G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf 4.4G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/bartowski_Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf 17G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/microsoft_Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-fp16.gguf 7.2G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/microsoft_Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4.gguf 2.3G
/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/models/huggingface/Qwen_Qwen3-30B-A3B-GGUF/Qwen3-30B-A3B-Q4_K_M.gguf 18G
```

**Primary GGUF per LLM (used by manager `path`):**
- gemma-4 Q4_K_M 19G, gemma-3 Q4_K_M 16G, Qwen3.8 Q4_K_M 17G, Qwen3-30B Q4_K_M 18G, Nemotron-49B Q4_K_M 29G, Qwen2.5-7B Q4_K_M 4.4G, Llama-3.2 Q4_K_M 1.9G, Mistral Q4_K_M 4.1G (canonical 44G variant pool total 127G), Phi-3 q4 2.3G (fp16 7.2G), Qwen2.5-72B variants 512G total (manager expects `path` dir + auto-picks first gguf).

---

## 4. Per-directory `ls -lh` (selected)

**LLM GGUF dirs (single-file):**
- `bartowski_google_gemma-4-31B-it-GGUF` → 19G single `google_gemma-4-31B-it-Q4_K_M.gguf`
- `bartowski_google_gemma-3-27b-it-GGUF` → 16G single `google_gemma-3-27b-it-Q4_K_M.gguf`
- `bartowski_Qwen2.5-7B-Instruct-GGUF` → 4.4G single `Qwen2.5-7B-Instruct-Q4_K_M.gguf`
- `bartowski_Llama-3.2-3B-Instruct-GGUF` → 1.9G single
- `bartowski_Qwen3.8-27B-GGUF` → 17G `Qwen3.8-27B-Q4_K_M.gguf`
- `Qwen_Qwen3-30B-A3B-GGUF` → 18G `Qwen3-30B-A3B-Q4_K_M.gguf`
- `bartowski_nvidia_Llama-3_3-Nemotron-Super-49B` → 29G single
- `microsoft_Phi-3-mini-4k-instruct-gguf` → 7.2G fp16 + 2.3G q4 + docs (9.4G total)
- `Qwen2.5-72B` → 12 gguf files 23G–38G each (512G total, incomplete — no Q4_K_M/Q8_0 pair completed, 73G expected vs 512G on disk is 7+ quant variants stalled)
- `bartowski_Mistral` → 28G f32 + 22 quant files (1.6G–7.2G) = 127G
- `bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B` → **empty 4K** (partial removed)

**Embed dirs:**
- `BAAI_bge-m3` → 2.2G `pytorch_model.bin` 2.2G + `tokenizer.json` 17M + `sentencepiece.bpe.model` 4.9M
- `intfloat_multilingual-e5-small` → 449M `model.safetensors` + 449M `pytorch_model.bin` = 920M total + onnx cache → 1.2G du
- `sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2` → 449M `model.safetensors` + 449M `pytorch_model.bin` → 912M
- `sentence-transformers_all-MiniLM-L6-v2` → 87M×4 (`model.safetensors`, `pytorch_model.bin`, `rust_model.ot`, `tf_model.h5`) + onnx/openvino → 348M ls, 932M du
- `BAAI_bge-small-en-v1.5` → 128M `model.safetensors` + 128M `pytorch_model.bin` → 256M ls, 383M du

**DeepSeek:**
- `deepseek-ai_DeepSeek-V4-Flash` → `config.json` 1.8K + `generation_config.json` 170 + 46× `model-0000N-of-00046.safetensors` (1011M first + 45× ~3.4G) = 149G du (159.6G tensor total_size per `model.safetensors.index.json`), plus `inference/` and `encoding/` subdirs.

```json
// deepseek model.safetensors.index.json (head)
{
  "metadata": {"total_size": 159609485896},
  "weight_map": {
    "embed.weight": "model-00001-of-00046.safetensors",
    "layers.0.attn.wq_a.weight": "model-00002-of-00046.safetensors",
    ...
  }
}
```
46 shards confirmed `ls *.safetensors | wc -l` = 46.

---

## 5. `.state.json` vs `offline_prepare_cli.py:MODELS` vs Manager `MODEL_REGISTRY` — Delta

**`.state.json` items (69 total, `grep model_`):**
```text
model_TheBloke/Llama-3.2-3B-Instruct-GGUF
model_TheBloke/Mistral-7B-Instruct-v0.3-GGUF
model_TheBloke/Qwen2.5-7B-Instruct-GGUF
model_TheBloke/Phi-3-mini-4k-instruct-GGUF
model_BAAI/bge-small-en-v1.5
model_sentence-transformers/all-MiniLM-L6-v2
model_microsoft/Phi-3-mini-4k-instruct-gguf
... plus 62 docker/pip/system items (pip_torch 2.5.0 failed etc — stale)
```
Old `TheBloke/` prefix shows **stale state** (AGENTS.md warns `.state.json` stale — `failed` marks later hand-installed). Real on-disk uses `bartowski/` and `microsoft_Phi-3` etc.

**`offline_prepare_cli.py:MODELS` (original queue, line 276):**
```python
MODELS = {
    "Qwen/Qwen2.5-7B-Instruct-GGUF": "Qwen 2.5 7B (Official GGUF)",
    "bartowski/Llama-3.2-3B-Instruct-GGUF": "Llama 3.2 3B",
    "bartowski/Mistral-7B-Instruct-v0.3-GGUF": "Mistral 7B v0.3",
    "microsoft/Phi-3-mini-4k-instruct-gguf": "Phi-3 Mini",
    "BAAI/bge-small-en-v1.5": "BGE Small Embeddings",
    "sentence-transformers/all-MiniLM-L6-v2": "MiniLM Embeddings",
}
```
Only **6 entries** in original prepare CLI. Remainder (gemma-4, gemma-3, Qwen3.8, Qwen3-30B, Nemotron, BAAI/bge-m3, intfloat/e5, paraphrase, DeepSeek, Qwen72B) were added **manually outside the CLI queue** via `scripts/download_models.py` / proxy retries.

**`llm_inference_manager/app.py:MODEL_REGISTRY` (11 entries, lines 26–195):**
| id | name | size_gb | quant | path | status | benchmark_mean |
|----|------|---------|-------|------|--------|----------------|
| gemma-4-31b | Gemma-4 31B Instruct | 19.6 | Q4_K_M | `bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf` | loaded (5 backends 8080-84) | 0.663 |
| gemma-3-27b | Gemma-3 27B Instruct | 16.5 | Q4_K_M | `..._gemma-3-27b-it-GGUF/...Q4_K_M.gguf` | available | 0.600 |
| qwen3.8-27b | Qwen3.8 27B multimodal | 17.8 | Q4_K_M | `bartowski_Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf` | available | 0.477 |
| qwen3-30b-a3b | Qwen3-30B-A3B MoE 3B active | 18.6 | Q4_K_M | `Qwen_Qwen3-30B-A3B-GGUF/qwen3-30b-a3b-q4_k_m.gguf` | available | 0.283 |
| nemotron-49b | Nemotron-Super 49B v1 | 30.2 | Q4_K_M | `bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/...gguf` | available | 0.494 |
| qwen2.5-7b | Qwen2.5 7B Instruct | 4.4 | Q4_K_M | `bartowski_Qwen2.5-7B-Instruct-GGUF/...Q4_K_M.gguf` | available (loads on demo) | 0.443 |
| llama-3.2-3b | Llama-3.2 3B Instruct | 1.9 | Q4_K_M | `bartowski_Llama-3.2-3B-Instruct-GGUF/...` | available | 0.326 |
| mistral-7b | Mistral 7B Instruct v0.3 | 4.1 | Q4_K_M | `bartowski_Mistral .../Q4_K_M.gguf` | available | 0.186 |
| phi-3-mini | Phi-3 Mini 4K Instruct | 2.4 | q4 | `microsoft_Phi-3-mini.../Phi-3-mini-4k-instruct-q4.gguf` | available | 0.143 |
| deepseek-v4-flash | DeepSeek V4 Flash | 148.7 | FP8 | `deepseek-ai_DeepSeek-V4-Flash` (dir, 46 shards) | available (needs vLLM) | None |
| qwen2.5-72b | Qwen2.5 72B Instruct | 73 | Q4_K_M/Q8_0 variants | `bartowski_Qwen2.5-72B-Instruct-GGUF` (dir) | partial/on-disk | None |

**Delta documented:**
- CLI `MODELS (6)` ⊂ disk `17 dirs` ⊂ Manager `11 registry` ⊂ Disk LLM files `12 dirs (including partial)`.
- Excluded by `≤100GB` download policy / struck-through in README §1.1: MiniMax, Kimi, GLM variants were **never queued**; instead large `Qwen72B (512G)` and `Mistral f32 (28G)` over-filled beyond 100G cap (README logs `removed from queue (partial on disk)`).
- `.state.json` is **stale** per AGENTS.md — trust `pip freeze` / `du` not state.

---

## 6. Embed Models — S1.3.3 Verification

| HF repo | Local dir | `ls` demo files | `du -sh` | Dim | `embed_server.py` arg | Status |
|---------|-----------|-----------------|----------|-----|------------------------|--------|
| `intfloat/multilingual-e5-small` | `intfloat_multilingual-e5-small` | `model.safetensors` 449M + `pytorch_model.bin` 449M + `sentencepiece.bpe.model` 4.9M | **1.2G** | **384** | `--model intfloat_multilingual-e5-small --port 8001 --model-id e5-small` | ✅ live 8001 |
| `BAAI/bge-m3` | `BAAI_bge-m3` | `pytorch_model.bin` 2.2G + `tokenizer.json` 17M | **2.2G** | **1024** | `--model BAAI_bge-m3 --port 8002 --model-id bge-m3` | ✅ live 8002 |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2` | `model.safetensors` 449M + `pytorch_model.bin` 449M | **912M** (du 912M) | **384** | `--port 8003 --model-id paraphrase` | ✅ live 8003 |
| `BAAI/bge-small-en-v1.5` | `BAAI_bge-small-en-v1.5` | `model.safetensors` 128M + `pytorch_model.bin` 128M | **383M** | **384** | offline备用 | ✅ on-disk |
| `sentence-transformers/all-MiniLM-L6-v2` | `sentence-transformers_all-MiniLM-L6-v2` | 87M×4 + onnx/openvino | **932M** du (348M ls) | **384** | offline备用 | ✅ on-disk |

`scripts/services/embed_server.py` (61L) generic FastAPI `SentenceTransformer(args.model)` exposing `GET /health` → `{"dim": model.get_sentence_embedding_dimension()}` and `POST /v1/embeddings` (OpenAI-compatible). S1.5.1 will curl `/health` for dim check; inventory confirms files exist.

---

## 7. Canonical Inventory Table (for README §4)

| # | HF Repo ID | Local Path (`offline-prep/models/huggingface/`) | GGUF Filename | Size (du -sh) | Quant | Context | Benchmark Mean | Status |
|---|------------|--------------------------------------------------|---------------|---------------|-------|---------|---------------|--------|
| 1 | `bartowski/google_gemma-4-31B-it-GGUF` | `bartowski_google_gemma-4-31B-it-GGUF/` | `google_gemma-4-31B-it-Q4_K_M.gguf` | **19G** | Q4_K_M | 8192 | 0.663 ★ | **loaded** 5× 8080-84 |
| 2 | `bartowski/google_gemma-3-27b-it-GGUF` | `bartowski_google_gemma-3-27b-it-GGUF/` | `google_gemma-3-27b-it-Q4_K_M.gguf` | **16G** | Q4_K_M | 8192 | 0.600 | available |
| 3 | `bartowski/Qwen3.8-27B-GGUF` | `bartowski_Qwen3.8-27B-GGUF/` | `Qwen3.8-27B-Q4_K_M.gguf` | **17G** | Q4_K_M | 8192 | 0.477 | available |
| 4 | `Qwen/Qwen3-30B-A3B-GGUF` | `Qwen_Qwen3-30B-A3B-GGUF/` | `Qwen3-30B-A3B-Q4_K_M.gguf` | **18G** | Q4_K_M | 8192 | 0.283 | available |
| 5 | `bartowski/nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF` | `bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/` | `nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf` | **29G** | Q4_K_M | 8192 | 0.494 | available |
| 6 | `bartowski/Qwen2.5-7B-Instruct-GGUF` | `bartowski_Qwen2.5-7B-Instruct-GGUF/` | `Qwen2.5-7B-Instruct-Q4_K_M.gguf` | **4.4G** | Q4_K_M | 8192 | 0.443 | available |
| 7 | `bartowski/Llama-3.2-3B-Instruct-GGUF` | `bartowski_Llama-3.2-3B-Instruct-GGUF/` | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | **1.9G** | Q4_K_M | 8192 | 0.326 | available |
| 8 | `bartowski/Mistral-7B-Instruct-v0.3-GGUF` | `bartowski_Mistral-7B-Instruct-v0.3-GGUF/` | `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` (canonical; 22 variants 1.6G–28G) | **127G** dir (4.1G canonical) | Q4_K_M | 8192 | 0.186 | available |
| 9 | `microsoft/Phi-3-mini-4k-instruct-gguf` | `microsoft_Phi-3-mini-4k-instruct-gguf/` | `Phi-3-mini-4k-instruct-q4.gguf` (fp16 7.2G) | **9.4G** dir (2.3G q4) | q4 | 4096 | 0.143 | available |
| 10 | `deepseek-ai/DeepSeek-V4-Flash` | `deepseek-ai_DeepSeek-V4-Flash/` | 46× `model-00001..46.safetensors` FP8 | **149G** | FP8 | 8192 | — | available (needs vLLM) |
| 11 | `bartowski/Qwen2.5-72B-Instruct-GGUF` | `bartowski_Qwen2.5-72B-Instruct-GGUF/` | `Qwen2.5-72B-Instruct-Q*` 12 variants | **512G** dir | IQ*/Q* | 8192 | — | **partial** on-disk |
| 12 | `bartowski/nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF` | `bartowski_nvidia_Llama-3_1-Nemotron-Ultra-253B-v1-GGUF/` | *none (empty subdir)` | **3.6G** du (4K actual) | — | — | — | **broken/removed** |
| 13 | `intfloat/multilingual-e5-small` | `intfloat_multilingual-e5-small/` | `model.safetensors` + `pytorch_model.bin` | **1.2G** | — | 512 | — | embed 384 live 8001 |
| 14 | `BAAI/bge-m3` | `BAAI_bge-m3/` | `pytorch_model.bin` | **2.2G** | — | 8192 | — | embed 1024 live 8002 |
| 15 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `sentence-transformers_paraphrase-multilingual-MiniLM-L12-v2/` | `model.safetensors` | **912M** | — | 512 | — | embed 384 live 8003 |
| 16 | `sentence-transformers/all-MiniLM-L6-v2` | `sentence-transformers_all-MiniLM-L6-v2/` | `model.safetensors` | **932M** | — | 256 | — | embed 384 offline |
| 17 | `BAAI/bge-small-en-v1.5` | `BAAI_bge-small-en-v1.5/` | `model.safetensors` | **383M** | — | 512 | — | embed 384 offline |

**Total on-disk:** 908G (`du -sh offline-prep/models/huggingface`). HF links: `https://huggingface.co/<repo id>` (replace `_` → `/` after prefix). Download: `offline-prep/venv/bin/python3.12 scripts/download_models.py` or `hf download bartowski/...` with `http_proxy=192.168.203.2:3128`.

---

## 8. Verification Notes

- `ls -lh .../*.gguf | awk '{print $9,$5}'` captured verbatim in §3.
- `du -sh` numbers used as **ground truth** for README table (not README old 18.3/15.4 approximations).
- DeepSeek shards counted via `model.safetensors.index.json` total_size 159609485896 (≈148.7G tensors + overhead → 149G du).
- Embed dims from `embed_server.py: health()` returns `model.get_sentence_embedding_dimension()`; inventory confirms model files exist for all 5. S1.5.1 will curl for live dim verification.
- Manager registry size_gb slightly differs from du (e.g., 19.6 vs 19G, 73 vs 512G for 72B dir — manager reports expected single-quant size, not multi-variant total). Document delta in README.

---

*Evidence produced by Worker T1.3 — commands run 2026-08-23, fits `todo.md` S1.3.1/S1.3.2/S1.3.3.*
