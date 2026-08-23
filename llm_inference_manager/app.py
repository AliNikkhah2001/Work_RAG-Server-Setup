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
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = pathlib.Path(__file__).parent / "manager.db"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

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
        "backends": ["http://127.0.0.1:8080", "http://127.0.0.1:8081", "http://127.0.0.1:8082", "http://127.0.0.1:8083", "http://127.0.0.1:8084"],
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
}

# Round-robin counters for load balancing
rr_counters: Dict[str, int] = {k:0 for k in MODEL_REGISTRY}

# Track spawned processes
spawned_processes: Dict[str, subprocess.Popen] = {}

app = FastAPI(title="LLM Inference Manager", version="1.0.0", description="OpenAI-compatible gateway with session/history, metrics, multi-model load balancing")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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
    conn.commit()
    # seed default token if none
    cur = conn.execute("SELECT count(*) FROM api_tokens")
    if cur.fetchone()[0]==0:
        conn.execute("INSERT INTO api_tokens(token,name,created_at) VALUES(?,?,?)", ("sk-local-dev", "default local", datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

init_db()

def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        return True  # allow anonymous for local dev - change to require token in prod
    token = authorization.replace("Bearer ","").strip()
    if token in ("sk-local-dev", "local", ""):
        return True
    conn=get_db()
    cur=conn.execute("SELECT 1 FROM api_tokens WHERE token=?", (token,))
    ok=cur.fetchone() is not None
    conn.close()
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

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

async def proxy_chat(model_id: str, payload: dict):
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
    # ensure max_tokens etc
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        r = await client.post(f"{backend}/v1/chat/completions", json=payload)
        if r.status_code!=200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

# --------------------------------------------------------------------------
# API: models
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status":"ok","manager":"llm_inference_manager","version":"1.0.0","gpus":gpu_info(),"models_loaded": sum(1 for m in MODEL_REGISTRY.values() if m["backends"]) }

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
    out = await proxy_chat(req.model, payload)
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
    # metrics
    try:
        conn=get_db()
        conn.execute("INSERT INTO metrics(id,model,endpoint,latency_ms,prompt_tokens,completion_tokens,created_at) VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()), req.model, "/v1/chat/completions", latency, 0, 0, datetime.utcnow().isoformat()))
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

@app.get("/api/dashboard")
async def api_dashboard():
    # aggregate everything for dashboard
    gpus = gpu_info()
    # model details with live health probe for loaded ones
    models=[]
    for mid, cfg in MODEL_REGISTRY.items():
        entry=dict(cfg)
        # probe backends if loaded
        health=[]
        if cfg.get("backends"):
            for b in cfg["backends"]:
                try:
                    import httpx as _hx
                    async with _hx.AsyncClient(timeout=2, trust_env=False) as c:
                        r=await c.get(f"{b}/health")
                        health.append({"backend":b,"status":r.status_code,"body":r.json() if r.status_code==200 else r.text[:200]})
                except Exception as e:
                    health.append({"backend":b,"status":"error","error":str(e)[:200]})
        entry["live_health"]=health
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
    return {
        "manager":{"version":"1.0.0","uptime": time.time(), "gpus": gpus, "models_loaded": sum(1 for m in MODEL_REGISTRY.values() if m["backends"])},
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

@app.get("/api/usage")
def api_usage():
    conn=get_db()
    rows=conn.execute("SELECT model, count(*) as cnt, avg(latency_ms) as avg_ms, max(latency_ms) as max_ms FROM metrics GROUP BY model").fetchall()
    recent=conn.execute("SELECT * FROM metrics ORDER BY created_at DESC LIMIT 30").fetchall()
    conn.close()
    return {"by_model":[dict(r) for r in rows], "recent":[dict(r) for r in recent]}

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
<button class="tab" data-t="embeds" onclick="switchTab('embeds')">Embeds & Docker</button>
<button class="tab" data-t="project" onclick="switchTab('project')">Project</button>
<button class="tab" data-t="usage" onclick="switchTab('usage')">Usage & Sessions</button>
<button class="tab" data-t="play" onclick="switchTab('play')">Playground</button>
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
<!-- USAGE -->
<div id="tab-usage" style="display:none">
<div class="grid cols2">
<div class="card"><h3>Usage by Model</h3><div id="usageByModel"></div></div>
<div class="card"><h3>Sessions (10 recent)</h3><div id="sessionsTbl"></div></div>
</div>
<div class="card" style="margin-top:14px"><h3>Recent Requests (10)</h3><div id="recentTbl"></div></div>
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
</div>
<script>
let D=null;
function switchTab(t){document.querySelectorAll('[id^="tab-"]').forEach(e=>e.style.display='none');document.getElementById('tab-'+t).style.display='block';document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));document.querySelector(`.tab[data-t="${t}"]`).classList.add('active')}
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
function renderUsage(){ if(!D) return; document.getElementById('usageByModel').innerHTML = D.metrics.by_model.length? D.metrics.by_model.map(b=>`<div class="kv"><span>${b.model}</span><span>${b.cnt} req avg ${Math.round(b.avg_ms)}ms</span></div>`).join('') : '<span class="muted">no usage yet</span>'; document.getElementById('sessionsTbl').innerHTML = D.metrics.sessions.length? D.metrics.sessions.map(s=>`<div class="kv"><span>${s.id.slice(0,8)} ${s.model}</span><span>${s.title.slice(0,20)} ${new Date(s.updated_at).toLocaleTimeString()}</span></div>`).join('') : 'no sessions'; document.getElementById('recentTbl').innerHTML = D.metrics.recent.map(r=>`<div class="kv"><span>${r.model} ${r.endpoint}</span><span>${Math.round(r.latency_ms)}ms ${new Date(r.created_at).toLocaleTimeString()}</span></div>`).join(''); document.getElementById('tokensTbl').innerHTML = D.metrics.tokens.map(t=>`<div class="kv"><span><code>${t.token.slice(0,12)}…</code> ${t.name}</span><span>${new Date(t.created_at).toLocaleDateString()}</span></div>`).join('');}
async function runModel(id){ const el=document.getElementById('msg-'+id); el.textContent='starting…'; try{ const r=await fetch(`/admin/models/load?model_id=${encodeURIComponent(id)}`,{method:'POST'}); const j=await r.json(); el.textContent= r.status==='already loaded'? 'already loaded '+j.backends : `spawned port ${j.port} gpu ${j.gpu} pid ${j.pid}`; setTimeout(loadDashboard,1500)} catch(e){el.textContent='error '+e.message}}
async function stopModel(id){ const el=document.getElementById('msg-'+id); el.textContent='stopping…'; try{ const r=await fetch(`/admin/models/unload?model_id=${encodeURIComponent(id)}`,{method:'POST'}); const j=await r.json(); el.textContent=j.status; loadDashboard()}catch(e){el.textContent='error '+e.message}}
async function testChat(id){ const out=document.getElementById('playOut')||null; try{ const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:id,messages:[{role:'user',content:'say hello one word'}],max_tokens:10})}); const j=await r.json(); alert(id+': '+(j.choices?.[0]?.message?.content||JSON.stringify(j).slice(0,300))); loadDashboard()} catch(e){alert('error '+e.message)}}
async function editModel(id){ const m=D.models.find(x=>x.id===id); const name=prompt('Edit name',m.name); if(name===null) return; const params=prompt('Edit params',m.params); if(params===null) return; try{ const r=await fetch(`/admin/models/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,params})}); const j=await r.json(); alert('patched '+j.model); loadDashboard()}catch(e){alert(e.message)}}
async function sendPlay(){ const id=document.getElementById('playModel').value; const prompt=document.getElementById('playPrompt').value; const mx=parseInt(document.getElementById('playMax').value)||50; const tp=parseFloat(document.getElementById('playTemp').value)||0.7; const out=document.getElementById('playOut'); out.textContent='sending…'; try{ const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:id,messages:[{role:'user',content:prompt}],max_tokens:mx,temperature:tp})}); const j=await r.json(); out.textContent=JSON.stringify(j,null,2)}catch(e){out.textContent='error '+e.message}}
async function sendEmbed(){ const txt=document.getElementById('embedInput').value; const out=document.getElementById('embedOut'); out.textContent='embedding…'; try{ const r=await fetch('http://127.0.0.1:8001/v1/embeddings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:txt})}); const j=await r.json(); out.textContent=`dim ${j.data[0].embedding.length}\nfirst 5: ${j.data[0].embedding.slice(0,5).map(x=>x.toFixed(4)).join(', ')}`}catch(e){ try{ const r=await fetch('/v1/embeddings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:txt})}); out.textContent=await r.text()}catch(e2){out.textContent='error '+e.message}}}
function testEmbeds(){ fetch('http://127.0.0.1:8001/health').then(r=>r.json()).then(j=>alert('8001 '+JSON.stringify(j))).catch(e=>alert(e.message))}
function refreshAll(){loadDashboard()}
loadDashboard(); setInterval(loadDashboard, 10000);
</script></body></html>
"""

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(DASHBOARD_HTML)

@app.get("/", response_class=HTMLResponse)
def index():
    # keep / also serving dashboard (backwards compat: old index still reachable via /?view=old)
    return HTMLResponse(DASHBOARD_HTML)


if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
