#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Inference Manager - OpenAI-compatible gateway with multi-model registry,
dynamic spawn, session/history, metrics, and Open WebUI integration.
"""
import os, json, time, uuid, sqlite3, subprocess, signal, atexit, pathlib, shlex, sys
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx
import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = pathlib.Path(__file__).parent / "manager.db"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
START_TIME = time.time()

# --------------------------------------------------------------------------
# Model Registry - from README §4 + huggingface dirs
# --------------------------------------------------------------------------
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "gemma-4-31b": {
        "id": "gemma-4-31b",
        "name": "Gemma-4 31B Instruct",
        "creator": "Google DeepMind",
        "family": "Gemma-4",
        "params": "31B",
        "size_gb": 19.6,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.663,
        "status": "loaded",
        "backends": ["http://127.0.0.1:18000"],
        "n_ctx": 8192,
        "notes": "Champion model - best Persian eval",
    },
    "gemma-3-27b": {
        "id": "gemma-3-27b",
        "name": "Gemma-3 27B Instruct",
        "creator": "Google DeepMind",
        "family": "Gemma-3",
        "params": "27B",
        "size_gb": 16.5,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.600,
        "status": "available",
        "backends": [],
        "n_ctx": 8192,
    },
    "qwen3.8-27b": {
        "id": "qwen3.8-27b",
        "name": "Qwen3.8 27B (multimodal)",
        "creator": "Alibaba",
        "family": "Qwen3.8",
        "params": "27B",
        "size_gb": 17.8,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.477,
        "status": "available",
        "backends": [],
    },
    "qwen3-30b-a3b": {
        "id": "qwen3-30b-a3b",
        "name": "Qwen3-30B-A3B MoE (3B active)",
        "creator": "Alibaba",
        "family": "Qwen3-MoE",
        "params": "30B/3B",
        "size_gb": 18.6,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/Qwen_Qwen3-30B-A3B-GGUF/Qwen3-30B-A3B-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.283,
        "status": "available",
        "backends": [],
    },
    "nemotron-49b": {
        "id": "nemotron-49b",
        "name": "Nemotron-Super 49B v1",
        "creator": "NVIDIA + Llama 3.3",
        "family": "Nemotron",
        "params": "49B",
        "size_gb": 30.2,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_nvidia_Llama-3_3-Nemotron-Super-49B-v1-GGUF/nvidia_Llama-3_3-Nemotron-Super-49B-v1-Q4_K_M.gguf",
        "context": 8192,
        "license": "NVIDIA Open",
        "benchmark_mean": 0.494,
        "status": "available",
        "backends": [],
    },
    "qwen2.5-7b": {
        "id": "qwen2.5-7b",
        "name": "Qwen2.5 7B Instruct",
        "creator": "Alibaba",
        "family": "Qwen2.5",
        "params": "7B",
        "size_gb": 4.4,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.443,
        "status": "available",
        "backends": [],
    },
    "llama-3.2-3b": {
        "id": "llama-3.2-3b",
        "name": "Llama-3.2 3B Instruct",
        "creator": "Meta",
        "family": "Llama-3.2",
        "params": "3.2B",
        "size_gb": 1.9,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "context": 8192,
        "license": "Llama 3.2",
        "benchmark_mean": 0.326,
        "status": "available",
        "backends": [],
    },
    "mistral-7b": {
        "id": "mistral-7b",
        "name": "Mistral 7B Instruct v0.3",
        "creator": "Mistral AI",
        "family": "Mistral",
        "params": "7B",
        "size_gb": 4.1,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/bartowski_Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.186,
        "status": "available",
        "backends": [],
    },
    "phi-3-mini": {
        "id": "phi-3-mini",
        "name": "Phi-3 Mini 4K Instruct",
        "creator": "Microsoft",
        "family": "Phi-3",
        "params": "3.8B",
        "size_gb": 2.4,
        "quant": "q4",
        "path": "offline-prep/models/huggingface/microsoft_Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4.gguf",
        "context": 4096,
        "license": "MIT",
        "benchmark_mean": 0.143,
        "status": "available",
        "backends": [],
    },
    "deepseek-v4-flash": {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash",
        "creator": "DeepSeek AI",
        "family": "DeepSeek",
        "params": "685B (MoE)",
        "size_gb": 148.7,
        "quant": "FP8",
        "path": "offline-prep/models/huggingface/deepseek-ai_DeepSeek-V4-Flash",
        "context": 8192,
        "license": "DeepSeek",
        "benchmark_mean": None,
        "status": "available (needs vLLM/transformers)",
        "backends": [],
    },
"qwen2.5-72b": {
        "id": "qwen2.5-72b",
        "name": "Qwen2.5 72B Instruct",
        "creator": "Alibaba",
        "family": "Qwen2.5",
        "params": "72B",
        "size_gb": 73,
        "quant": "Q4_K_M/Q8_0 variants",
        "path": "offline-prep/models/huggingface/bartowski_Qwen2.5-72B-Instruct-GGUF",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": None,
        "status": "partial/on-disk",
        "backends": [],
    },
    "mizan-v3-3b": {
        "id": "mizan-v3-3b",
        "name": "Mizan-v3-3B",
        "creator": "Nimruz",
        "family": "qwen",
        "params": "3B",
        "size_gb": 1.9,
        "quant": "Q4_K_M",
        "path": "offline-prep/models/huggingface/Nimruz_Mizan-v3-3B-GGUF/mizan-v3-3b-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.825,
        "status": "available",
        "backends": [],
        "n_ctx": 8192,
        "notes": "Persian-first System-1 decision model (choice/noul/score)",
    },
    # --- Triton-optimized champion variants (B + A) ---
    "gemma-4-31b-triton-vllm": {
        "id": "gemma-4-31b-triton-vllm",
        "name": "Gemma-4 31B Triton-vLLM (reuse GGUF, continuous batching)",
        "creator": "Google DeepMind",
        "family": "Gemma-4-Triton",
        "params": "31B",
        "size_gb": 19.6,
        "quant": "Q4_K_M + PagedAttention",
        "path": "offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.663,
        "status": "available",
        "backends": [],
        "n_ctx": 8192,
        "backend_type": "triton_vllm",
        "notes": "B: fast path - reuses GGUF via vLLM Triton kernels (no HF download), continuous batching, prefix caching",
    },
    "gemma-4-31b-triton-trt": {
        "id": "gemma-4-31b-triton-trt",
        "name": "Gemma-4 31B Triton-TRT-LLM (HF FP8 engine)",
        "creator": "Google DeepMind",
        "family": "Gemma-4-Triton",
        "params": "31B",
        "size_gb": 38,
        "quant": "FP8 TensorRT-LLM",
        "path": "offline-prep/models/huggingface/google_gemma-4-31b-it",
        "engine_path": "offline-prep/models/trt_engines/gemma-4-31b_fp8",
        "context": 8192,
        "license": "Apache-2.0",
        "benchmark_mean": 0.663,
        "status": "loaded",
        "backends": ["http://127.0.0.1:8010"],
        "n_ctx": 8192,
        "backend_type": "triton_trtllm",
        "notes": "A: best future - HF FP8 TRT-LLM engine, Triton dynamic batching",
    },
}

# Round-robin counters for load balancing
rr_counters: Dict[str, int] = {k:0 for k in MODEL_REGISTRY}

# Track spawned processes
spawned_processes: Dict[str, subprocess.Popen] = {}

# --------------------------------------------------------------------------
# Unified Panel — upstreams (Main Panel :9000 proxies all other panels)
# --------------------------------------------------------------------------
LITELLM_URL = os.getenv("LITELLM_URL", os.getenv("LITELLM_HOST", "http://127.0.0.1:4000")).rstrip("/")
PANEL_UPSTREAMS: Dict[str, str] = {
    "kb":       os.getenv("PANEL_KB_URL", "http://127.0.0.1:8000"),
    "guard":    os.getenv("PANEL_GUARD_URL", "http://127.0.0.1:8200"),
    "trace":    os.getenv("PANEL_TRACE_URL", "http://127.0.0.1:3000"),
    "langfuse": os.getenv("PANEL_LANGFUSE_URL", "http://127.0.0.1:3001"),
    "studio":   os.getenv("PANEL_STUDIO_URL", "http://127.0.0.1:2024"),
    "grafana":  os.getenv("PANEL_GRAFANA_URL", "http://127.0.0.1:13001"),
    "prom":     os.getenv("PANEL_PROM_URL", "http://127.0.0.1:19090/prometheus"),
    "webui":    os.getenv("PANEL_WEBUI_URL", "http://127.0.0.1:13000"),
    "litellm":  LITELLM_URL,
    "jaeger":   os.getenv("PANEL_JAEGER_URL", "http://127.0.0.1:16686"),
    "embed8001": os.getenv("PANEL_EMBED8001_URL", "http://127.0.0.1:8001"),
    "embed8002": os.getenv("PANEL_EMBED8002_URL", "http://127.0.0.1:8002"),
    "embed8003": os.getenv("PANEL_EMBED8003_URL", "http://127.0.0.1:8003"),
    "triton":   os.getenv("PANEL_TRITON_URL", "http://127.0.0.1:8004"),
    "triton_vllm": os.getenv("PANEL_TRITON_VLLM_URL", "http://127.0.0.1:8104"),
    "triton_grpc": os.getenv("PANEL_TRITON_GRPC_URL", "http://127.0.0.1:8005"),
}
# per-panel health probe path (fallback to /) — must match upstream --web.route-prefix
PANEL_HEALTH_PATH: Dict[str, str] = {
    "kb": "/health",
    "guard": "/health",
    "trace": "/health",
    "langfuse": "/api/public/health",
    "studio": "/health",
    "grafana": "/api/health",
    "prom": "/-/healthy",
    "webui": "/health",
    "litellm": "/health/liveliness",
    "jaeger": "/",
    "embed8001": "/health",
    "embed8002": "/health",
    "embed8003": "/health",
    "triton": "/v2/health/ready",
    "triton_vllm": "/health",
    "triton_grpc": "/v2/health/ready",
}

# T-C3: Fix CORS — explicit origins, no wildcard with credentials (merged: PUBLIC_CORS_ORIGINS + secure default)
PUBLIC_CORS_ORIGINS = os.getenv("PUBLIC_CORS_ORIGINS", os.getenv("CORS_ORIGINS", "http://localhost:13000,http://127.0.0.1:13000"))
_cors_origins = [o.strip() for o in PUBLIC_CORS_ORIGINS.split(",") if o.strip() and o.strip() != "*"]
if not _cors_origins:
    _cors_origins = ["http://localhost:13000", "http://127.0.0.1:13000"]
app = FastAPI(title="LLM Inference Manager", version="1.0.0", description="OpenAI-compatible gateway with session/history, metrics, multi-model load balancing")
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS models (
        id TEXT PRIMARY KEY,
        name TEXT,
        config_json TEXT,
        status TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS api_tokens (
        token TEXT PRIMARY KEY,
        name TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        model TEXT,
        title TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        role TEXT,
        content TEXT,
        created_at TEXT,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(id)
    );
    CREATE TABLE IF NOT EXISTS metrics (
        id TEXT PRIMARY KEY,
        model TEXT,
        endpoint TEXT,
        latency_ms REAL,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        created_at TEXT
    );
    """)
    # --- migrations for analytics (per-sample + cumulative) ---
    for ddl in [
        "ALTER TABLE metrics ADD COLUMN status TEXT",
        "ALTER TABLE metrics ADD COLUMN finish_reason TEXT",
        "ALTER TABLE metrics ADD COLUMN panel TEXT",
        "ALTER TABLE metrics ADD COLUMN trace_id TEXT",
    ]:
        try: conn.execute(ddl)
        except: pass
    conn.execute("""
    CREATE TABLE IF NOT EXISTS cache_transparency (
        query_hash TEXT PRIMARY KEY,
        query TEXT,
        payload TEXT,
        created_at TEXT
    );
    """)
    # backfill status for old rows
    try: conn.execute("UPDATE metrics SET status='success' WHERE status IS NULL")
    except: pass
    conn.commit()
    # seed default token if none
    cur = conn.execute("SELECT count(*) FROM api_tokens")
    if cur.fetchone()[0]==0:
        conn.execute("INSERT INTO api_tokens(token,name,created_at) VALUES(?,?,?)", ("sk-local-dev", "default local", datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

init_db()

PUBLIC_MODE = os.getenv("PUBLIC_DASHBOARD", "0").lower() in ("1","true","yes","on")
PUBLIC_REQUIRE_AUTH = os.getenv("PUBLIC_REQUIRE_AUTH", "1").lower() in ("1","true","yes","on")

def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        if PUBLIC_MODE and PUBLIC_REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="Public mode requires Authorization: Bearer <token>")
        return True  # allow anonymous for local dev - change to require token in prod
    token = authorization.replace("Bearer ","").strip()
    if token in ("sk-local-dev", "local", ""):
        # in public mode, sk-local-dev is not sufficient unless explicitly allowed
        if PUBLIC_MODE and PUBLIC_REQUIRE_AUTH and token == "sk-local-dev" and os.getenv("ALLOW_SK_LOCAL_IN_PUBLIC","0") not in ("1","true","yes","on"):
            raise HTTPException(status_code=401, detail="Public mode: sk-local-dev not allowed; use LITELLM_MASTER_KEY or api_tokens")
        return True
    # LiteLLM master key is also valid for Main Panel (single key unlocks all panels)
    litellm_master = os.getenv("LITELLM_MASTER_KEY", "")
    if litellm_master and token == litellm_master:
        return True
    conn=get_db()
    cur=conn.execute("SELECT 1 FROM api_tokens WHERE token=?", (token,))
    ok=cur.fetchone() is not None
    conn.close()
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

def verify_public_dashboard(request: Request):
    """Dependency for dashboard HTML when PUBLIC_MODE is on — checks query token or header."""
    if not PUBLIC_MODE:
        return True
    if not PUBLIC_REQUIRE_AUTH:
        return True
    # allow ?token=xxx for browser direct access
    tok = request.query_params.get("token") or request.headers.get("authorization","").replace("Bearer ","").strip()
    if not tok:
        # render login hint instead of 401 for GET /
        return False
    # reuse verify_token logic
    if tok in ("sk-local-dev", "local"):
        if PUBLIC_REQUIRE_AUTH and os.getenv("ALLOW_SK_LOCAL_IN_PUBLIC","0") not in ("1","true","yes","on"):
            return False
        return True
    litellm_master = os.getenv("LITELLM_MASTER_KEY", "")
    if litellm_master and tok == litellm_master:
        return True
    conn=get_db()
    cur=conn.execute("SELECT 1 FROM api_tokens WHERE token=?", (tok,))
    ok=cur.fetchone() is not None
    conn.close()
    return ok

# --------------------------------------------------------------------------
# Helpers: GPU, process
# --------------------------------------------------------------------------
def gpu_info():
    try:
        import subprocess, json
        out=subprocess.check_output(["nvidia-smi","--query-gpu=index,memory.used,memory.total,utilization.gpu","--format=csv,noheader,nounits"], text=True)
        gpus=[]
        for line in out.strip().splitlines():
            idx,used,total,util= [x.strip() for x in line.split(",")]
            gpus.append({"index":int(idx),"used_mib":int(used),"total_mib":int(total),"free_mib":int(total)-int(used),"util":int(util)})
        return gpus
    except Exception as e:
        return [{"error":str(e)}]

def pick_backend(model_id: str) -> Optional[str]:
    cfg = MODEL_REGISTRY.get(model_id)
    if not cfg: return None
    backs = cfg.get("backends", [])
    if not backs: return None
    # also accept aliases like gemma-4-31b-1 etc. map to base
    # round robin
    n = rr_counters.get(model_id,0)
    url = backs[n % len(backs)]
    rr_counters[model_id] = n+1
    return url

def _triton_promoted_backend(model_id: str) -> Optional[str]:
    """If Triton-optimized pool is live, promote gemma-4-31b to it (B -> A fallback)."""
    if model_id == "gemma-4-31b" or model_id.startswith("gemma-4-31b"):
        # prefer TRT-LLM (A) then vLLM (B) if they have backends
        for cand in ["gemma-4-31b-triton-trt", "gemma-4-31b-triton-vllm"]:
            b = pick_backend(cand)
            if b:
                # undo rr increment side-effect by peeking: pick_backend already rotated, revert one step not needed - just use it
                return b
    return None

async def proxy_chat(model_id: str, payload: dict):
    # Triton promotion: champion gemma routes to optimized Triton pool when available
    promoted = _triton_promoted_backend(model_id)
    if promoted:
        # short-circuit to optimized backend (preserves OpenAI shape)
        payload = dict(payload)
        cfg = MODEL_REGISTRY.get("gemma-4-31b-triton-trt" if "trt" in promoted else "gemma-4-31b-triton-vllm", {})
        backends = cfg.get("backends", [promoted])
        last_err = None
        for attempt_backend in [promoted] + [b for b in backends if b != promoted]:
            try:
                async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
                    r = await client.post(f"{attempt_backend}/v1/chat/completions", json=payload)
                    if r.status_code != 200:
                        raise HTTPException(status_code=r.status_code, detail=r.text)
                    return r.json()
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_err = f"optimized backend {attempt_backend} unreachable: {e}"
                continue
        # fallback to legacy gemma pool if optimized down
        pass
    # resolve alias: gemma-4-31b-1 -> gemma-4-31b
    base_id = model_id.split("-31b-")[0]+"-31b" if "-31b-" in model_id else model_id
    if base_id not in MODEL_REGISTRY and model_id in MODEL_REGISTRY:
        base_id = model_id
    backend = pick_backend(base_id) or pick_backend(model_id)
    if not backend:
        # try default gemma pool if unknown model
        if model_id.startswith("gemma"):
            backend = pick_backend("gemma-4-31b")
        if not backend:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not loaded. Available: {list(MODEL_REGISTRY.keys())} - use POST /admin/models/load to spawn")
    # rewrite model field to backend's expected id (strip alias)
    # backend expects its own model-id like gemma-4-31b-1 ; but we pass original
    payload = dict(payload)
    # ensure max_tokens etc — health-aware retry across backends
    cfg = MODEL_REGISTRY.get(base_id) or MODEL_REGISTRY.get(model_id) or {}
    backends = cfg.get("backends", [backend])
    last_err = None
    for attempt_backend in [backend] + [b for b in backends if b != backend]:
        try:
            async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
                r = await client.post(f"{attempt_backend}/v1/chat/completions", json=payload)
                if r.status_code!=200:
                    raise HTTPException(status_code=r.status_code, detail=r.text)
                return r.json()
        except httpx.ConnectError as e:
            last_err = f"backend {attempt_backend} unreachable: {e}"
            continue
        except httpx.ReadTimeout as e:
            last_err = f"backend {attempt_backend} timeout: {e}"
            continue
    raise HTTPException(status_code=502, detail=f"All backends for {model_id} unreachable. Tried {backends}. Last: {last_err}. Use POST /admin/models/load or check 8080-8084.")

# --------------------------------------------------------------------------
# API: models
# --------------------------------------------------------------------------
@app.get("/metrics", response_class=Response)
def metrics_prom():
    # minimal Prometheus exposition for manager — scraped by prometheus:9090
    lines=[]
    lines.append("# HELP manager_uptime_seconds Manager uptime")
    lines.append("# TYPE manager_uptime_seconds gauge")
    lines.append(f"manager_uptime_seconds {int(time.time()-START_TIME)}")
    lines.append("# HELP manager_models_loaded Number of loaded models (backends >0)")
    lines.append("# TYPE manager_models_loaded gauge")
    lines.append(f"manager_models_loaded {sum(1 for m in MODEL_REGISTRY.values() if m['backends'])}")
    lines.append("# HELP manager_models_live Number of models with at least one healthy backend")
    lines.append("# TYPE manager_models_live gauge")
    # live count from last probe not stored; compute via quick sync probe? use 0 for now
    lines.append(f"manager_models_live 0")
    # gpu
    for g in gpu_info():
        if "index" in g:
            lines.append(f'manager_gpu_used_mib{{gpu="{g["index"]}"}} {g["used_mib"]}')
            lines.append(f'manager_gpu_util{{gpu="{g["index"]}"}} {g["util"]}')
    return Response(content="\n".join(lines)+"\n", media_type="text/plain")

@app.get("/health")
def health():
    return {"status":"ok","manager":"llm_inference_manager","version":"1.0.0","uptime_sec": int(time.time()-START_TIME), "gpus":gpu_info(),"models_loaded": sum(1 for m in MODEL_REGISTRY.values() if m["backends"]) }

@app.get("/v1/models")
def list_models():
    data=[]
    for mid, cfg in MODEL_REGISTRY.items():
        data.append({
            "id": mid,
            "object": "model",
            "created": 0,
            "owned_by": cfg["creator"],
            "meta": {
                "name": cfg["name"],
                "family": cfg["family"],
                "params": cfg["params"],
                "size_gb": cfg["size_gb"],
                "quant": cfg["quant"],
                "context": cfg.get("context"),
                "benchmark_mean": cfg.get("benchmark_mean"),
                "status": cfg.get("status"),
                "backends": cfg.get("backends"),
                "path": cfg.get("path"),
            }
        })
    return {"object":"list","data":data}

@app.get("/v1/models/{model_id}")
def get_model(model_id: str):
    cfg=MODEL_REGISTRY.get(model_id)
    if not cfg:
        raise HTTPException(404, "model not found")
    return {"id":model_id,"object":"model","owned_by":cfg["creator"],"meta":cfg,"backends":cfg.get("backends"),"gpus":gpu_info()}

# --------------------------------------------------------------------------
# OpenAI-compatible chat
# --------------------------------------------------------------------------
class ChatReq(BaseModel):
    model: str = Field(default="gemma-4-31b")
    messages: List[Dict[str, Any]]
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    session_id: Optional[str] = None

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatReq, authorized=Depends(verify_token)):
    start=time.time()
    # session handling: inject full history if session_id provided
    sid = req.session_id
    history_messages = []
    if sid:
        conn=get_db()
        # ensure session exists
        cur=conn.execute("SELECT id FROM chat_sessions WHERE id=?", (sid,))
        if not cur.fetchone():
            conn.execute("INSERT INTO chat_sessions(id,model,title,created_at,updated_at) VALUES(?,?,?,?,?)", (sid, req.model, req.messages[-1].get("content","")[:40], datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
            conn.commit()
        # fetch prior history
        rows=conn.execute("SELECT role,content FROM messages WHERE session_id=? ORDER BY created_at", (sid,)).fetchall()
        history_messages=[{"role":r[0],"content":r[1]} for r in rows]
        # save current user message
        conn.execute("INSERT INTO messages(id,session_id,role,content,created_at) VALUES(?,?,?,?,?)", (str(uuid.uuid4()), sid, "user", req.messages[-1].get("content",""), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
    # merge history + current turn (current turn already in req.messages[-1], but history contains prior turns)
    all_messages = history_messages + req.messages if sid else req.messages
    payload = {"model": req.model, "messages": all_messages, "max_tokens": req.max_tokens, "temperature": req.temperature}
    try:
        out = await proxy_chat(req.model, payload)
    except Exception as e:
        latency = (time.time()-start)*1000
        try:
            conn=get_db()
            conn.execute("INSERT INTO metrics(id,model,endpoint,latency_ms,prompt_tokens,completion_tokens,created_at,status,finish_reason,panel,trace_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), req.model, "/v1/chat/completions", latency, 0,0,datetime.utcnow().isoformat(),"error", str(e)[:120], "llm", None))
            conn.commit(); conn.close()
        except: pass
        raise HTTPException(status_code=502, detail=str(e)[:500])
    latency = (time.time()-start)*1000
    # save assistant
    if sid:
        try:
            content = out["choices"][0]["message"]["content"]
            conn=get_db()
            conn.execute("INSERT INTO messages(id,session_id,role,content,created_at) VALUES(?,?,?,?,?)", (str(uuid.uuid4()), sid, "assistant", content, datetime.utcnow().isoformat()))
            conn.execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (datetime.utcnow().isoformat(), sid))
            conn.commit()
            conn.close()
        except: pass
    # metrics – tag success with finish_reason + trace_id if supplied
    try:
        finish = out.get("choices",[{}])[0].get("finish_reason") if isinstance(out, dict) else "stop"
        status = "success" if finish in ("stop","length") else ("blocked" if finish=="content_filter" else "success")
        # map finish to status
        if finish == "content_filter": status = "blocked"
        elif finish and finish != "stop": status = "error"
        trace_id = out.get("id") if isinstance(out, dict) else None
        conn=get_db()
        conn.execute("INSERT INTO metrics(id,model,endpoint,latency_ms,prompt_tokens,completion_tokens,created_at,status,finish_reason,panel,trace_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), req.model, "/v1/chat/completions", latency, 0, 0, datetime.utcnow().isoformat(), status, finish, "llm", trace_id))
        conn.commit()
        conn.close()
    except: pass
    # inject latency header
    return JSONResponse(out, headers={"X-Manager-Latency-ms": str(int(latency))})

@app.post("/v1/completions")
async def completions(request: Request, authorized=Depends(verify_token)):
    body = await request.json()
    model = body.get("model","gemma-4-31b")
    prompt = body.get("prompt","")
    payload = {"messages":[{"role":"user","content":prompt}], "max_tokens": body.get("max_tokens",256), "temperature": body.get("temperature",0.7), "model": model}
    out = await proxy_chat(model, payload)
    # convert to completions shape
    return {"id": out.get("id","cmpl-local"), "object":"text_completion","model":model, "choices":[{"text": out["choices"][0]["message"]["content"], "index":0, "finish_reason":"stop"}]}

@app.post("/v1/embeddings")
async def embeddings_proxy(request: Request, authorized=Depends(verify_token)):
    body = await request.json()
    # try local embed 8001 via trust_env=False, fallback to litellm if configured
    for target in ["http://127.0.0.1:8001/v1/embeddings", LITELLM_URL.rstrip("/")+"/v1/embeddings"]:
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                # forward auth if litellm
                headers = {}
                if "4000" in target:
                    mk = os.getenv("LITELLM_MASTER_KEY", "")
                    if mk:
                        headers["Authorization"] = f"Bearer {mk}"
                r = await c.post(target, json=body, headers=headers)
                if r.status_code == 200:
                    return JSONResponse(content=r.json(), status_code=200)
                # if 404 try next
                if r.status_code in (404, 501):
                    continue
                return JSONResponse(content=r.json() if "json" in r.headers.get("content-type","") else {"error": r.text[:800]}, status_code=r.status_code)
        except Exception as e:
            last_err = str(e)[:400]
            continue
    raise HTTPException(status_code=502, detail=f"embeddings upstream unreachable (tried 8001 and litellm): {last_err}")

# --------------------------------------------------------------------------
# Sessions / history
# --------------------------------------------------------------------------
@app.get("/v1/sessions")
def list_sessions():
    conn=get_db()
    rows=conn.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT 50").fetchall()
    conn.close()
    return {"object":"list","data":[dict(r) for r in rows]}

@app.get("/v1/sessions/{sid}")
def get_session(sid: str):
    conn=get_db()
    sess=conn.execute("SELECT * FROM chat_sessions WHERE id=?", (sid,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(404,"session not found")
    msgs=conn.execute("SELECT role,content,created_at FROM messages WHERE session_id=? ORDER BY created_at", (sid,)).fetchall()
    conn.close()
    return {"session": dict(sess), "messages":[dict(m) for m in msgs]}

@app.delete("/v1/sessions/{sid}")
def delete_session(sid: str):
    conn=get_db()
    conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    conn.execute("DELETE FROM chat_sessions WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return {"status":"deleted"}

@app.post("/v1/sessions")
def create_session(model: str = "gemma-4-31b", title: str = "New chat"):
    sid=str(uuid.uuid4())
    conn=get_db()
    conn.execute("INSERT INTO chat_sessions(id,model,title,created_at,updated_at) VALUES(?,?,?,?,?)", (sid,model,title,datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {"id": sid, "model": model, "title": title}

# --------------------------------------------------------------------------
# Admin: load / unload / status
# --------------------------------------------------------------------------
@app.get("/admin/status")
def admin_status():
    return {"gpus": gpu_info(), "registry": {k: {"status":v["status"],"backends":v["backends"],"size_gb":v["size_gb"]} for k,v in MODEL_REGISTRY.items()}, "spawned": list(spawned_processes.keys())}

@app.get("/admin/metrics")
def admin_metrics():
    conn=get_db()
    rows=conn.execute("SELECT model, count(*) as cnt, avg(latency_ms) as avg_ms FROM metrics GROUP BY model").fetchall()
    recent=conn.execute("SELECT * FROM metrics ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
    return {"by_model":[dict(r) for r in rows], "recent":[dict(r) for r in recent]}

def find_next_port(start=8085):
    import socket
    for p in range(start, 8100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p))!=0:
                # also check not in registry
                used = []
                for cfg in MODEL_REGISTRY.values():
                    for b in cfg["backends"]:
                        try: used.append(int(b.split(":")[-1]))
                        except: pass
                if p not in used:
                    return p
    return 8099

@app.post("/admin/models/load")
def admin_load(model_id: str, port: Optional[int]=None, n_ctx: int=8192):
    cfg=MODEL_REGISTRY.get(model_id)
    if not cfg:
        raise HTTPException(404,"unknown model")
    if cfg["backends"]:
        return {"status":"already loaded","backends":cfg["backends"]}
    path = ROOT / cfg["path"]
    if not path.exists():
        # try find actual gguf file if path is dir
        if path.is_dir():
            cand=list(path.glob("*.gguf"))
            if cand: path=cand[0]
            else: raise HTTPException(400, f"model path not found: {path}")
        else:
            raise HTTPException(400, f"model file not found: {path}")
    port = port or find_next_port()
    # pick GPU
    gpus=gpu_info()
    if gpus and "free_mib" in gpus[0]:
        gpus_sorted=sorted(gpus, key=lambda x: x["free_mib"], reverse=True)
        gpu=gpus_sorted[0]["index"]
    else:
        gpu=0
    logfile = LOG_DIR / f"llama_server_{port}.log"
    cmd = [f"{ROOT}/offline-prep/venv/bin/python3.12", f"{ROOT}/scripts/services/llama_chat_server.py", "--model", str(path), "--port", str(port), "--model-id", model_id, "--n-ctx", str(n_ctx)]
    env=os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"]=str(gpu)
    proc = subprocess.Popen(cmd, env=env, stdout=open(logfile,"ab"), stderr=subprocess.STDOUT)
    spawned_processes[model_id]=proc
    cfg["backends"]=[f"http://127.0.0.1:{port}"]
    cfg["status"]="loading"
    # wait a bit for health
    import time as _t
    _t.sleep(2)
    return {"status":"spawned","model":model_id,"port":port,"gpu":gpu,"pid":proc.pid,"log":str(logfile)}

@app.post("/admin/models/unload")
def admin_unload(model_id: str):
    cfg=MODEL_REGISTRY.get(model_id)
    if not cfg: raise HTTPException(404,"unknown")
    proc=spawned_processes.pop(model_id, None)
    if proc:
        try: proc.terminate()
        except: pass
    cfg["backends"]=[]
    cfg["status"]="available"
    return {"status":"unloaded","model":model_id}

@app.get("/admin/triton/status")
async def triton_status():
    out={}
    for name, url in [("triton","http://127.0.0.1:8004"),("triton_vllm","http://127.0.0.1:8104"),("triton_trt","http://127.0.0.1:8105")]:
        try:
            async with httpx.AsyncClient(timeout=2, trust_env=False) as c:
                r=await c.get(f"{url}/health" if "8104" in url else f"{url}/v2/health/ready")
                out[name]={"url":url,"code":r.status_code,"ok":r.status_code==200,"body":r.text[:500]}
        except Exception as e:
            out[name]={"url":url,"ok":False,"error":str(e)[:300]}
    out["registry"]={k:{"backends":v.get("backends"),"status":v.get("status"),"backend_type":v.get("backend_type")} for k,v in MODEL_REGISTRY.items() if "triton" in k}
    out["champion_promoted"] = bool(MODEL_REGISTRY.get("gemma-4-31b-triton-vllm",{}).get("backends") or MODEL_REGISTRY.get("gemma-4-31b-triton-trt",{}).get("backends"))
    return out

@app.post("/admin/triton/promote")
def triton_promote(backend: str = "vllm", url: str = "http://127.0.0.1:8104"):
    # promote gemma-4-31b -> triton optimized backend. backend=vllm|trt
    key = "gemma-4-31b-triton-vllm" if backend=="vllm" else "gemma-4-31b-triton-trt"
    cfg = MODEL_REGISTRY.get(key)
    if not cfg:
        raise HTTPException(404, "triton model not in registry")
    cfg["backends"]=[url]
    cfg["status"]="loaded"
    return {"status":"promoted","model":key,"url":url,"note":"gemma-4-31b now routes via _triton_promoted_backend to this optimized pool"}

@app.post("/admin/triton/demote")
def triton_demote():
    for key in ["gemma-4-31b-triton-vllm","gemma-4-31b-triton-trt"]:
        cfg=MODEL_REGISTRY.get(key)
        if cfg:
            cfg["backends"]=[]
            cfg["status"]="available"
    return {"status":"demoted","note":"gemma-4-31b falls back to legacy 18000 pool"}

@app.get("/admin/tokens")
def list_tokens():
    conn=get_db()
    rows=conn.execute("SELECT token,name,created_at FROM api_tokens").fetchall()
    conn.close()
    return {"data":[dict(r) for r in rows]}

# --------------------------------------------------------------------------
# Frontend helpers - simple chat UI
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Dashboard — comprehensive webapp
# --------------------------------------------------------------------------
import glob as _glob

def _project_structure():
    import os
    root = ROOT
    # minimal tree for dashboard
    items = []
    for sub in ["scripts","scripts/services","deploy","llm_inference_manager","offline-prep/models/huggingface","docs/reports","e2e-test","rag_storage","logs"]:
        pp = root / sub
        try:
            files = list(pp.iterdir()) if pp.exists() else []
            items.append({"path": sub, "exists": pp.exists(), "count": len(files), "files": [f.name for f in sorted(files)[:20]]})
        except Exception as e:
            items.append({"path": sub, "exists": False, "error": str(e)})
    return items

def _docker_status():
    try:
        out = subprocess.check_output(["docker","ps","--format","{{.Names}}|{{.Status}}|{{.Ports}}"], text=True, timeout=5)
        rows=[]
        for line in out.strip().splitlines():
            if not line.strip(): continue
            parts=line.split("|")
            rows.append({"name":parts[0],"status":parts[1] if len(parts)>1 else "","ports":parts[2] if len(parts)>2 else ""})
        return rows
    except Exception as e:
        return [{"error":str(e)}]

async def _embed_status():
    import asyncio
    results=[]
    for port, mid in [(8001,"multilingual-e5-small"),(8002,"bge-m3"),(8003,"paraphrase-multilingual-minilm")]:
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as c:
                r=await c.get(f"http://127.0.0.1:{port}/health")
                j=r.json() if r.status_code==200 else {"error":r.text[:200]}
                j["port"]=port; j["model_id"]=mid
                # also try embeddings
                try:
                    r2=await c.post(f"http://127.0.0.1:{port}/v1/embeddings", json={"input":"test"})
                    if r2.status_code==200:
                        j["embed_ok"]=True
                        j["embed_dim"]=len(r2.json()["data"][0]["embedding"])
                except: pass
                results.append(j)
        except Exception as e:
            results.append({"port":port,"model_id":mid,"error":str(e)[:200]})
    return results

def _disk_models():
    try:
        mdir = ROOT / "offline-prep/models/huggingface"
        if not mdir.exists(): return []
        rows=[]
        import subprocess
        out=subprocess.check_output(["du","-sh",str(mdir / "*")], text=True, shell=True)
        for line in out.strip().splitlines():
            sz, path = line.split("\t")
            rows.append({"size":sz,"path":path.split("/")[-1]})
        return rows
    except Exception as e:
        return [{"error":str(e)}]

# --- Unified Panel helpers (LiteLLM + panel probes) ---
async def _probe_one(panel: str, timeout: float = 2.0) -> dict:
    base = PANEL_UPSTREAMS.get(panel, "")
    health_path = PANEL_HEALTH_PATH.get(panel, "/health")
    url = base.rstrip("/") + health_path
    try:
        headers={}
        if panel=="litellm":
            mk=os.getenv("LITELLM_MASTER_KEY","")
            if mk:
                headers["Authorization"]=f"Bearer {mk}"
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
            r = await c.get(url, headers=headers)
            body = ""
            try:
                body = r.json()
            except:
                body = r.text[:400]
            return {"panel": panel, "url": url, "status": "ok" if r.status_code == 200 else f"http_{r.status_code}", "code": r.status_code, "body": body}
    except Exception as e:
        return {"panel": panel, "url": url, "status": "error", "error": str(e)[:300]}

async def _probe_panels(timeout: float = 2.0) -> dict:
    import asyncio
    tasks = [_probe_one(p, timeout) for p in PANEL_UPSTREAMS]
    results = await asyncio.gather(*tasks)
    return {r["panel"]: r for r in results}

async def _litellm_status(timeout: float = 3.0) -> dict:
    base = LITELLM_URL.rstrip("/")
    out: dict = {"url": base, "health": None, "models": None, "model_info": None, "error": None}
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
            try:
                hk = {}
                mk0 = os.getenv("LITELLM_MASTER_KEY", "")
                if mk0:
                    hk["Authorization"] = f"Bearer {mk0}"
                r = await c.get(f"{base}/health", headers=hk)
                try:
                    body = r.json()
                except:
                    body = r.text[:600]
                out["health"] = {"code": r.status_code, "body": body}
            except Exception as e:
                out["health"] = {"error": str(e)[:300]}
            # models list (needs auth if LITELLM_MASTER_KEY set)
            try:
                headers = {}
                mk = os.getenv("LITELLM_MASTER_KEY", "")
                if mk:
                    headers["Authorization"] = f"Bearer {mk}"
                r2 = await c.get(f"{base}/v1/models", headers=headers)
                try:
                    out["models"] = r2.json()
                except:
                    out["models"] = {"raw": r2.text[:2000], "code": r2.status_code}
            except Exception as e:
                out["models"] = {"error": str(e)[:300]}
            # optional model_info (litellm admin)
            try:
                headers = {}
                mk = os.getenv("LITELLM_MASTER_KEY", "")
                if mk:
                    headers["Authorization"] = f"Bearer {mk}"
                r3 = await c.get(f"{base}/model/info", headers=headers)
                if r3.status_code == 200:
                    try:
                        out["model_info"] = r3.json()
                    except:
                        out["model_info"] = {"raw": r3.text[:4000]}
            except:
                pass
    except Exception as e:
        out["error"] = str(e)[:300]
    return out

@app.get("/api/dashboard")
async def api_dashboard():
    # aggregate everything for dashboard
    gpus = gpu_info()
    # model details with live health probe for loaded ones (parallel)
    async def _probe_backend(url: str):
        try:
            async with httpx.AsyncClient(timeout=2, trust_env=False) as c:
                r = await c.get(f"{url}/health")
                return {"backend": url, "status": r.status_code, "body": r.json() if r.status_code==200 else r.text[:200]}
        except Exception as e:
            return {"backend": url, "status": "error", "error": str(e)[:200]}
    models=[]
    for mid, cfg in MODEL_REGISTRY.items():
        entry=dict(cfg)
        # probe backends if loaded (gather)
        health=[]
        if cfg.get("backends"):
            health = await __import__("asyncio").gather(*[_probe_backend(b) for b in cfg["backends"]])
            health = list(health)
        entry["live_health"]=health
        entry["live_ok"] = sum(1 for h in health if h.get("status")==200)
        # check file exists
        p = ROOT / cfg["path"]
        entry["path_exists"]=p.exists()
        if p.is_dir():
            try: entry["path_files"]=len(list(p.glob("*.gguf")))+len(list(p.glob("*.safetensors")))
            except: pass
        models.append(entry)
    docker=_docker_status()
    embeds=await _embed_status()
    disk=_disk_models()
    proj=_project_structure()
    # metrics
    try:
        conn=get_db()
        by_model=conn.execute("SELECT model, count(*) as cnt, avg(latency_ms) as avg_ms FROM metrics GROUP BY model").fetchall()
        recent=conn.execute("SELECT model,endpoint,latency_ms,created_at FROM metrics ORDER BY created_at DESC LIMIT 10").fetchall()
        sessions=conn.execute("SELECT id,model,title,updated_at FROM chat_sessions ORDER BY updated_at DESC LIMIT 10").fetchall()
        tokens=conn.execute("SELECT token,name,created_at FROM api_tokens").fetchall()
        conn.close()
        metrics={"by_model":[dict(r) for r in by_model], "recent":[dict(r) for r in recent], "sessions":[dict(r) for r in sessions], "tokens":[dict(r) for r in tokens]}
    except Exception as e:
        metrics={"error":str(e)}
    live_loaded = sum(1 for m in models if m.get("live_ok",0)>0)
    return {
        "manager":{"version":"1.0.0","uptime_sec": int(time.time()-START_TIME), "uptime": int(time.time()-START_TIME), "gpus": gpus, "models_loaded": sum(1 for m in MODEL_REGISTRY.values() if m["backends"]), "models_live": live_loaded},
        "models": models,
        "docker": docker,
        "embeds": embeds,
        "disk": disk,
        "project": proj,
        "metrics": metrics,
        "proxy": {"PROXY_URL": os.environ.get("HTTP_PROXY",""), "no_proxy": os.environ.get("no_proxy","")},
        "paths": {"root": str(ROOT), "venv": str(ROOT/"offline-prep/venv"), "models_dir": str(ROOT/"offline-prep/models/huggingface")},
        "benchmarks": {"logs": [f.name for f in (ROOT/"logs").glob("evalp*.json")] if (ROOT/"logs").exists() else [], "plots": [f.name for f in (ROOT/"docs/reports").glob("*.png")] if (ROOT/"docs/reports").exists() else []}
    }

@app.get("/api/project")
def api_project():
    return {"structure": _project_structure(), "disk": _disk_models(), "docker": _docker_status()}

def _pct(vals, p):
    if not vals: return None
    vals = sorted(vals)
    k = (len(vals)-1)*p/100
    f = int(k); c = min(f+1, len(vals)-1)
    d = k-f
    return round(vals[f]*(1-d)+vals[c]*d, 1) if len(vals)>1 else round(vals[0],1)

@app.get("/api/usage")
def api_usage():
    conn=get_db()
    rows=conn.execute("SELECT model, count(*) as cnt, avg(latency_ms) as avg_ms, max(latency_ms) as max_ms FROM metrics GROUP BY model").fetchall()
    recent=conn.execute("SELECT * FROM metrics ORDER BY created_at DESC LIMIT 30").fetchall()
    # percentiles per model
    by = []
    for r in rows:
        d=dict(r)
        vals=[x[0] for x in conn.execute("SELECT latency_ms FROM metrics WHERE model=? ORDER BY latency_ms", (d["model"],)).fetchall()]
        d["p50_ms"]= _pct(vals,50)
        d["p95_ms"]= _pct(vals,95)
        d["p99_ms"]= _pct(vals,99)
        d["min_ms"]= min(vals) if vals else None
        by.append(d)
    conn.close()
    return {"by_model":by, "recent":[dict(r) for r in recent]}

@app.get("/api/metrics/percentiles")
def api_percentiles(model: str = None, hours: int = 24):
    import datetime as _dt
    conn=get_db()
    q = "SELECT model, latency_ms FROM metrics WHERE created_at >= datetime('now', ?)"
    param = f"-{hours} hours"
    if model:
        q += " AND model=?"
        rows=conn.execute(q, (param, model)).fetchall()
    else:
        rows=conn.execute(q, (param,)).fetchall()
    conn.close()
    from collections import defaultdict
    groups=defaultdict(list)
    for m, lat in rows:
        groups[m].append(lat)
    out={}
    for m, vals in groups.items():
        out[m]={"cnt":len(vals),"avg_ms": round(sum(vals)/len(vals),1) if vals else 0, "p50_ms": _pct(vals,50), "p95_ms": _pct(vals,95), "p99_ms": _pct(vals,99), "min_ms": min(vals) if vals else None, "max_ms": max(vals) if vals else None}
    return {"hours":hours, "by_model": out}

@app.get("/api/metrics/histogram")
def api_histogram(model: str = None, buckets: int = 20, status: str = None, hours: int = 24):
    conn=get_db()
    # support status + hours filtering
    q="SELECT latency_ms FROM metrics WHERE created_at >= datetime('now', ?)"
    params=[f"-{hours} hours"]
    if model:
        q+=" AND model=?"
        params.append(model)
    if status:
        q+=" AND status=?"
        params.append(status)
    q+=" ORDER BY latency_ms"
    vals=[x[0] for x in conn.execute(q, tuple(params)).fetchall()]
    conn.close()
    if not vals:
        return {"buckets": [], "counts": [], "counts_pct": [], "p50_ms": None, "p95_ms": None, "p99_ms": None, "total": 0}
    mn, mx = min(vals), max(vals)
    total=len(vals)
    if mx==mn:
        return {"buckets":[mn], "counts":[total], "counts_pct":[100.0], "p50_ms": _pct(vals,50), "p95_ms": _pct(vals,95), "p99_ms": _pct(vals,99), "min_ms": mn, "max_ms": mx, "total": total}
    step=(mx-mn)/buckets
    hist=[0]*buckets
    edges=[round(mn+i*step,1) for i in range(buckets+1)]
    for v in vals:
        idx=min(int((v-mn)/step), buckets-1)
        hist[idx]+=1
    pct=[round(c/total*100,1) for c in hist]
    return {"model": model, "status": status, "hours": hours, "buckets": edges, "counts": hist, "counts_pct": pct, "p50_ms": _pct(vals,50), "p95_ms": _pct(vals,95), "p99_ms": _pct(vals,99), "min_ms": mn, "max_ms": mx, "total": total}

@app.get("/api/metrics/timeseries")
def api_timeseries(hours: int = 24, bucket_min: int = 60, group_by: str = None):
    import datetime as _dt
    conn=get_db()
    # include status for stacked view
    try:
        rows=conn.execute("SELECT created_at, latency_ms, model, status FROM metrics WHERE created_at >= datetime('now', ?) ORDER BY created_at", (f"-{hours} hours",)).fetchall()
    except:
        rows=conn.execute("SELECT created_at, latency_ms, model FROM metrics WHERE created_at >= datetime('now', ?) ORDER BY created_at", (f"-{hours} hours",)).fetchall()
        rows=[(r[0],r[1],r[2],None) for r in rows]
    conn.close()
    from collections import defaultdict
    buckets=defaultdict(list)
    buckets_status=defaultdict(lambda: defaultdict(list))
    for ts, lat, model, status in rows:
        try:
            dt=_dt.datetime.fromisoformat(ts)
        except:
            continue
        key=dt.strftime("%Y-%m-%dT%H:%M" if bucket_min<=60 else "%Y-%m-%dT%H:00")
        buckets[key].append(lat)
        # group by status for stacked
        s=status or "success"
        buckets_status[key][s].append(lat)
        if group_by=="model":
            buckets_status[key][model].append(lat)
    series=[]
    for k in sorted(buckets.keys()):
        v=buckets[k]
        entry={"t":k, "avg_ms": round(sum(v)/len(v),1), "cnt": len(v), "p95_ms": _pct(v,95), "p50_ms": _pct(v,50)}
        # add per-status counts
        for st in ["success","blocked","error"]:
            entry[f"{st}_cnt"] = len(buckets_status[k].get(st,[]))
        series.append(entry)
    return {"hours":hours, "bucket_min": bucket_min, "group_by": group_by, "series": series}

@app.get("/api/transparency")
async def api_transparency(query: str, top_k: int = 5, keyword_boost: float = None):
    """Unified transparency: KB search + OTEL trace join, with per-stage percentages."""
    import time as _t
    start=_t.monotonic()
    # fetch KB search with stage timings
    kb_url = PANEL_UPSTREAMS.get("kb","http://127.0.0.1:8000").rstrip("/") + "/search/api"
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as c:
            r=await c.post(kb_url, json={"query": query, "top_k": top_k, "keyword_boost": keyword_boost} if keyword_boost is not None else {"query": query, "top_k": top_k})
            kb_data=r.json() if r.status_code==200 else {"error": r.text[:800], "code": r.status_code}
    except Exception as e:
        kb_data={"error": str(e)[:500]}
    # compute stages from stage_ms if present
    stage_ms = kb_data.get("stage_ms", {}) if isinstance(kb_data, dict) else {}
    total = kb_data.get("elapsed_ms", 0) or sum(v for v in stage_ms.values() if isinstance(v, (int,float))) or 1
    percentages = {k: round(v/total*100,1) if total else 0 for k,v in stage_ms.items()}
    # build diagram stages list
    order = ["bm25","dense","hyde","rrf","rerank","build_context","total"]
    stages=[]
    for name in order:
        ms = stage_ms.get(name)
        if ms is None: continue
        status="ok"
        if name=="hyde" and ms==0: status="skipped"
        stages.append({"name": name, "status": status, "elapsed_ms": ms, "percent": percentages.get(name,0)})
    # try fetch OTEL trace for this query if request_id in kb_data or recent trace
    otel_spans=[]
    try:
        # use recent trace list to find spans for this query (best-effort)
        async with httpx.AsyncClient(timeout=3, trust_env=False) as c:
            tr=await c.get(PANEL_UPSTREAMS.get("trace","http://127.0.0.1:3000").rstrip("/") + "/api/observe/requests?limit=5")
            if tr.status_code==200:
                j=tr.json()
                # pick latest
                rec = (j.get("data") or j) if isinstance(j, dict) else j
                if isinstance(rec, list) and rec:
                    rid = rec[0].get("request_id") if isinstance(rec[0], dict) else None
                    if rid:
                        tr2=await c.get(PANEL_UPSTREAMS.get("trace","http://127.0.0.1:3000").rstrip("/") + f"/api/observe/timeline/{rid}")
                        if tr2.status_code==200:
                            otel_spans=tr2.json().get("spans", []) if isinstance(tr2.json(), dict) else []
    except: pass
    return {
        "query": kb_data.get("query", query),
        "normalized_query": kb_data.get("normalized_query", query),
        "tokens": kb_data.get("tokens", []),
        "total_chunks_indexed": kb_data.get("total_chunks_indexed", 0),
        "config": kb_data.get("config", {}),
        "stage_ms": stage_ms,
        "percentages": percentages,
        "stages": stages,
        "total_elapsed_ms": total,
        "bm25_results": kb_data.get("bm25_results", [])[:3],
        "dense_results": kb_data.get("dense_results", [])[:3],
        "merged_candidates": kb_data.get("merged_candidates", [])[:3],
        "final_results": kb_data.get("final_results", []),
        "elapsed_ms": kb_data.get("elapsed_ms", 0),
        "rerank_ms": kb_data.get("rerank_ms", 0),
        "otel_spans": otel_spans[:20],
        "raw": kb_data if len(str(kb_data))<5000 else None,
        "server_elapsed_ms": round((_t.monotonic()-start)*1000,1)
    }

@app.get("/api/spans")
async def api_spans(request_id: str, limit: int = 20):
    """Proxy to Jaeger / trace timeline – normalized spans."""
    # try Jaeger first
    try:
        async with httpx.AsyncClient(timeout=4, trust_env=False) as c:
            jr=await c.get(PANEL_UPSTREAMS.get("jaeger","http://127.0.0.1:16686").rstrip("/") + f"/api/traces/{request_id}")
            if jr.status_code==200:
                j=jr.json()
                # Jaeger format: data[0].spans
                if isinstance(j, dict) and j.get("data"):
                    spans=j["data"][0].get("spans", [])
                    out=[]
                    for s in spans[:limit]:
                        out.append({"id": s.get("spanID"), "name": s.get("operationName"), "service": s.get("process",{}).get("serviceName"), "duration_us": s.get("duration"), "startTime": s.get("startTime")})
                    if out: return {"request_id": request_id, "source": "jaeger", "spans": out}
    except: pass
    # fallback to trace collector
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as c:
            r=await c.get(PANEL_UPSTREAMS.get("trace","http://127.0.0.1:3000").rstrip("/") + f"/api/observe/timeline/{request_id}")
            if r.status_code==200:
                j=r.json()
                spans=j.get("spans", []) if isinstance(j, dict) else []
                return {"request_id": request_id, "source": "trace", "timeline": j, "spans": spans[:limit]}
            return {"request_id": request_id, "error": r.text[:400], "code": r.status_code}
    except Exception as e:
        return {"request_id": request_id, "error": str(e)[:300]}

@app.get("/api/metrics/summary")
def api_metrics_summary(hours: int = 24):
    """Global summary: total, by_status, by_model, by_panel, success rates."""
    conn=get_db()
    # ensure status column exists
    try:
        rows=conn.execute("SELECT status, count(*) as cnt FROM metrics WHERE created_at >= datetime('now', ?) GROUP BY status", (f"-{hours} hours",)).fetchall()
        by_status={r[0] or "unknown": r[1] for r in rows}
    except:
        by_status={}
    try:
        rows=conn.execute("SELECT model, count(*) as cnt FROM metrics WHERE created_at >= datetime('now', ?) GROUP BY model", (f"-{hours} hours",)).fetchall()
        by_model={r[0]: r[1] for r in rows}
    except:
        by_model={}
    try:
        total=conn.execute("SELECT count(*) FROM metrics WHERE created_at >= datetime('now', ?)", (f"-{hours} hours",)).fetchone()[0]
    except:
        total=0
    # percentiles per model
    summary_by_model={}
    for m in by_model:
        vals=[x[0] for x in conn.execute("SELECT latency_ms FROM metrics WHERE model=? AND created_at >= datetime('now', ?)", (m, f"-{hours} hours")).fetchall()]
        if vals:
            summary_by_model[m]={"cnt": len(vals), "p50": _pct(vals,50), "p95": _pct(vals,95), "p99": _pct(vals,99), "avg": round(sum(vals)/len(vals),1)}
    conn.close()
    success = by_status.get("success",0)
    blocked = by_status.get("blocked",0)
    error = by_status.get("error",0)
    total_status = sum(by_status.values()) or 1
    return {"hours": hours, "total": total, "by_status": by_status, "by_model": by_model, "summary_by_model": summary_by_model, "success_rate": round(success/total_status,3), "blocked_rate": round(blocked/total_status,3), "error_rate": round(error/total_status,3)}

@app.get("/api/panels/health")
async def api_panels_health():
    return await _probe_panels()

@app.get("/api/litellm/health")
async def api_litellm_health():
    return await _litellm_status()

@app.get("/api/litellm/models")
async def api_litellm_models():
    st = await _litellm_status()
    return st.get("models") or {"error": "no models", "litellm": st}

@app.get("/api/litellm/spend")
async def api_litellm_spend():
    base = LITELLM_URL.rstrip("/")
    mk = os.getenv("LITELLM_MASTER_KEY", "")
    headers = {"Authorization": f"Bearer {mk}"} if mk else {}
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
            r = await c.get(f"{base}/spend/logs", headers=headers)
            if r.status_code == 200:
                try:
                    return r.json()
                except:
                    return {"raw": r.text[:6000]}
            # fallback to global spend
            r2 = await c.get(f"{base}/global/spend/logs", headers=headers)
            if r2.status_code == 200:
                try:
                    return r2.json()
                except:
                    return {"raw": r2.text[:6000]}
            return {"error": f"spend endpoint {r.status_code}", "body": r.text[:800]}
    except Exception as e:
        return {"error": str(e)[:500]}

@app.get("/api/unified")
async def api_unified():
    panels = await _probe_panels()
    litellm = await _litellm_status()
    dash = await api_dashboard()
    return {"manager": dash["manager"], "models": dash["models"], "panels": panels, "litellm": litellm, "embeds": dash["embeds"], "docker": dash["docker"], "disk": dash["disk"], "project": dash["project"], "metrics": dash["metrics"]}

@app.api_route("/panel/{panel}", methods=["GET","POST","PUT","PATCH","DELETE","HEAD","OPTIONS"])
@app.api_route("/panel/{panel}/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","HEAD","OPTIONS"])
async def panel_proxy(panel: str, request: Request, path: str = ""):
    upstream = PANEL_UPSTREAMS.get(panel)
    if not upstream:
        raise HTTPException(status_code=404, detail=f"unknown panel {panel}. known: {list(PANEL_UPSTREAMS.keys())}")
    # strip hop-by-hop headers, forward auth if present
    target = upstream.rstrip("/") + ("/" + path if path else "")
    # preserve query string
    qs = str(request.url.query)
    if qs:
        target += "?" + qs
    # forward headers (keep Authorization, Content-Type)
    headers = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in ("host","connection","keep-alive","proxy-connection","transfer-encoding","content-length"):
            continue
        headers[k] = v
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=True) as c:
            r = await c.request(request.method, target, headers=headers, content=body)
            # filter response headers + strip iframe blockers
            resp_headers = {}
            for hk, hv in r.headers.items():
                lk = hk.lower()
                if lk in ("connection","keep-alive","transfer-encoding","content-encoding","content-length","x-frame-options","x-content-type-options"):
                    continue
                if lk == "content-security-policy" and "frame-ancestors" in hv.lower():
                    continue
                resp_headers[hk] = hv
            # allow embedding in manager :9000 (public 192.168.96.82)
            resp_headers["Content-Security-Policy"] = "frame-ancestors 'self' http://127.0.0.1:9000 http://192.168.96.82:9000 http://192.168.177.10:9000 http://localhost:9000"
            media = r.headers.get("content-type", "application/octet-stream")
            if "application/json" in media:
                try:
                    return JSONResponse(content=r.json(), status_code=r.status_code, headers=resp_headers)
                except:
                    return Response(content=r.content, status_code=r.status_code, headers=resp_headers, media_type=media)
            return Response(content=r.content, status_code=r.status_code, headers=resp_headers, media_type=media)
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"panel {panel} upstream unreachable: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"panel proxy error: {e}")

# Model edit: update metadata (name, params, etc) — does not move files
class ModelPatch(BaseModel):
    name: Optional[str]=None
    params: Optional[str]=None
    size_gb: Optional[float]=None
    quant: Optional[str]=None
    path: Optional[str]=None
    context: Optional[int]=None
    benchmark_mean: Optional[float]=None
    notes: Optional[str]=None

@app.patch("/admin/models/{model_id}")
def patch_model(model_id: str, patch: ModelPatch):
    cfg=MODEL_REGISTRY.get(model_id)
    if not cfg: raise HTTPException(404,"unknown model")
    data=patch.dict(exclude_none=True)
    for k,v in data.items():
        cfg[k]=v
    return {"status":"patched","model":model_id,"meta":cfg}

@app.put("/admin/models/{model_id}")
def put_model(model_id: str, cfg: Dict[str,Any]):
    # create or replace
    MODEL_REGISTRY[model_id]=cfg
    cfg["id"]=model_id
    rr_counters[model_id]=0
    return {"status":"created","model":model_id}

# --------------------------------------------------------------------------
# Dashboard HTML — single file, no CDN, vanilla JS
# --------------------------------------------------------------------------
DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>H200 RAG Dashboard — Manager :9000</title>
<style>
:root{--bg:#0f1419;--panel:#161b22;--border:#21262d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--ok:#3fb950;--warn:#d29922;--err:#f85149;--card:#1c2128}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;background:var(--bg);color:var(--text)}
header{position:sticky;top:0;z-index:10;background:#010409;border-bottom:1px solid var(--border);padding:10px 18px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{margin:0;font-size:18px}header .badge{padding:3px 8px;border-radius:999px;font-size:12px;border:1px solid var(--border)} .ok{color:var(--ok);border-color:var(--ok)} .warn{color:var(--warn)} .err{color:var(--err)}
.tabs{display:flex;gap:6px;padding:12px 18px;border-bottom:1px solid var(--border);overflow:auto;background:var(--panel)}
.tab{padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:var(--card);cursor:pointer;white-space:nowrap}.tab.active{background:var(--accent);color:#010409;border-color:var(--accent);font-weight:600}
.wrap{padding:18px;max-width:1400px;margin:0 auto}
.grid{display:grid;gap:14px}.cols2{grid-template-columns:1fr 1fr}.cols3{grid-template-columns:repeat(3,1fr)}.cols4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.cols2,.cols3,.cols4{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px}
.card h3{margin:0 0 8px 0;font-size:15px}.muted{color:var(--muted);font-size:12px}code{background:#0d1117;padding:2px 6px;border-radius:6px;border:1px solid var(--border);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:7px 8px;border-bottom:1px solid var(--border);text-align:left}th{color:var(--muted);font-weight:600}
.btn{padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--text);cursor:pointer;font-size:13px}.btn:hover{border-color:var(--accent)}.btn.primary{background:var(--accent);color:#010409;border-color:var(--accent)}.btn.danger{border-color:var(--err);color:var(--err)}.btn:disabled{opacity:.5;cursor:not-allowed}
.badge-sm{font-size:11px;padding:2px 6px;border-radius:999px;border:1px solid var(--border)} .s-loaded{color:var(--ok);border-color:var(--ok)} .s-available{color:var(--muted)} .s-loading{color:var(--warn);border-color:var(--warn)}
.gpu-bar{height:10px;background:#0d1117;border:1px solid var(--border);border-radius:999px;overflow:hidden;margin:6px 0}.gpu-fill{height:100%;background:linear-gradient(90deg,var(--accent),#a371f7)}
input,textarea,select{width:100%;padding:8px;border-radius:8px;border:1px solid var(--border);background:#0d1117;color:var(--text);font-size:13px}
.kv{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px dashed var(--border);font-size:13px}
.log{background:#010409;border:1px solid var(--border);border-radius:8px;padding:10px;font-family:ui-monospace,monospace;font-size:12px;white-space:pre-wrap;max-height:320px;overflow:auto}
</style></head><body>
<header>
<h1>🚀 H200 RAG Dashboard</h1>
<span id="health" class="badge">checking…</span>
<span id="gpus" class="muted"></span>
<span class="muted">Manager <code>:9000</code> · Open WebUI <a href="http://192.168.96.82:13000" target="_blank" style="color:var(--accent)">:13000</a> · <a href="/docs" target="_blank" style="color:var(--accent)">Swagger /docs</a></span>
<div style="margin-left:auto;display:flex;gap:8px">
<button class="btn" onclick="refreshAll()">↻ Refresh</button>
<button class="btn" onclick="window.open('/v1/models','_blank')">/v1/models</button>
<button class="btn" onclick="window.open('/admin/status','_blank')">/admin/status</button>
</div>
</header>
<div class="tabs">
<button class="tab active" data-t="overview" onclick="switchTab('overview')">Overview</button>
<button class="tab" data-t="models" onclick="switchTab('models')">Models (11)</button>
<button class="tab" data-t="litellm" onclick="switchTab('litellm')">LiteLLM</button>
<button class="tab" data-t="transparency" onclick="switchTab('transparency')">Transparency</button>
<button class="tab" data-t="embeds" onclick="switchTab('embeds')">Embeds & Docker</button>
<button class="tab" data-t="project" onclick="switchTab('project')">Project</button>
<button class="tab" data-t="usage" onclick="switchTab('usage')">Usage & Sessions</button>
<button class="tab" data-t="play" onclick="switchTab('play')">Playground</button>
</div>
<div class="tabs" style="background:#0f1419;border-top:1px dashed var(--border);gap:4px">
<span class="muted" style="align-self:center;margin-right:6px">Panels:</span>
<button class="tab" data-t="p-kb" onclick="openPanel('kb')">KB :8000</button>
<button class="tab" data-t="p-guard" onclick="openPanel('guard')">Guard :8200</button>
<button class="tab" data-t="p-trace" onclick="openPanel('trace')">Tracing :3000</button>
<button class="tab" data-t="p-langfuse" onclick="openPanel('langfuse')">Langfuse :3001</button>
<button class="tab" data-t="p-studio" onclick="openPanel('studio')">Studio :2024</button>
<button class="tab" data-t="p-webui" onclick="openPanel('webui')">WebUI :13000</button>
<button class="tab" data-t="p-grafana" onclick="openPanel('grafana')">Grafana :13001</button>
<button class="tab" data-t="p-prom" onclick="openPanel('prom')">Prom :19090</button>
<button class="tab" data-t="p-jaeger" onclick="openPanel('jaeger')">Jaeger :16686</button>
<button class="tab" data-t="p-litellm" onclick="openPanel('litellm')">LiteLLM :4000</button>
<span id="panelsHealth" class="muted" style="margin-left:auto;align-self:center">panels: checking…</span>
</div>
<div class="wrap">
<!-- OVERVIEW -->
<div id="tab-overview">
<div class="grid cols3">
<div class="card"><h3>Manager</h3><div id="mgrInfo" class="muted">loading…</div><div id="mgrGpus"></div></div>
<div class="card"><h3>Quick Actions</h3><div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0">
<button class="btn primary" onclick="testChat('gemma-4-31b')">Test Gemma-4</button>
<button class="btn" onclick="testChat('qwen2.5-7b')">Test Qwen2.5-7B</button>
<button class="btn" onclick="testEmbeds()">Test Embed 8001</button>
<button class="btn" onclick="window.open('/dashboard','_blank')">Dashboard /dashboard</button>
</div><div class="muted">Proxy <code>192.168.203.2:3128</code> · <code>HF_HUB_DISABLE_XET=1</code> · <code>no_proxy=localhost</code></div></div>
<div class="card"><h3>Paths</h3><div id="paths" class="muted"></div></div>
</div>
<div class="grid cols2" style="margin-top:14px">
<div class="card"><h3>GPU Utilization (nvidia-smi)</h3><div id="gpuDetail"></div></div>
<div class="card"><h3>Recent Metrics (10)</h3><div id="recentMetrics" class="muted">loading…</div></div>
</div>
<div class="card" style="margin-top:14px"><h3>README Quick Start (copy)</h3><pre class="log">export PROXY_URL="http://192.168.203.2:3128"
export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL" HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL"
export no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"
curl -s http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"Hello"}]}' | jq</pre></div>
</div>
<!-- MODELS -->
<div id="tab-models" style="display:none">
<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
<input id="modelFilter" placeholder="filter models…" oninput="renderModels()" style="max-width:260px">
<select id="statusFilter" onchange="renderModels()" style="max-width:160px"><option value="">all status</option><option>loaded</option><option>available</option><option>partial</option></select>
<button class="btn" onclick="loadDashboard()">Reload</button>
</div>
<div id="modelsGrid" class="grid cols2"></div>
</div>
<!-- EMBEDS & DOCKER -->
<div id="tab-embeds" style="display:none">
<div class="grid cols2">
<div class="card"><h3>Embeddings (3 live)</h3><div id="embedsTbl"></div></div>
<div class="card"><h3>Docker Data Plane (9)</h3><div id="dockerTbl" class="muted">loading…</div></div>
</div>
<div class="grid cols2" style="margin-top:14px">
<div class="card"><h3>Disk — Models (du -sh)</h3><div id="diskTbl" class="muted"></div></div>
<div class="card"><h3>Benchmark Logs & Plots</h3><div id="benchInfo" class="muted"></div></div>
</div>
</div>
<!-- PROJECT -->
<div id="tab-project" style="display:none">
<div class="card"><h3>Project Structure</h3><div id="projTbl" class="muted">loading…</div></div>
<div class="grid cols2" style="margin-top:14px">
<div class="card"><h3>Scripts</h3><div id="scriptsInfo" class="muted"></div></div>
<div class="card"><h3>How to Run</h3><pre class="log">offline-prep/venv/bin/python3.12 scripts/eval_persian.py --model offline-prep/models/huggingface/bartowski_google_gemma-4-31B-it-GGUF/google_gemma-4-31B-it-Q4_K_M.gguf --limit 50 --chat --max-tokens 400 --out logs/evalp_test.json
offline-prep/venv/bin/python3.12 scripts/bench_speed.py --out logs/speed_bench.json
bash scripts/services/gemma_supervisor.sh  # 5× gemma 8080-84
bash llm_inference_manager/test_manager.sh
bash scripts/opencode_test_session.sh</pre></div>
</div>
</div>
<!-- USAGE — cumulative breakdown + plots -->
<div id="tab-usage" style="display:none">
<div class="card"><h3>Global Summary (cumulative)</h3><div id="usageSummary" class="muted">loading…</div><div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:8px"><svg id="pieSvg" width="140" height="140" style="background:#0d1117;border:1px solid var(--border);border-radius:50%"></svg><div id="pieLegend" class="muted" style="font-size:12px"></div><svg id="modelBarSvg" width="320" height="140" style="background:#0d1117;border:1px solid var(--border);border-radius:8px"></svg></div><div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap"><button class="btn" onclick="loadSummary(24)">24h</button><button class="btn" onclick="loadSummary(168)">7d</button><button class="btn" onclick="loadSummary(8760)">30d</button><button class="btn" onclick="loadSummary(8760)">1y</button><span id="summaryMeta" class="muted"></span></div></div>
<div class="grid cols2" style="margin-top:14px">
<div class="card"><h3>Usage by Model (p50/p95/p99) + histograms %</h3><div id="usageByModel"></div><svg id="histSvg" width="100%" height="120" style="background:#0d1117;border:1px solid var(--border);border-radius:8px;margin-top:8px"></svg><div id="histLegend" class="muted"></div><div id="histPct" class="muted" style="font-size:11px"></div></div>
<div class="card"><h3>Sessions (10 recent)</h3><div id="sessionsTbl"></div></div>
</div>
<div class="card" style="margin-top:14px"><h3>Requests over time (hourly avg + p95 + success/blocked/error stacked)</h3><svg id="timeSvg" width="100%" height="120" style="background:#0d1117;border:1px solid var(--border);border-radius:8px"></svg><div id="timeLegend" class="muted"></div></div>
<div class="card" style="margin-top:14px"><h3>Recent Requests (30) — status breakdown</h3><div id="recentTbl"></div></div>
<div class="card" style="margin-top:14px"><h3>API Tokens</h3><div id="tokensTbl"></div></div>
</div>
<!-- PLAYGROUND -->
<div id="tab-play" style="display:none">
<div class="grid cols2">
<div class="card"><h3>Chat Playground (via Manager)</h3>
<select id="playModel" style="margin:8px 0"></select>
<textarea id="playPrompt" rows="3" placeholder="Say hello in one word">Say hello in one word</textarea>
<div style="display:flex;gap:8px;margin:8px 0"><input id="playMax" type="number" value="100" style="max-width:90px" placeholder="max_tokens"><input id="playTemp" type="number" step="0.1" value="0.7" style="max-width:90px" placeholder="temp"><button class="btn primary" onclick="sendPlay()">Send</button></div>
<div id="playOut" class="log" style="min-height:120px">output…</div>
</div>
 <div class="card"><h3>Embed Playground (direct 8001)</h3>
<textarea id="embedInput" rows="3" placeholder="hello world">hello world</textarea>
<button class="btn" onclick="sendEmbed()">Embed → dim</button>
<div id="embedOut" class="log" style="min-height:120px">output…</div>
</div>
</div>
</div>
<!-- LITELLM -->
<div id="tab-litellm" style="display:none">
<div class="grid cols2">
<div class="card"><h3>LiteLLM Status</h3><div id="llmHealth" class="muted">loading…</div><div id="llmAliases" style="margin-top:8px"></div></div>
<div class="card"><h3>Spend & Budgets</h3><div id="llmSpend" class="muted">loading…</div></div>
</div>
<div class="card" style="margin-top:14px"><h3>Alias Grid (logical → deployments)</h3><div id="llmGrid" class="muted">loading…</div></div>
<div class="card" style="margin-top:14px"><h3>Manager ↔ LiteLLM Compare</h3><div id="llmCompare" class="muted"></div></div>
<div class="card" style="margin-top:14px"><h3>Fallback Visualizer</h3><pre class="log" id="llmFallback">loading…</pre></div>
</div>
<!-- TRANSPARENCY — diagrammed sequential view + per-sample breakdown -->
<div id="tab-transparency" style="display:none">
<div class="card"><h3>Search Transparency — step-by-step pipeline</h3>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0">
<input id="transparencyQ" placeholder="اعتبارسنجی چیست" style="flex:1;min-width:200px" value="اعتبارسنجی چیست">
<input id="transparencyTopK" type="number" value="5" min="1" max="20" style="width:80px" title="top_k"><input id="transparencyBoost" type="number" step="0.1" value="3.0" style="width:80px" title="keyword_boost">
<button class="btn primary" onclick="runTransparency()">▶ Run pipeline</button>
<span id="transparencyMeta" class="muted"></span>
</div>
<div id="transparencyDiagram" style="margin:10px 0;min-height:60px"></div>
<div id="transparencyBar" style="height:16px;background:#0d1117;border:1px solid var(--border);border-radius:999px;overflow:hidden;display:flex;margin:8px 0"></div>
<div id="transparencyLegend" class="muted" style="font-size:11px"></div>
<div id="transparencyStages" style="margin-top:10px"></div>
<div id="transparencyFinal" style="margin-top:10px"></div>
<div id="transparencyRaw" class="log" style="display:none;max-height:200px;margin-top:8px"></div>
<button class="btn" style="margin-top:6px" onclick="document.getElementById('transparencyRaw').style.display=document.getElementById('transparencyRaw').style.display==='none'?'block':'none'">Toggle raw JSON</button>
</div>
<div class="grid cols2" style="margin-top:14px">
<div class="card"><h3>Recent Traces (request → response)</h3><div style="display:flex;gap:6px;margin-bottom:6px"><input id="traceIdInput" placeholder="request_id" style="flex:1"><button class="btn" onclick="loadTraces()">Load recent</button><button class="btn" onclick="loadTraceDetail()">Show detail</button></div><div id="tracesTbl" class="muted">loading…</div></div>
<div class="card"><h3>Trace Detail — per-span Gantt (OTEL/Jaeger)</h3><div id="traceDetail" class="log" style="min-height:120px">select a trace</div><svg id="traceGantt" width="100%" height="80" style="background:#0d1117;border:1px solid var(--border);border-radius:8px;margin-top:6px"></svg><div class="muted" style="margin-top:6px">OTEL <code>14317/14318</code> → Jaeger <code>:16686</code> · <code>/api/spans?request_id=</code> + <code>/api/observe</code></div></div>
</div>
</div>
<!-- PANEL FRAME -->
<div id="panel-frame" style="display:none">
<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
<span id="panelTitle" class="muted">Panel</span>
<button class="btn" onclick="closePanel()">✕ Close panel</button>
<button class="btn" onclick="document.getElementById('panelIframe').src=document.getElementById('panelIframe').src">↻ Reload</button>
<button class="btn" onclick="window.open(document.getElementById('panelIframe').src,'_blank')">↗ Open in new tab</button>
</div>
<iframe id="panelIframe" style="width:100%;height:78vh;border:1px solid var(--border);border-radius:12px;background:#010409"></iframe>
</div>
</div>
<script>
let D=null;
let PANELS=null;
function switchTab(t){document.querySelectorAll('[id^="tab-"]').forEach(e=>e.style.display='none');document.getElementById('panel-frame').style.display='none'; const el=document.getElementById('tab-'+t); if(el) el.style.display='block'; document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active')); const a=document.querySelector(`.tab[data-t="${t}"]`); if(a) a.classList.add('active'); if(t==='litellm') loadLitellm(); if(t==='transparency') loadTraces()}
function openPanel(name){const map={kb:'/panel/kb/',guard:'/panel/guard/dashboard',trace:'/panel/trace/',langfuse:'/panel/langfuse/',studio:'/panel/studio/',webui:'/panel/webui/',grafana:'/panel/grafana/',prom:'/panel/prom/',jaeger:'/panel/jaeger/',litellm:'/panel/litellm/',embed8001:'/panel/embed8001/',embed8002:'/panel/embed8002/',embed8003:'/panel/embed8003/'}; const url=map[name]||'/panel/'+name+'/'; document.querySelectorAll('[id^="tab-"]').forEach(e=>e.style.display='none'); const f=document.getElementById('panel-frame'); f.style.display='block'; document.getElementById('panelIframe').src=url; document.getElementById('panelTitle').textContent='Panel: '+name+' → '+url; document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active')); const a=document.querySelector(`.tab[data-t="p-${name}"]`); if(a) a.classList.add('active')}
function closePanel(){document.getElementById('panel-frame').style.display='none'; switchTab('overview')}
async function fetchJSON(u, opts){const r=await fetch(u, opts); if(!r.ok) throw new Error(r.status+' '+await r.text().then(s=>s.slice(0,400))); return r.json()}
async function loadDashboard(){
 try{
  D=await fetchJSON('/api/dashboard');
  document.getElementById('health').textContent = `models_loaded: ${D.manager.models_loaded} · ${D.manager.gpus.length} GPUs`;
  document.getElementById('health').className='badge ok';
  document.getElementById('gpus').textContent = D.manager.gpus.map(g=>`GPU${g.index} ${g.used_mib}/${g.total_mib}MiB free ${g.free_mib} util ${g.util}%`).join(' · ');
  document.getElementById('mgrInfo').innerHTML = `Version <code>${D.manager.version}</code> · <span class="badge-sm s-loaded">loaded ${D.manager.models_loaded}/11</span> · Proxy <code>${D.proxy.PROXY_URL||'192.168.203.2:3128'}</code>`;
  document.getElementById('paths').innerHTML = `Root <code>${D.paths.root}</code><br>Venv <code>${D.paths.venv}</code><br>Models <code>${D.paths.models_dir}</code>`;
  // GPUs
  let gh=''; D.manager.gpus.forEach(g=>{const pct=Math.round(g.used_mib/g.total_mib*100); gh+=`<div class="kv"><span>GPU ${g.index}</span><span>${g.used_mib}/${g.total_mib} MiB (${pct}%) free ${g.free_mib}</span></div><div class="gpu-bar"><div class="gpu-fill" style="width:${pct}%"></div></div>`}); document.getElementById('mgrGpus').innerHTML=gh;
  let gd=''; D.manager.gpus.forEach(g=>{gd+=`<div class="kv"><span>GPU ${g.index} util ${g.util}%</span><span>free ${g.free_mib} MiB</span></div>`}); document.getElementById('gpuDetail').innerHTML=gd;
  document.getElementById('recentMetrics').innerHTML = D.metrics.recent.length? D.metrics.recent.map(r=>`<div class="kv"><span>${r.model} <code>${r.endpoint}</code></span><span>${Math.round(r.latency_ms)}ms ${new Date(r.created_at).toLocaleTimeString()}</span></div>`).join('') : '<span class="muted">no metrics yet</span>';
  renderModels(); renderEmbeds(); renderDocker(); renderDisk(); renderProject(); renderUsage();
  // play models
  const sel=document.getElementById('playModel'); sel.innerHTML=D.models.map(m=>`<option value="${m.id}">${m.id} — ${m.name} (${m.status})</option>`).join('');
 }catch(e){document.getElementById('health').textContent='error '+e.message; document.getElementById('health').className='badge err'}
}
function renderModels(){
 if(!D) return; const f=(document.getElementById('modelFilter').value||'').toLowerCase(); const sf=document.getElementById('statusFilter').value;
 const filtered=D.models.filter(m=> (!f|| (m.id+m.name+m.family).toLowerCase().includes(f)) && (!sf|| m.status.includes(sf)) );
 document.getElementById('modelsGrid').innerHTML = filtered.map(m=>`
  <div class="card">
   <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b>${m.id}</b> <span class="badge-sm ${m.status.includes('loaded')?'s-loaded':m.status.includes('loading')?'s-loading':'s-available'}">${m.status}</span> <span class="muted">${m.family} · ${m.params} · ${m.quant} · ${m.context} ctx</span></div>
   <div class="muted">${m.name} — ${m.creator} · ${m.size_gb}GB · mean ${m.benchmark_mean??'—'} · <code>${m.path}</code> ${m.path_exists?'✅':'❌'}</div>
   <div style="margin:8px 0;display:flex;gap:6px;flex-wrap:wrap">
    ${m.backends.map(b=>`<code>${b}</code>`).join(' ') || '<span class="muted">no backend</span>'}
   </div>
   ${m.live_health && m.live_health.length? `<div class="muted">${m.live_health.map(h=>`health ${h.backend}: ${h.status}`).join(' · ')}</div>` : ''}
   <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
    <button class="btn primary" onclick="runModel('${m.id}')" ${m.status.includes('loaded')?'disabled':''}>▶ Run</button>
    <button class="btn danger" onclick="stopModel('${m.id}')" ${!m.status.includes('loaded') && !m.status.includes('loading')?'disabled':''}>⏹ Stop</button>
    <button class="btn" onclick="testChat('${m.id}')">💬 Test</button>
    <button class="btn" onclick="editModel('${m.id}')">✎ Edit</button>
   </div>
   <div id="msg-${m.id}" class="muted" style="margin-top:6px"></div>
  </div>
 `).join('');
}
function renderEmbeds(){ if(!D) return; document.getElementById('embedsTbl').innerHTML = `<table><tr><th>port</th><th>model</th><th>dim</th><th>health</th></tr>${D.embeds.map(e=>`<tr><td>${e.port}</td><td>${e.model_id}</td><td>${e.dim||'?'}</td><td>${e.status|| (e.error?'❌ '+e.error.slice(0,60):'✅')}</td></tr>`).join('')}</table>`; }
function renderDocker(){ if(!D) return; document.getElementById('dockerTbl').innerHTML = D.docker.length? `<table><tr><th>name</th><th>status</th><th>ports</th></tr>${D.docker.map(d=>`<tr><td>${d.name}</td><td>${d.status.slice(0,60)}</td><td>${(d.ports||'').slice(0,80)}</td></tr>`).join('')}</table>` : 'no docker';}
function renderDisk(){ if(!D) return; document.getElementById('diskTbl').innerHTML = D.disk.map(d=>`<div class="kv"><span>${d.path}</span><span>${d.size}</span></div>`).join(''); document.getElementById('benchInfo').innerHTML = `Logs <code>${D.benchmarks.logs.length} evalp*.json</code> · Plots <code>${D.benchmarks.plots.length} png</code><br><span class="muted">${D.benchmarks.logs.slice(0,5).join(', ')}</span>`; }
function renderProject(){ if(!D) return; document.getElementById('projTbl').innerHTML = D.project.map(p=>`<div class="kv"><span><code>${p.path}</code> ${p.exists?'✅':'❌'} (${p.count})</span><span class="muted">${(p.files||[]).slice(0,5).join(', ')}</span></div>`).join('');}
function renderUsage(){ if(!D) return; document.getElementById('usageByModel').innerHTML = D.metrics.by_model.length? D.metrics.by_model.map(b=>`<div class="kv"><span>${b.model}</span><span>${b.cnt} req avg ${Math.round(b.avg_ms||0)}ms p50 ${b.p50_ms||'?'} p95 ${b.p95_ms||'?'} p99 ${b.p99_ms||'?'} max ${Math.round(b.max_ms||0)}ms</span></div>`).join('') : '<span class="muted">no usage yet</span>'; document.getElementById('sessionsTbl').innerHTML = D.metrics.sessions.length? D.metrics.sessions.map(s=>`<div class="kv" style="cursor:pointer" onclick="loadSession('${s.id}')" title="Click to view chat"><span><code>${s.id.slice(0,8)}</code> ${s.model}</span><span>${s.title.slice(0,20)} ${new Date(s.updated_at).toLocaleTimeString()}</span></div>`).join('') + '<div id="sessionDetail" class="log" style="margin-top:8px;max-height:240px;display:none"></div>' : 'no sessions'; document.getElementById('recentTbl').innerHTML = D.metrics.recent.map(r=>`<div class="kv"><span>${r.model} ${r.endpoint}</span><span>${Math.round(r.latency_ms)}ms ${new Date(r.created_at).toLocaleTimeString()}</span></div>`).join(''); document.getElementById('tokensTbl').innerHTML = D.metrics.tokens.map(t=>`<div class="kv"><span><code>${t.token.slice(0,12)}…</code> ${t.name}</span><span>${new Date(t.created_at).toLocaleDateString()}</span></div>`).join(''); loadHist(); loadTimeSeries(); loadSummary(8760);}
async function loadSession(sid){ const el=document.getElementById('sessionDetail'); if(!el) return; el.style.display='block'; el.textContent='loading '+sid+'…'; try{ const j=await fetchJSON('/v1/sessions/'+encodeURIComponent(sid)); const msgs=j.messages||[]; el.innerHTML = msgs.map(m=>`<div style="margin:6px 0;padding:8px;border-radius:8px;background:${m.role==='user'?'#0d1117':'#161b22'};border:1px solid var(--border)"><b style="color:${m.role==='user'?'var(--accent)':'var(--ok)'}">${m.role}</b> <span class="muted">${new Date(m.created_at).toLocaleTimeString()}</span><div style="margin-top:4px;white-space:pre-wrap">${(m.content||'').replace(/</g,'&lt;')}</div></div>`).join('') || '<span class="muted">no messages</span>'; }catch(e){ el.textContent='error '+e.message; }}

function drawHist(svg, counts, buckets){ const w=svg.clientWidth||560, h=100, pad=10; svg.setAttribute('viewBox',`0 0 ${w} ${h}`); const max=Math.max(...counts,1); svg.innerHTML=''; counts.forEach((c,i)=>{const bh=c/max*(h-pad*2); const bw=(w-pad*2)/counts.length-2; const x=pad+i*(bw+2), y=h-pad-bh; const rect=document.createElementNS('http://www.w3.org/2000/svg','rect'); rect.setAttribute('x',x); rect.setAttribute('y',y); rect.setAttribute('width',bw); rect.setAttribute('height',bh); rect.setAttribute('fill','#58a6ff'); rect.setAttribute('opacity',0.8); svg.appendChild(rect);});}
async function loadHist(){ try{const j=await fetchJSON('/api/metrics/histogram?hours=8760'); drawHist(document.getElementById('histSvg'), j.counts||[], j.buckets||[]); document.getElementById('histLegend').textContent=`p50 ${j.p50_ms||'?'} ms p95 ${j.p95_ms||'?'} p99 ${j.p99_ms||'?'} min ${j.min_ms||'?'} max ${j.max_ms||'?'} total ${j.total||0}`; const pctEl=document.getElementById('histPct'); if(pctEl) pctEl.textContent=j.counts_pct? `counts%: ${j.counts_pct.slice(0,6).join(', ')}…` : ''; }catch(e){document.getElementById('histLegend').textContent='hist error '+e.message}}
async function loadTimeSeries(){ try{const j=await fetchJSON('/api/metrics/timeseries?hours=720&bucket_min=60'); const svg=document.getElementById('timeSvg'); const s=j.series||[]; if(!s.length){document.getElementById('timeLegend').textContent='no timeseries (metrics empty – no requests in last 7d)'; return;} const w=svg.clientWidth||560, h=100, pad=14; svg.setAttribute('viewBox',`0 0 ${w} ${h}`); const max=Math.max(...s.map(x=>x.avg_ms),1); const pmax=Math.max(...s.map(x=>x.p95_ms||0),1); svg.innerHTML=''; s.forEach((pt,i)=>{const x=pad+i*(w-pad*2)/Math.max(s.length-1,1); const yAvg=h-pad-pt.avg_ms/max*(h-pad*2); const yP95=h-pad-(pt.p95_ms||0)/pmax*(h-pad*2); if(i>0){const prev=s[i-1]; const xp=pad+(i-1)*(w-pad*2)/Math.max(s.length-1,1); const yAp=h-pad-prev.avg_ms/max*(h-pad*2); const l=document.createElementNS('http://www.w3.org/2000/svg','line'); l.setAttribute('x1',xp); l.setAttribute('y1',yAp); l.setAttribute('x2',x); l.setAttribute('y2',yAvg); l.setAttribute('stroke','#3fb950'); l.setAttribute('stroke-width','2'); svg.appendChild(l); const l2=document.createElementNS('http://www.w3.org/2000/svg','line'); l2.setAttribute('x1',xp); l2.setAttribute('y1',h-pad-(prev.p95_ms||0)/pmax*(h-pad*2)); l2.setAttribute('x2',x); l2.setAttribute('y2',yP95); l2.setAttribute('stroke','#d29922'); l2.setAttribute('stroke-width','1'); l2.setAttribute('stroke-dasharray','4 2'); svg.appendChild(l2);} const c=document.createElementNS('http://www.w3.org/2000/svg','circle'); c.setAttribute('cx',x); c.setAttribute('cy',yAvg); c.setAttribute('r','2'); c.setAttribute('fill','#3fb950'); svg.appendChild(c);}); document.getElementById('timeLegend').textContent=s.length+` points avg max ${Math.round(max)}ms p95 max ${Math.round(pmax)}ms (green avg, dashed p95)  blocked:${s[s.length-1]?.blocked_cnt||0} err:${s[s.length-1]?.error_cnt||0}`;}catch(e){document.getElementById('timeLegend').textContent='timeseries error '+e.message}}
async function loadSummary(hours=720){ try{const j=await fetchJSON(`/api/metrics/summary?hours=${hours}`); const el=document.getElementById('usageSummary'); const meta=document.getElementById('summaryMeta'); if(!el) return; el.innerHTML=`Total <b>${j.total}</b> · Success <span style="color:var(--ok)">${j.by_status.success||0} (${(j.success_rate*100).toFixed(1)}%)</span> · Blocked <span style="color:var(--warn)">${j.by_status.blocked||0} (${(j.blocked_rate*100).toFixed(1)}%)</span> · Error <span style="color:var(--err)">${j.by_status.error||0} (${(j.error_rate*100).toFixed(1)}%)</span> · Models ${Object.keys(j.by_model).length}`; if(meta) meta.textContent=`${hours}h window · p50/p95 per model below`; drawDoughnut(document.getElementById('pieSvg'), j.by_status); drawModelBars(document.getElementById('modelBarSvg'), j.summary_by_model); const leg=document.getElementById('pieLegend'); if(leg) leg.innerHTML=Object.entries(j.by_status).map(([k,v])=>`${k}: ${v}`).join('<br>') + `<br>success ${(j.success_rate*100).toFixed(1)}%`; }catch(e){ const el=document.getElementById('usageSummary'); if(el) el.textContent='summary error '+e.message; }}
function drawDoughnut(svg, byStatus){ if(!svg) return; const total=Object.values(byStatus).reduce((a,b)=>a+b,0)||1; const colors={"success":"#3fb950","blocked":"#d29922","error":"#f85149","unknown":"#8b949e"}; let acc=0; svg.setAttribute('viewBox','0 0 100 100'); svg.innerHTML=''; Object.entries(byStatus).forEach(([k,v])=>{ const pct=v/total; const angle=pct*360; const large=angle>180?1:0; const x1=50+40*Math.cos((acc*360-90)*Math.PI/180), y1=50+40*Math.sin((acc*360-90)*Math.PI/180); acc+=pct; const x2=50+40*Math.cos((acc*360-90)*Math.PI/180), y2=50+40*Math.sin((acc*360-90)*Math.PI/180); const path=document.createElementNS('http://www.w3.org/2000/svg','path'); const d=`M50,50 L${x1},${y1} A40,40 0 ${large},1 ${x2},${y2} Z`; path.setAttribute('d',d); path.setAttribute('fill',colors[k]||'#58a6ff'); path.setAttribute('stroke','#0d1117'); path.setAttribute('stroke-width','1'); svg.appendChild(path);}); if(total===0){ const c=document.createElementNS('http://www.w3.org/2000/svg','circle'); c.setAttribute('cx',50); c.setAttribute('cy',50); c.setAttribute('r',40); c.setAttribute('fill','#161b22'); svg.appendChild(c);} }
function drawModelBars(svg, summary){ if(!svg || !summary) return; const entries=Object.entries(summary).slice(0,5); const w=svg.clientWidth||320, h=140, pad=14; svg.setAttribute('viewBox',`0 0 ${w} ${h}`); svg.innerHTML=''; const maxP95=Math.max(...entries.map(([,v])=>v.p95||v.p95_ms||1),1); entries.forEach(([model, v], i)=>{ const y=pad+i*26; const bw=(v.p95||v.p95_ms||0)/maxP95*(w-pad*60); const rect=document.createElementNS('http://www.w3.org/2000/svg','rect'); rect.setAttribute('x',60); rect.setAttribute('y',y); rect.setAttribute('width',bw); rect.setAttribute('height',14); rect.setAttribute('fill','#58a6ff'); rect.setAttribute('opacity',0.8); svg.appendChild(rect); const txt=document.createElementNS('http://www.w3.org/2000/svg','text'); txt.setAttribute('x',2); txt.setAttribute('y',y+10); txt.setAttribute('fill','#e6edf3'); txt.setAttribute('font-size','8'); txt.textContent=model.slice(0,14); svg.appendChild(txt); const vtxt=document.createElementNS('http://www.w3.org/2000/svg','text'); vtxt.setAttribute('x',62+bw+2); vtxt.setAttribute('y',y+10); vtxt.setAttribute('fill','#8b949e'); vtxt.setAttribute('font-size','7'); vtxt.textContent=`p95 ${Math.round(v.p95||v.p95_ms||0)}`; svg.appendChild(vtxt);}); }
async function runModel(id){ const el=document.getElementById('msg-'+id); el.textContent='starting…'; try{ const r=await fetch(`/admin/models/load?model_id=${encodeURIComponent(id)}`,{method:'POST'}); const j=await r.json(); el.textContent= r.status==='already loaded'? 'already loaded '+j.backends : `spawned port ${j.port} gpu ${j.gpu} pid ${j.pid}`; setTimeout(loadDashboard,1500)} catch(e){el.textContent='error '+e.message}}
async function stopModel(id){ const el=document.getElementById('msg-'+id); el.textContent='stopping…'; try{ const r=await fetch(`/admin/models/unload?model_id=${encodeURIComponent(id)}`,{method:'POST'}); const j=await r.json(); el.textContent=j.status; loadDashboard()}catch(e){el.textContent='error '+e.message}}
async function testChat(id){ const out=document.getElementById('playOut')||null; try{ const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:id,messages:[{role:'user',content:'say hello one word'}],max_tokens:10})}); const j=await r.json(); alert(id+': '+(j.choices?.[0]?.message?.content||JSON.stringify(j).slice(0,300))); loadDashboard()} catch(e){alert('error '+e.message)}}
async function editModel(id){ const m=D.models.find(x=>x.id===id); const name=prompt('Edit name',m.name); if(name===null) return; const params=prompt('Edit params',m.params); if(params===null) return; try{ const r=await fetch(`/admin/models/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,params})}); const j=await r.json(); alert('patched '+j.model); loadDashboard()}catch(e){alert(e.message)}}
async function sendPlay(){ const id=document.getElementById('playModel').value; const prompt=document.getElementById('playPrompt').value; const mx=parseInt(document.getElementById('playMax').value)||50; const tp=parseFloat(document.getElementById('playTemp').value)||0.7; const out=document.getElementById('playOut'); out.textContent='sending…'; try{ const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:id,messages:[{role:'user',content:prompt}],max_tokens:mx,temperature:tp})}); const j=await r.json(); out.textContent=JSON.stringify(j,null,2)}catch(e){out.textContent='error '+e.message}}
async function sendEmbed(){ const txt=document.getElementById('embedInput').value; const out=document.getElementById('embedOut'); out.textContent='embedding…'; try{ const r=await fetch('/v1/embeddings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:txt})}); if(!r.ok) throw new Error(r.status+' '+await r.text().then(s=>s.slice(0,300))); const j=await r.json(); out.textContent=`dim ${j.data[0].embedding.length}\nfirst 5: ${j.data[0].embedding.slice(0,5).map(x=>x.toFixed(4)).join(', ')}`}catch(e){ out.textContent='error '+e.message+' (embed 8001 via /v1/embeddings proxy; if 502 check panel embed8001 health)'} }
function testEmbeds(){ fetch('/panel/embed8001/health').then(r=>r.json()).then(j=>alert('embed8001 via panel: '+JSON.stringify(j).slice(0,300))).catch(e=>alert(e.message))}
async function loadLitellm(){const h=document.getElementById('llmHealth'); try{const s=await fetchJSON('/api/litellm/health'); const g=await fetchJSON('/api/litellm/models').catch(e=>({error:String(e)})); const isDown = s.health && s.health.error && s.health.error.includes('All connection'); const healthCode = s.health && s.health.code; h.innerHTML=`LiteLLM <code>${s.url||'http://127.0.0.1:4000'}</code> health <span class="badge-sm ${healthCode===200?'s-loaded':isDown?'s-available':'s-loading'}">${isDown?'down':healthCode||s.health?.status||'ok'}</span><br><span class="muted">${isDown?'⚠️ LiteLLM container not running — <code>docker compose -f deploy/docker-compose.yml up -d litellm</code> or <code>python -m litellm --config litellm.yaml --port 4000</code> (needs <code>litellm.env</code> with LITELLM_MASTER_KEY)':JSON.stringify(s.health?.body||s.health||'').slice(0,500)}</span>`; let grid='<table><tr><th>alias</th><th>model / api_base</th><th>deployments</th></tr>'; let list=[]; if(s.model_info && s.model_info.data){ s.model_info.data.forEach(d=>{ list.push({id:d.model_name, model:d.litellm_params?.model, api_base:d.litellm_params?.api_base, owned_by:d.litellm_params?.model}) }); } const gData = g.data || g.raw || g; const gList = Array.isArray(gData)? gData : (gData.data||[]); if(!list.length && gList.length){ gList.forEach(m=>{ list.push({id:m.id||m.model_name, model:m.model||'', api_base:m.litellm_params?.api_base||m.api_base||'', owned_by:m.owned_by||''}) }); } if(isDown){ grid+=`<tr><td colspan=3 class="muted">LiteLLM down — showing <code>litellm.yaml</code> expected aliases: <code>self-gemma</code>→Manager :9000, <code>cheap</code>→SiliconFlow, <code>strong</code>→OpenRouter, <code>judge</code>→Gemini · Start container to see live list.<br><span class="muted">Health error: ${s.health.error.slice(0,300)}</span></td></tr>`; } else if(list.length){ list.forEach(m=>{ grid+=`<tr><td><code>${m.id}</code></td><td>${(m.model||'')}<br><span class="muted">${(m.api_base||'')}</span></td><td><span class="badge-sm">${m.owned_by||''}</span></td></tr>`}); } else { grid+=`<tr><td colspan=3 class="muted">${JSON.stringify(g).slice(0,1200)}</td></tr>` } grid+='</table>'; document.getElementById('llmGrid').innerHTML=grid; document.getElementById('llmAliases').innerHTML=`Aliases visible: <code>${list.length||0}</code> · from <code>${isDown?'litellm.yaml (expected)':'/api/litellm/models + /model/info'}</code>`; const comp=`<div class="muted">Manager models: <code>${D?D.models.length:0}</code> (gemma-4-31b 5×8080-84) vs LiteLLM aliases: <code>${list.length||0}</code> (self-gemma→Manager :9000)</div>`; document.getElementById('llmCompare').innerHTML=comp; document.getElementById('llmFallback').textContent='fallbacks (from litellm.yaml):\n strong → cheap → self-gemma\n judge  → strong → self-gemma\n cheap  → self-gemma\n(routing_strategy: usage-based-routing, retries:3)'+(isDown?' — will activate once LiteLLM up':''); try{const sp=await fetchJSON('/api/litellm/spend'); const spendTxt = sp.error && sp.error.includes('database_url') ? 'Spend requires DATABASE_URL in litellm.yaml — configure or ignore (expected when no DB)' : JSON.stringify(sp,null,2).slice(0,4000); document.getElementById('llmSpend').innerHTML=`<pre class="log">${spendTxt}</pre>`;}catch(e){document.getElementById('llmSpend').textContent='spend unavailable: '+e.message+(isDown?' (LiteLLM down)':'')}}catch(e){ const he=document.getElementById('llmHealth'); if(he) he.textContent='litellm load error '+e.message}}
async function loadPanelsHealth(){try{const p=await fetchJSON('/api/panels/health'); PANELS=p; const ok=Object.values(p).filter(x=>x.status==='ok').length; const total=Object.keys(p).length; document.getElementById('panelsHealth').textContent=`panels ${ok}/${total} ok`; document.getElementById('panelsHealth').className='badge '+(ok===total?'ok':ok>total/2?'warn':'err');}catch(e){document.getElementById('panelsHealth').textContent='panels: error'; document.getElementById('panelsHealth').className='badge err'}}
async function loadTraces(){const tbl=document.getElementById('tracesTbl'); try{const j=await fetchJSON('/panel/trace/api/observe/requests?limit=10'); const rows=j.data||j||[]; if(!rows.length){tbl.innerHTML='<span class="muted">no traces yet (run a chat via playground)</span>'; return;} tbl.innerHTML='<table><tr><th>flag</th><th>request_id</th><th>name</th><th>spans</th><th>input</th></tr>'+rows.slice(-10).reverse().map(r=>`<tr><td>${r.has_response?'✓':'…'}</td><td><a href="#" onclick="document.getElementById('traceIdInput').value='${r.request_id}';loadTraceDetail();return false">${r.request_id.slice(0,16)}…</a></td><td>${r.name||''}</td><td>${r.spans||0}</td><td>${(r.input_preview||'').slice(0,60)}</td></tr>`).join('')+'</table>';}catch(e){tbl.textContent='traces error '+e.message}}
async function loadTraceDetail(){
  const id=document.getElementById('traceIdInput').value.trim();
  const out=document.getElementById('traceDetail');
  const gantt=document.getElementById('traceGantt');
  if(!id){out.textContent='enter request_id'; return;}
  out.textContent='loading '+id+'…'; if(gantt) gantt.innerHTML='';
  const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const badge=(src)=>{
    const m={both:'BOTH',ce:'CE',rrf:'RRF'}; const lb=(m[src]||src||'—').toUpperCase();
    const cls=src==='both'?'background:#dbeafe;color:#1e40af;border-color:#bfdbfe':src==='ce'?'background:#dcfce7;color:#166534':src==='rrf'?'background:#fef3c7;color:#92400e':'background:#161b22;color:#8b949e';
    return '<span style="font-size:10px;padding:2px 7px;border-radius:10px;border:1px solid var(--border);'+cls+'">'+esc(lb)+'</span>';
  };
  const chunkCard=(c,i)=>{
    const src=(c.source||'').toLowerCase();
    const score=c.score!=null?Number(c.score):(c.hybrid_score!=null?Number(c.hybrid_score):(c.rerank_score!=null?Number(c.rerank_score):null));
    const pct=score!=null?Math.min(100,Math.max(0,Math.round(score*100))):null;
    const col=pct==null?'#8b949e':pct>=80?'#3fb950':pct>=50?'#58a6ff':'#d29922';
    let content=(c.content||c.text||'').trim();
    if(!content&&c.content_preview) content=c.content_preview;
    return '<div style="border:1px solid var(--border);border-radius:8px;padding:8px;margin:5px 0;background:#0d1117">'
      +'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">'+badge(src)
      +(pct!=null?'<div style="flex:1;max-width:100px;height:7px;background:#21262d;border-radius:4px;overflow:hidden"><div style="height:100%;border-radius:4px;width:'+pct+'%;background:'+col+'"></div></div><span style="font-size:10px;color:var(--muted)">'+(score!=null?score.toFixed(3):'')+'</span>':'')
      +'<b style="font-size:11px">'+esc(c.title||c.doc_title||'Untitled')+'</b></div>'
      +(c.heading||c.heading_path?'<div style="font-size:10px;color:var(--muted)">'+esc(c.heading||c.heading_path)+'</div>':'')
      +'<div style="font-size:11px;white-space:pre-wrap;word-break:break-word;margin-top:4px">'+esc(content.slice(0,600))+'</div>'
      +(content.length>600?'<details style="margin-top:4px"><summary style="cursor:pointer;font-size:10px;color:var(--muted)">Show more</summary><div style="font-size:11px;white-space:pre-wrap">'+esc(content.slice(600))+'</div></details>':'')
      +'</div>';
  };
  // Try the rich observability pipeline first (formatted stages + chunks)
  try{
    const d=await fetchJSON('/panel/trace/api/observability/pipeline/'+encodeURIComponent(id));
    if(d && (d.retrieved_chunks||d.stage_timing||d.timeline)){
      const rc=d.retrieved_chunks||[]; const st=d.stage_timing||{}; const tl=d.timeline||d.observer_timeline||null;
      let html='';
      // Stage 1: User + Stage 2: Guardrail Input + Stage 3: Rewrite (compact)
      html+='<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">'
        +(rc.length?'<span style="font-size:10px;padding:2px 7px;border-radius:10px;background:#1f2937;border:1px solid var(--border)">'+rc.length+' chunks</span>':'')
        +(d.retrieval_method?'<span style="font-size:10px;padding:2px 7px;border-radius:10px;background:#1f2937;border:1px solid var(--border)">'+esc(d.retrieval_method)+'</span>':'')
        +(d.model?'<span style="font-size:10px;padding:2px 7px;border-radius:10px;background:#1f2937;border:1px solid var(--border)">'+esc(d.model)+'</span>':'')
        +'</div>';
      html+='<div style="font-size:11px;color:var(--muted);margin-bottom:4px">Query: '+esc((d.user_query||'').slice(0,200))+'</div>';
      if(d.rewritten_query&&d.rewritten_query!==d.user_query) html+='<div style="font-size:11px;color:var(--muted)">Rewritten: '+esc(d.rewritten_query.slice(0,200))+'</div>';
      // Chunks
      if(rc.length){
        html+='<h4 style="margin:6px 0 4px;font-size:11px">Retrieved chunks</h4>';
        rc.forEach((c,i)=>{ html+=chunkCard(c,i); });
      }
      // Stage timing
      if(st && Object.keys(st).length){
        html+='<h4 style="margin:6px 0 4px;font-size:11px">Stage timing</h4><div style="font-size:11px;color:var(--muted)">'
          +Object.entries(st).map(([k,v])=>esc(k)+' '+Math.round(Number(v))+'ms').join(' · ')
          +' · total '+esc(d.latency_ms!=null? d.latency_ms+'ms':'—')+'</div>';
      }
      // Response preview
      if(d.response){
        html+='<h4 style="margin:6px 0 4px;font-size:11px">Response</h4><div style="font-size:11px;white-space:pre-wrap;background:#0d1117;border:1px solid var(--border);padding:6px;border-radius:6px;max-height:300px;overflow:auto">'+esc(String(d.response).slice(0,2000))+'</div>';
      }
      // Also show spans Gantt from timeline
      if(tl&&tl.spans&&tl.spans.length&&gantt){
        html+='<details style="margin-top:6px"><summary style="cursor:pointer;font-size:10px;color:var(--muted)">Raw JSON (debug)</summary><pre style="max-height:400px;overflow:auto;margin-top:4px;font-size:10px;white-space:pre-wrap;word-break:break-all">'+esc(JSON.stringify(d,null,2).slice(0,6000))+'</pre></details>';
        out.innerHTML=html;
        drawTraceGantt(gantt, tl.spans);
        return;
      }
      out.innerHTML=html;
      if(tl&&tl.spans&&gantt) drawTraceGantt(gantt, tl.spans);
      return;
    }
  }catch(e){ /* fall through to spans API */ }
  // Fallback: spans/Gantt from Jaeger or observe timeline
  try{
    const j=await fetchJSON('/api/spans?request_id='+encodeURIComponent(id));
    if(j.spans&&j.spans.length){
      out.innerHTML='<div style="font-size:11px;color:var(--muted)">Spans from '+esc(j.source||'trace')+'</div>';
      if(gantt) drawTraceGantt(gantt, j.spans);
      return;
    }
    const t=await fetchJSON('/panel/trace/api/observe/timeline/'+encodeURIComponent(id));
    if(t&&t.spans){
      out.innerHTML='<div style="font-size:11px;color:var(--muted)">Observer timeline: '+esc(t.name||'')+'</div>';
      if(gantt) drawTraceGantt(gantt, t.spans);
      if(t.input) out.innerHTML+='<div style="margin-top:4px"><b style="font-size:10px">Input</b><pre style="margin:2px 0;font-size:10px;white-space:pre-wrap;max-height:200px;overflow:auto">'+esc(String(t.input).slice(0,1000))+'</pre></div>';
      if(t.output) out.innerHTML+='<div style="margin-top:4px"><b style="font-size:10px">Output</b><pre style="margin:2px 0;font-size:10px;white-space:pre-wrap;max-height:200px;overflow:auto">'+esc(String(t.output).slice(0,1000))+'</pre></div>';
      return;
    }
    // Nothing to show but not an error
    if(j.spans) out.innerHTML='<div class="muted" style="font-size:11px">No spans for '+esc(id)+'</div>';
    else out.innerHTML='<div class="muted" style="font-size:11px">No trace data — only RAG requests with retrieval have pipeline traces. Check the Tracing tab for request_ids with traces, or <a href="#" onclick="loadTraces();return false">reload recent</a>.</div>';
  }catch(e){out.innerHTML='<span style="color:var(--err)">'+esc(e.message)+'</span>';}
}
function drawTraceGantt(svg, spans){ if(!svg || !spans.length) return; const w=svg.clientWidth||560, h=80, pad=10; svg.setAttribute('viewBox',`0 0 ${w} ${h}`); svg.innerHTML=''; const maxDur=Math.max(...spans.map(s=>s.duration_us||s.duration||1000),1000); spans.slice(0,8).forEach((s,i)=>{ const dur=s.duration_us||s.duration||0; const bw=Math.max(dur/maxDur*(w-pad*2), 4); const y=pad+i*9; const rect=document.createElementNS('http://www.w3.org/2000/svg','rect'); rect.setAttribute('x',pad); rect.setAttribute('y',y); rect.setAttribute('width',bw); rect.setAttribute('height',7); rect.setAttribute('fill', i%2?'#58a6ff':'#3fb950'); rect.setAttribute('opacity',0.8); svg.appendChild(rect); const txt=document.createElementNS('http://www.w3.org/2000/svg','text'); txt.setAttribute('x',pad+bw+4); txt.setAttribute('y',y+6); txt.setAttribute('fill','#8b949e'); txt.setAttribute('font-size','7'); txt.textContent=(s.name||s.operationName||s.id||'span').slice(0,24)+' '+Math.round(dur/1000)+'ms'; svg.appendChild(txt);});}
async function runTransparency(){const q=document.getElementById('transparencyQ').value||'اعتبارسنجی چیست'; const topK=parseInt(document.getElementById('transparencyTopK').value)||5; const boost=parseFloat(document.getElementById('transparencyBoost').value); const meta=document.getElementById('transparencyMeta'); const diag=document.getElementById('transparencyDiagram'); const bar=document.getElementById('transparencyBar'); const leg=document.getElementById('transparencyLegend'); const stagesEl=document.getElementById('transparencyStages'); const fin=document.getElementById('transparencyFinal'); const raw=document.getElementById('transparencyRaw'); if(meta) meta.textContent='running…'; if(diag) diag.innerHTML='<span class="muted">running pipeline…</span>'; try{const j=await fetchJSON(`/api/transparency?query=${encodeURIComponent(q)}&top_k=${topK}` + (isFinite(boost)?`&keyword_boost=${boost}`:'')); if(meta) meta.textContent=`total ${j.total_elapsed_ms}ms · chunks ${j.total_chunks_indexed} · tokens ${j.tokens.length}`; renderTransparency(j); if(raw) raw.textContent=JSON.stringify(j,null,2).slice(0,8000);}catch(e){ if(meta) meta.textContent='error '+e.message; if(diag) diag.textContent='error '+e.message;}}
function renderTransparency(j){ const diag=document.getElementById('transparencyDiagram'); const bar=document.getElementById('transparencyBar'); const leg=document.getElementById('transparencyLegend'); const stagesEl=document.getElementById('transparencyStages'); const fin=document.getElementById('transparencyFinal'); if(!j.stages) return; // diagram
  let html='<div style="display:flex;gap:4px;flex-wrap:wrap;align-items:center">'; j.stages.forEach((s,i)=>{ const col=s.status==='ok'?'var(--ok)':s.status==='skipped'?'var(--muted)':'var(--err)'; const w=Math.max(s.percent, 3); html+=`<div style="flex:0 0 auto;border:1px solid ${col};border-radius:8px;padding:6px 8px;background:#0d1117;min-width:70px;text-align:center"><div style="font-weight:600;color:${col}">${s.name}</div><div class="muted">${s.elapsed_ms}ms</div><div style="font-size:11px;color:${col}">${s.percent}%</div></div>`; if(i<j.stages.length-1) html+='<span style="color:var(--accent)">→</span>'; }); html+='</div>'; if(diag) diag.innerHTML=html;
  // stacked bar
  if(bar){ bar.innerHTML=''; const colors={"bm25":"#58a6ff","dense":"#a371f7","hyde":"#8b949e","rrf":"#d29922","rerank":"#f85149","build_context":"#3fb950","total":"#21262d"}; j.stages.forEach(s=>{ if(s.name==='total') return; const seg=document.createElement('div'); seg.style.width=s.percent+'%'; seg.style.background=colors[s.name]||'#58a6ff'; seg.title=s.name+' '+s.elapsed_ms+'ms '+s.percent+'%'; seg.style.height='100%'; bar.appendChild(seg);});}
  if(leg) leg.textContent=j.stages.map(s=>`${s.name} ${s.elapsed_ms}ms (${s.percent}%)`).join(' · ') + ` · config: boost ${j.config.keyword_boost} beam ${j.config.beam} rerank ${j.config.reranker_model} pgvector ${j.config.use_pgvector?'on':'off'}`;
  // stage cards
  if(stagesEl){ let out=''; const resultsMap={"bm25": j.bm25_results,"dense": j.dense_results,"rrf": j.merged_candidates}; j.stages.forEach(s=>{ if(s.name==='total'||s.name==='build_context') return; const res=resultsMap[s.name]||[]; const preview=res.slice(0,2).map(r=>`<tr><td><code>${(r.chunk_id||'').slice(0,8)}</code></td><td>${(r.doc_title||'').slice(0,20)}</td><td>${(r.heading_path||'').slice(0,20)}</td><td>${(r.bm25_score||r.dense_score||r.hybrid_score||r.rerank_score||0).toString().slice(0,6)}</td><td>${(r.content_preview||'').slice(0,80)}</td></tr>`).join('') || '<tr><td colspan=5 class="muted">no preview</td></tr>'; out+=`<details class="card" style="margin-top:8px" ${s.name==='rerank'?'open':''}><summary><b>${s.name}</b> <span class="badge-sm ${s.status==='ok'?'s-loaded':s.status==='skipped'?'s-available':'s-loading'}">${s.status}</span> ${s.elapsed_ms}ms ${s.percent}%</summary><table><tr><th>chunk</th><th>doc</th><th>heading</th><th>score</th><th>preview</th></tr>${preview}</table><div class="muted">count ${res.length} ${s.name==='hyde'?'skipped: KB_HYDE_ENABLED=false':''}</div></details>`; }); stagesEl.innerHTML=out;}
  if(fin){ fin.innerHTML=`<div class="card"><h4>Final <code>top_${j.final_results.length}</code> (rerank pool) — total ${j.total_elapsed_ms}ms</h4><table><tr><th>#</th><th>doc</th><th>heading</th><th>rerank</th><th>hybrid</th><th>preview</th></tr>`+j.final_results.map((r,i)=>`<tr><td>${i+1}</td><td>${(r.doc_title||'').slice(0,20)}</td><td>${(r.heading_path||'').slice(0,20)}</td><td>${(r.rerank_score||0).toFixed(3)}</td><td>${(r.hybrid_score||0).toFixed(4)}</td><td>${(r.content_preview||'').slice(0,100)}</td></tr>`).join('')+`</table><div class="muted">tokens ${j.tokens.length} · rerank ${j.rerank_ms}ms · config beam ${j.config.beam} fusion α ${j.config.fusion_alpha}</div></div>`;}
}
function refreshAll(){loadDashboard(); loadPanelsHealth(); if(document.getElementById('tab-litellm').style.display!=='none') loadLitellm(); if(document.getElementById('tab-transparency').style.display!=='none') loadTraces();}
loadDashboard(); loadPanelsHealth(); setInterval(()=>{loadDashboard(); loadPanelsHealth();}, 10000);
</script></body></html>
"""

@app.get("/public/health")
def public_health():
    return {"status":"ok","public": PUBLIC_MODE, "auth_required": PUBLIC_REQUIRE_AUTH, "manager":"llm_inference_manager","panels": list(PANEL_UPSTREAMS.keys())}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if PUBLIC_MODE and not verify_public_dashboard(request):
        return HTMLResponse("""<html><head><title>Auth required</title></head><body style="font-family:system-ui;padding:2rem;background:#0f1419;color:#e6edf3">
<h1>🔒 Public Dashboard — Authentication required</h1>
<p>This manager is in <code>PUBLIC_DASHBOARD=1</code> mode. Provide a token:</p>
<ul><li>Header: <code>Authorization: Bearer $LITELLM_MASTER_KEY</code></li><li>Query: <code>?token=$LITELLM_MASTER_KEY</code></li><li>Or generate via <code>POST /admin/tokens</code> on LAN</li></ul>
<p>Try: <code>/dashboard?token=YOUR_TOKEN</code></p>
<p>Health (no auth): <a href="/public/health" style="color:#58a6ff">/public/health</a> · <a href="/health" style="color:#58a6ff">/health</a></p>
</body></html>""", status_code=401)
    return HTMLResponse(DASHBOARD_HTML)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if PUBLIC_MODE and not verify_public_dashboard(request):
        return HTMLResponse("""<html><head><title>Auth required</title></head><body style="font-family:system-ui;padding:2rem;background:#0f1419;color:#e6edf3">
<h1>🔒 Public Dashboard — Authentication required</h1>
<p>This manager is in <code>PUBLIC_DASHBOARD=1</code> mode. Provide a token via <code>?token=</code> or <code>Authorization</code> header.</p>
<p><a href="/public/health" style="color:#58a6ff">/public/health</a></p>
</body></html>""", status_code=401)
    return HTMLResponse(DASHBOARD_HTML)


if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
