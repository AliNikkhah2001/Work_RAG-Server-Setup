#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import logging
import traceback
import shutil
import urllib.request
import importlib
from pathlib import Path
from datetime import datetime

# ========================= CONFIG =========================
PROXY_URL = "http://192.168.203.2:3128"
BASE_DIR = Path(__file__).resolve().parent / "offline-prep"
VENV_DIR = BASE_DIR / "venv"
STATE_FILE = BASE_DIR / ".state.json"
RETRY_QUEUE = BASE_DIR / ".retry_queue.json"
REPORT_FILE = BASE_DIR / "COMPREHENSIVE_REPORT.md"
LOG_DIR = BASE_DIR / "logs"

# Redirect pip cache to large drive
os.environ["PIP_CACHE_DIR"] = str(BASE_DIR / "pip_cache")
os.makedirs(os.environ["PIP_CACHE_DIR"], exist_ok=True)

os.environ.update({
    "HTTP_PROXY": PROXY_URL,
    "HTTPS_PROXY": PROXY_URL,
    "http_proxy": PROXY_URL,
    "https_proxy": PROXY_URL,
    "HF_XET_HIGH_PERFORMANCE": "1",
    "UV_HTTP_TIMEOUT": "600",
    "PYTHONUNBUFFERED": "1"  # Force Python to not buffer output
})

# Ensure directories
for d in [BASE_DIR, VENV_DIR, LOG_DIR, BASE_DIR / "docker-images",
          BASE_DIR / "python-packages", BASE_DIR / "python-packages-cu124",
          BASE_DIR / "models" / "huggingface", BASE_DIR / "models" / "gguf",
          BASE_DIR / "inference-engines", BASE_DIR / "sample-projects"]:
    d.mkdir(parents=True, exist_ok=True)

# ========================= LOGGING =========================
def setup_logging():
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(LOG_DIR / "main.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    error_handler = logging.FileHandler(LOG_DIR / "errors.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(error_handler)
    return logging.getLogger()

logger = setup_logging()

# ========================= UTILITIES =========================
def run_cmd(cmd, max_retries=5, timeout=900, cwd=None, env=None):
    """Run command with retries - fully automated"""
    for attempt in range(1, max_retries + 1):
        try:
            run_env = os.environ.copy()
            if env:
                run_env.update(env)
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=run_env
            )
            if proc.returncode == 0:
                logger.info(f"Command succeeded: {' '.join(cmd[:2])}")
                return True, proc.stdout
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {proc.stderr.strip()[:200]}")
            if "No space left" in proc.stderr:
                logger.error("Disk space error! Cleaning up...")
                cleanup_disk_space()
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout on attempt {attempt}")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        if attempt < max_retries:
            wait = 15 * attempt  # Longer wait between retries
            logger.info(f"Retrying in {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
    return False, "Max retries exceeded"

def cleanup_disk_space():
    """Try to free up disk space automatically"""
    try:
        # Clean pip cache
        subprocess.run(["pip", "cache", "purge"], capture_output=True)
        # Clean uv cache
        subprocess.run(["uv", "cache", "clean"], capture_output=True)
        logger.info("Cache cleaned")
    except:
        pass

def get_venv_pip():
    return str(VENV_DIR / "bin" / "pip")

def get_venv_uv():
    return str(VENV_DIR / "bin" / "uv")

def get_venv_python():
    return str(VENV_DIR / "bin" / "python")

def activate_venv():
    bin_dir = VENV_DIR / "bin"
    if not bin_dir.exists():
        raise RuntimeError(f"Venv not found at {VENV_DIR}")
    os.environ["PATH"] = f"{bin_dir}:{os.environ['PATH']}"
    os.environ["VIRTUAL_ENV"] = str(VENV_DIR)

# ========================= PRE‑CHECKS =========================
def check_connectivity():
    logger.info("Checking connectivity via proxy...")
    try:
        req = urllib.request.Request("https://pypi.org", headers={"User-Agent": "Mozilla/5.0"})
        urllib.request.urlopen(req, timeout=10)
        logger.info("Connectivity OK")
        return True
    except Exception as e:
        logger.error(f"Connectivity failed: {e}")
        return False

def check_tools():
    tools = {
        "python": ["python3", "--version"],
        "pip": ["pip", "--version"],
        "docker": ["docker", "--version"],
        "git": ["git", "--version"],
    }
    results = {}
    for name, cmd in tools.items():
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"{name} found")
            results[name] = True
        except Exception:
            logger.warning(f"{name} not found")
            results[name] = False
    return results

def create_venv():
    if VENV_DIR.exists():
        logger.info("Venv already exists")
        return True
    logger.info("Creating virtual environment...")
    try:
        subprocess.run(["python3", "-m", "venv", str(VENV_DIR)], check=True)
        logger.info("Venv created")
        return True
    except Exception as e:
        logger.error(f"Venv creation failed: {e}")
        return False

