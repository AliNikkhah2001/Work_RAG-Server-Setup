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
@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!doctype html><html><head><meta charset=utf-8><title>LLM Inference Manager</title>
<style>body{font-family:system-ui;background:#0f1419;color:#e6edf3;padding:2rem} a{color:#58a6ff} table{border-collapse:collapse} th,td{padding:.4rem .6rem;border:1px solid #21262d} code{background:#161b22;padding:.1rem .3rem;border-radius:3px}</style></head><body>
<h1>LLM Inference Manager</h1>
<p>OpenAI-compatible gateway - <code>/v1/models</code> | <code>/v1/chat/completions</code> | sessions/history | metrics</p>
<ul>
<li><a href="/v1/models">GET /v1/models</a> - list all models</li>
<li><a href="/admin/status">GET /admin/status</a> - GPU & status</li>
<li><a href="/admin/metrics">GET /admin/metrics</a> - metrics</li>
<li><a href="/docs">/docs</a> - interactive API docs (Swagger)</li>
<li><a href="/v1/sessions">/v1/sessions</a> - chat sessions</li>
</ul>
<p>Connected frontends: <a href="http://192.168.96.82:13000">Open WebUI :13000</a> (configure OpenAI base <code>http://192.168.96.82:9000/v1</code>)</p>
<p><b>Gemma-4 API direct:</b> <code>curl http://127.0.0.1:9000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"Hello"}]}'</code></p>
</body></html>
"""

if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