def install_core_tools():
    pip = get_venv_pip()
    run_cmd([pip, "install", "--upgrade", "pip"])
    run_cmd([pip, "install", "uv"])
    run_cmd([pip, "install", "--upgrade", "huggingface-hub"])
    try:
        subprocess.run(["hf", "--help"], check=True, capture_output=True)
        logger.info("hf CLI installed")
    except:
        logger.warning("hf CLI not found; reinstalling")
        run_cmd([pip, "install", "--upgrade", "huggingface-hub"])
    return True

# ========================= STATE =========================
class State:
    def __init__(self):
        self.data = {"items": {}, "max_retries": 5}  # Increased retries
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    self.data = json.load(f)
            except:
                pass
        self.retry_queue = []
        if RETRY_QUEUE.exists():
            try:
                with open(RETRY_QUEUE) as f:
                    self.retry_queue = json.load(f)
            except:
                pass

    def save(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.data, f, indent=2)
        with open(RETRY_QUEUE, "w") as f:
            json.dump(self.retry_queue, f, indent=2)

    def is_done(self, key):
        return self.data["items"].get(key, {}).get("status") == "completed"

    def set_status(self, key, status, details=""):
        item = self.data["items"].get(key, {})
        item["status"] = status
        item["details"] = details[:500]  # Truncate long messages
        item["updated"] = datetime.now().isoformat()
        item["retries"] = item.get("retries", 0)
        if status == "failed":
            item["retries"] += 1
            if item["retries"] <= self.data["max_retries"] and key not in self.retry_queue:
                self.retry_queue.append(key)
        else:
            if key in self.retry_queue:
                self.retry_queue.remove(key)
        self.data["items"][key] = item
        self.save()

    def get_pending(self):
        all_keys = set()
        for img, _ in DOCKER_IMAGES:
            all_keys.add(f"docker_{img}")
        for pkg in CUDA_PACKAGES + STD_PACKAGES:
            all_keys.add(f"pip_{pkg}")
        for model in MODELS:
            all_keys.add(f"model_{model}")
        for proj in PROJECTS:
            all_keys.add(f"project_{proj['name']}")

        done = set(self.data["items"].keys())
        pending = all_keys - done
        for key in self.retry_queue:
            if key not in pending:
                pending.add(key)
        return list(pending)

state = State()

# ========================= TASK DEFINITIONS =========================
DOCKER_IMAGES = [
    ("ghcr.io/open-webui/open-webui:main", "Open WebUI"),
    ("vllm/vllm-openai:latest", "vLLM"),
    ("nvidia/cuda:12.8.0-runtime-ubuntu22.04", "CUDA 12.8 Runtime"),
    ("pgvector/pgvector:pg16", "pgvector"),
    ("milvusdb/milvus:latest", "Milvus"),
    ("qdrant/qdrant:latest", "Qdrant"),
    ("redis:7-alpine", "Redis"),
]

CUDA_PACKAGES = [
    "torch==2.4.0",
    "torchvision==0.19.0",
    "torchaudio==2.4.0",
    "xformers==0.0.27.post2",
    "flash-attn==2.6.3",
    "vllm==0.6.1.post1",
    "triton==3.0.0",
    "faiss-gpu==1.8.0",
]

STD_PACKAGES = [
    "transformers", "accelerate", "bitsandbytes", "sentence-transformers",
    "fastapi", "uvicorn", "langchain", "llama-index", "pandas",
    "numpy", "scipy", "pydantic", "httpx", "aiohttp", "docling",
    "unstructured", "pypdf", "pdfplumber", "markdown",
    "chromadb", "pymilvus", "qdrant-client", "redis",
    "ragas", "deepeval", "litellm", "openai",
]

MODELS = {
    "Qwen/Qwen2.5-7B-Instruct-GGUF": "Qwen 2.5 7B (Official GGUF)",
    "bartowski/Llama-3.2-3B-Instruct-GGUF": "Llama 3.2 3B (bartowski GGUF)",
    "bartowski/Mistral-7B-Instruct-v0.3-GGUF": "Mistral 7B v0.3 (bartowski GGUF)",
    "microsoft/Phi-3-mini-4k-instruct-gguf": "Phi-3 Mini (Microsoft GGUF)",
    "BAAI/bge-small-en-v1.5": "BGE Small Embeddings",
    "sentence-transformers/all-MiniLM-L6-v2": "MiniLM Embeddings",
}

PROJECTS = [
    {"name": "dify", "url": "https://github.com/langgenius/dify.git"},
    {"name": "anything-llm", "url": "https://github.com/mintplex-labs/anything-llm.git"},
    {"name": "ragflow", "url": "https://github.com/infiniflow/ragflow.git"},
    {"name": "lightrag", "url": "https://github.com/hkuds/lightrag.git"},
]

# ========================= TASK EXECUTORS =========================
def pull_docker(image):
    logger.info(f"Pulling {image}")
    success, _ = run_cmd(["docker", "pull", image], max_retries=5, timeout=1200)
    if not success:
        return False, "Docker pull failed"
    tar = BASE_DIR / "docker-images" / f"{image.replace('/', '_').replace(':', '_')}.tar"
    return run_cmd(["docker", "save", "-o", str(tar), image], max_retries=3, timeout=600)

def install_python_package(pkg, cuda=False):
    logger.info(f"Installing {pkg} (CUDA: {cuda})")
    uv = get_venv_uv()
    
    # Try uv first
    cmd = [uv, "pip", "install", pkg]
    if cuda:
        cmd.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    if pkg.startswith("triton"):
        cmd.append("--no-cache-dir")
    if pkg.startswith("flash-attn"):
        cmd.append("--no-build-isolation")
    if pkg.startswith("vllm"):
        cmd.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
        cmd.extend(["--extra-index-url", "https://pypi.org/simple"])
    
    success, _ = run_cmd(cmd, max_retries=3, timeout=900)
    if success:
        return True, "Install OK with uv"
    
    # Fallback to pip
    logger.info(f"Falling back to pip for {pkg}")
    pip = get_venv_pip()
    cmd_pip = [pip, "install", pkg]
    if cuda:
        cmd_pip.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    if pkg.startswith("triton"):
        cmd_pip.append("--no-cache-dir")
    if pkg.startswith("flash-attn"):
        cmd_pip.append("--no-build-isolation")
    if pkg.startswith("vllm"):
        cmd_pip.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    
    success, _ = run_cmd(cmd_pip, max_retries=5, timeout=900)
    if success:
        return True, "Install OK with pip"
    
    return False, "Install failed"

def download_hf_model(repo_id):
    logger.info(f"Downloading {repo_id}")
    dest = BASE_DIR / "models" / "huggingface" / repo_id.replace("/", "_")
    env = os.environ.copy()
    env["HF_XET_HIGH_PERFORMANCE"] = "1"
    if "HF_TOKEN" in os.environ:
        env["HF_TOKEN"] = os.environ["HF_TOKEN"]
    
    cmd = [
        "hf", "download",
        repo_id,
        "--local-dir", str(dest)
    ]
    success, _ = run_cmd(cmd, max_retries=5, timeout=7200, env=env)
    if success:
        return True, "Download OK"
    
    # Fallback to Python API
    logger.info("Falling back to Python API...")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(dest),
            local_dir_use_symlinks=False,
            resume_download=True,
            token=os.environ.get("HF_TOKEN"),
            proxies={"http": PROXY_URL, "https": PROXY_URL}
        )
        return True, "Downloaded via API"
    except Exception as e:
        return False, f"API fallback failed: {e}"

def setup_project(proj):
    name, url = proj["name"], proj["url"]
    logger.info(f"Cloning {name}")
    dest = BASE_DIR / "sample-projects" / name
    if dest.exists():
        shutil.rmtree(dest)
    success, _ = run_cmd(["git", "clone", url, str(dest)], max_retries=5, timeout=300)
    if not success:
        return False, "Clone failed"
    req = dest / "requirements.txt"
    if req.exists():
        uv = get_venv_uv()
        success, _ = run_cmd([uv, "pip", "install", "-r", str(req)],
                             cwd=str(dest), max_retries=3, timeout=600)
        if not success:
            return False, "Dependencies failed"
    return True, "Project ready"

# ========================= MAIN =========================
def main():
    print("\n" + "="*80)
    print(" H200 Offline Preparation Tool (AUTOMATED MODE)")
    print(f" Proxy: {PROXY_URL}")
    print(f" Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Set max retries to 5 for automation
    state.data["max_retries"] = 5
    state.save()

    # ---- Pre-checks ----
    print("\n--- Running pre-checks ---")
    check_connectivity()
    check_tools()
    if not create_venv():
        logger.error("Failed to create venv. Exiting.")
        return
    activate_venv()
    install_core_tools()
    print("Pre-checks done.\n")

    # ---- All tasks selected automatically ----
    selection = {
        "docker": [img for img, _ in DOCKER_IMAGES],
        "cuda": CUDA_PACKAGES,
        "std": STD_PACKAGES,
        "models": list(MODELS.keys()),
        "projects": [p["name"] for p in PROJECTS]
    }

    # Build task list
    all_tasks = []
    for img in selection["docker"]:
        all_tasks.append(("docker", f"docker_{img}", img))
    for pkg in selection["cuda"]:
        all_tasks.append(("pip_cuda", f"pip_{pkg}", pkg, True))
    for pkg in selection["std"]:
        all_tasks.append(("pip_std", f"pip_{pkg}", pkg, False))
    for model in selection["models"]:
        all_tasks.append(("model", f"model_{model}", model))
    for proj_name in selection["projects"]:
        proj = next(p for p in PROJECTS if p["name"] == proj_name)
        all_tasks.append(("project", f"project_{proj_name}", proj))

    # ---- Main execution loop with auto-retry ----
    max_rounds = 10  # Prevent infinite loops
    for round_num in range(max_rounds):
        pending = state.get_pending()
        pending = [key for key in pending if any(key == t[1] for t in all_tasks)]

        if not pending:
            print("\nAll tasks completed successfully!")
            break

        print(f"\n=== Round {round_num + 1}/{max_rounds}: {len(pending)} tasks pending ===")

        for key in pending:
            if state.is_done(key):
                continue
            task = next((t for t in all_tasks if t[1] == key), None)
            if not task:
                continue

            print(f"\n[PROCESSING] {key}")
            try:
                if task[0] == "docker":
                    ok, msg = pull_docker(task[2])
                elif task[0] in ("pip_cuda", "pip_std"):
                    ok, msg = install_python_package(task[2], task[3])
                elif task[0] == "model":
                    ok, msg = download_hf_model(task[2])
                elif task[0] == "project":
                    ok, msg = setup_project(task[2])
                else:
                    continue
            except Exception as e:
                ok, msg = False, str(e)

            if ok:
                state.set_status(key, "completed", msg)
                print(f"[OK] {key}")
            else:
                state.set_status(key, "failed", msg)
                print(f"[FAIL] {key} - {msg[:100]}")
                # It will be retried in the next round

        # Check if we need to continue
        if round_num == max_rounds - 1:
            print("\nWARNING: Max rounds reached. Some tasks may still be pending.")
            break

        # Wait before next round
        if state.retry_queue:
            wait_time = 60  # Wait 1 minute before retrying
            print(f"\nWaiting {wait_time}s before retrying failed tasks...")
            time.sleep(wait_time)

    # ---- Final import verification ----
    print("\n" + "="*80)
    print(" FINAL IMPORT VERIFICATION")
    print("="*80)
    if VENV_DIR.exists():
        activate_venv()
        python = get_venv_python()
        import_results = {}
        packages = ["torch", "transformers", "accelerate", "huggingface_hub",
                    "vllm", "fastapi", "uvicorn", "langchain", "llama_index",
                    "sentence_transformers", "pandas", "numpy", "scipy", "pydantic"]
        for pkg in packages:
            try:
                cmd = [python, "-c", f"import {pkg.replace('-', '_')}; print('OK')"]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0:
                    import_results[pkg] = "OK"
                else:
                    import_results[pkg] = "FAIL"
            except:
                import_results[pkg] = "FAIL"
        ok_count = sum(1 for v in import_results.values() if v == "OK")
        fail_count = len(import_results) - ok_count
        print(f"Imports: {ok_count} OK, {fail_count} FAIL")
        for pkg, status in import_results.items():
            print(f"  {pkg}: {status}")

    # ---- Generate final report ----
    generate_report()

    print("\n" + "="*80)
    print(" FINAL SUMMARY")
    print("="*80)
    total = len(state.data["items"])
    done = sum(1 for v in state.data["items"].values() if v["status"] == "completed")
    failed = sum(1 for v in state.data["items"].values() if v["status"] == "failed")
    print(f"Total tasks: {total}")
    print(f"Completed: {done}")
    print(f"Failed: {failed}")
    if state.retry_queue:
        print(f"Retry queue: {len(state.retry_queue)} tasks remaining")
        print(f"These tasks exceeded max retries ({state.data['max_retries']})")
    print(f"Report: {REPORT_FILE}")
    print(f"Logs: {LOG_DIR}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def generate_report():
    with open(REPORT_FILE, "w") as f:
        f.write("# Offline Preparation Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        total = len(state.data["items"])
        done = sum(1 for v in state.data["items"].values() if v["status"] == "completed")
        failed = sum(1 for v in state.data["items"].values() if v["status"] == "failed")
        f.write(f"- Total tasks: {total}\n")
        f.write(f"- Completed: {done}\n")
        f.write(f"- Failed: {failed}\n")
        f.write(f"- Retry queue: {len(state.retry_queue)}\n\n")
        f.write("## Failed Tasks\n")
        for key, item in state.data["items"].items():
            if item["status"] == "failed":
                f.write(f"- {key}: {item['details'][:200]}\n")
    logger.info(f"Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    main()
