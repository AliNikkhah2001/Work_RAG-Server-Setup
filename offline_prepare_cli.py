#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import logging
import importlib
import traceback
from pathlib import Path
from datetime import datetime
import click

# ======================== CONFIGURATION ========================
BASE_DIR = Path("./offline-prep")
STATE_FILE = BASE_DIR / ".state.json"
PROJECTS_DIR = BASE_DIR / "sample-projects"
REPORT_FILE = BASE_DIR / "COMPREHENSIVE_REPORT.md"
RETRY_QUEUE = BASE_DIR / ".retry_queue.json"
LOG_FILE = BASE_DIR / "download.log"
ERROR_LOG = BASE_DIR / "errors.log"
FAILED_TASKS_LOG = BASE_DIR / "failed_tasks.log"
DEBUG_LOG = BASE_DIR / "debug.log"
IMPORT_REPORT = BASE_DIR / "import_report.txt"

# Proxy configuration
PROXY_URL = "http://192.168.203.2:3128"

# Set proxy environment variables
os.environ['HTTP_PROXY'] = PROXY_URL
os.environ['HTTPS_PROXY'] = PROXY_URL
os.environ['http_proxy'] = PROXY_URL
os.environ['https_proxy'] = PROXY_URL

DIRS = {
    "docker": BASE_DIR / "docker-images",
    "python": BASE_DIR / "python-packages",
    "python_cu124": BASE_DIR / "python-packages-cu124",
    "models_hf": BASE_DIR / "models" / "huggingface",
    "models_gguf": BASE_DIR / "models" / "gguf",
    "inference": BASE_DIR / "inference-engines",
    "bin": BASE_DIR / "bin",
    "logs": BASE_DIR / "logs"
}

for d in DIRS.values(): d.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Add bin to PATH
os.environ["PATH"] = f"{DIRS['bin']}:{os.environ.get('PATH', '')}"

# ======================== LOGGING SETUP ========================
class Logger:
    def __init__(self):
        self.base_dir = BASE_DIR
        self.setup_logging()
        
    def setup_logging(self):
        main_logger = logging.getLogger('main')
        main_logger.setLevel(logging.INFO)
        main_handler = logging.FileHandler(LOG_FILE)
        main_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        main_logger.addHandler(main_handler)
        
        error_logger = logging.getLogger('error')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(ERROR_LOG)
        error_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s\n%(exc_info)s\n'))
        error_logger.addHandler(error_handler)
        
        debug_logger = logging.getLogger('debug')
        debug_logger.setLevel(logging.DEBUG)
        debug_handler = logging.FileHandler(DEBUG_LOG)
        debug_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        debug_logger.addHandler(debug_handler)
        
        failed_logger = logging.getLogger('failed')
        failed_logger.setLevel(logging.INFO)
        failed_handler = logging.FileHandler(FAILED_TASKS_LOG)
        failed_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        failed_logger.addHandler(failed_handler)
        
        self.main_logger = main_logger
        self.error_logger = error_logger
        self.debug_logger = debug_logger
        self.failed_logger = failed_logger
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.main_logger.addHandler(console_handler)
    
    def info(self, msg):
        self.main_logger.info(msg)
        self.debug_logger.info(msg)
        print(msg)
    
    def warning(self, msg):
        self.main_logger.warning(msg)
        self.debug_logger.warning(msg)
        print(f"WARNING: {msg}")
    
    def error(self, msg, exc_info=None):
        self.main_logger.error(msg)
        self.error_logger.error(msg, exc_info=exc_info)
        self.debug_logger.error(msg, exc_info=exc_info)
        self.failed_logger.error(msg)
        if exc_info:
            self.failed_logger.error(f"Traceback: {exc_info}")
        print(f"ERROR: {msg}")
    
    def debug(self, msg):
        self.debug_logger.debug(msg)
    
    def failed_task(self, task_name, error_msg, retries=0):
        timestamp = datetime.now().isoformat()
        entry = f"""
{'='*80}
FAILED TASK: {task_name}
Timestamp: {timestamp}
Retries: {retries}
Error: {error_msg}
{'='*80}
"""
        self.failed_logger.info(entry)
        self.error_logger.error(entry)
        
        failed_file = self.base_dir / "failed_tasks.json"
        try:
            if failed_file.exists():
                with open(failed_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {"failed_tasks": []}
            
            data["failed_tasks"].append({
                "task": task_name,
                "timestamp": timestamp,
                "retries": retries,
                "error": error_msg,
                "full_trace": traceback.format_exc()
            })
            
            with open(failed_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.error(f"Failed to write failed_tasks.json: {e}")

logger = Logger()

# ======================== PRE-INSTALLATION CHECKS ========================
def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f" {text}")
    print("="*80)

def print_subheader(text):
    """Print a formatted subheader"""
    print(f"\n--- {text} ---")

def check_connectivity():
    """Check internet connectivity through proxy"""
    print_subheader("Checking Network Connectivity")
    
    try:
        import urllib.request
        import socket
        
        # Set proxy handler
        proxy_handler = urllib.request.ProxyHandler({
            'http': PROXY_URL,
            'https': PROXY_URL
        })
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)
        
        # Test with multiple endpoints
        endpoints = [
            "https://pypi.org",
            "https://huggingface.co",
            "https://github.com",
            "https://download.pytorch.org"
        ]
        
        for endpoint in endpoints:
            try:
                response = urllib.request.urlopen(endpoint, timeout=10)
                logger.info(f"PASS: Connected to {endpoint}")
                print(f"  [PASS] {endpoint}")
            except Exception as e:
                logger.warning(f"FAIL: Could not reach {endpoint}: {str(e)}")
                print(f"  [FAIL] {endpoint} - {str(e)[:50]}")
                
    except Exception as e:
        logger.error(f"Connectivity check failed: {e}")
        return False
    
    return True

def check_tools():
    """Check if required tools are installed"""
    print_subheader("Checking Required Tools")
    
    tools_status = {}
    
    tools_to_check = {
        'python': ['python3', '--version'],
        'pip': ['pip', '--version'],
        'uv': ['uv', '--version'],
        'docker': ['docker', '--version'],
        'git': ['git', '--version'],
        'huggingface-cli': ['huggingface-cli', '--version'],
    }
    
    for tool_name, cmd in tools_to_check.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                logger.info(f"FOUND: {tool_name} - {version}")
                print(f"  [PASS] {tool_name}: {version}")
                tools_status[tool_name] = True
            else:
                logger.warning(f"MISSING: {tool_name}")
                print(f"  [FAIL] {tool_name} - not found")
                tools_status[tool_name] = False
        except Exception as e:
            logger.warning(f"MISSING: {tool_name}")
            print(f"  [FAIL] {tool_name} - not found")
            tools_status[tool_name] = False
    
    return tools_status

def create_virtual_environment():
    """Create and activate virtual environment"""
    print_subheader("Setting up Virtual Environment")
    
    venv_path = BASE_DIR / "venv"
    
    if venv_path.exists():
        logger.info(f"Virtual environment already exists at {venv_path}")
        print(f"  [PASS] Virtual environment exists at: {venv_path}")
        return venv_path
    
    try:
        logger.info(f"Creating virtual environment at {venv_path}")
        subprocess.run(
            ["python3", "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True
        )
        logger.info("Virtual environment created successfully")
        print(f"  [PASS] Virtual environment created at: {venv_path}")
        
        # Get python path in venv
        venv_python = venv_path / "bin" / "python3"
        venv_pip = venv_path / "bin" / "pip"
        
        # Upgrade pip in venv
        subprocess.run(
            [str(venv_pip), "install", "--upgrade", "pip", 
             "--proxy", PROXY_URL],
            capture_output=True
        )
        logger.info("Pip upgraded in virtual environment")
        
        return venv_path
        
    except Exception as e:
        logger.error(f"Failed to create virtual environment: {e}")
        return None

def install_missing_tools(tools_status):
    """Install missing tools if possible"""
    print_subheader("Installing Missing Tools")
    
    venv_path = BASE_DIR / "venv"
    venv_pip = venv_path / "bin" / "pip"
    
    if not tools_status.get('uv', False):
        logger.info("Installing uv...")
        try:
            subprocess.run(
                [str(venv_pip), "install", "uv", "--proxy", PROXY_URL],
                check=True
            )
            print("  [PASS] uv installed successfully")
            tools_status['uv'] = True
        except Exception as e:
            logger.error(f"Failed to install uv: {e}")
    
    if not tools_status.get('huggingface-cli', False):
        logger.info("Installing huggingface-cli...")
        try:
            subprocess.run(
                [str(venv_pip), "install", "huggingface-hub[cli]", 
                 "--proxy", PROXY_URL],
                check=True
            )
            print("  [PASS] huggingface-cli installed successfully")
            tools_status['huggingface-cli'] = True
        except Exception as e:
            logger.error(f"Failed to install huggingface-cli: {e}")
    
    return tools_status

# ======================== IMPORT VERIFICATION ========================
def verify_imports():
    """Verify all installed packages can be imported"""
    print_subheader("Verifying Package Imports")
    
    packages_to_check = [
        'torch',
        'transformers',
        'accelerate',
        'huggingface_hub',
        'vllm',
        'fastapi',
        'uvicorn',
        'langchain',
        'llama_index',
        'sentence_transformers',
        'pandas',
        'numpy',
        'scipy',
        'pydantic'
    ]
    
    import_results = {}
    
    for pkg in packages_to_check:
        try:
            # Handle package names with hyphens
            import_name = pkg.replace('-', '_')
            module = importlib.import_module(import_name)
            
            # Get version if available
            version = getattr(module, '__version__', 'unknown')
            import_results[pkg] = {'status': 'OK', 'version': version}
            logger.info(f"IMPORT OK: {pkg} (version: {version})")
            print(f"  [PASS] {pkg} - version: {version}")
        except ImportError as e:
            import_results[pkg] = {'status': 'FAIL', 'error': str(e)}
            logger.error(f"IMPORT FAIL: {pkg} - {e}")
            print(f"  [FAIL] {pkg} - {str(e)[:50]}")
    
    # Generate import report
    with open(IMPORT_REPORT, 'w') as f:
        f.write("=== IMPORT VERIFICATION REPORT ===\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        
        passed = sum(1 for v in import_results.values() if v['status'] == 'OK')
        failed = sum(1 for v in import_results.values() if v['status'] == 'FAIL')
        
        f.write(f"Total packages checked: {len(packages_to_check)}\n")
        f.write(f"Passed: {passed}\n")
        f.write(f"Failed: {failed}\n\n")
        
        f.write("--- DETAILED RESULTS ---\n")
        for pkg, result in import_results.items():
            status = "[OK]" if result['status'] == 'OK' else "[FAIL]"
            f.write(f"{status} {pkg}")
            if result['status'] == 'OK':
                f.write(f" - version: {result['version']}\n")
            else:
                f.write(f" - error: {result['error']}\n")
    
    return import_results

# ======================== PRE-INSTALLATION MAIN ========================
def run_pre_installation_checks():
    """Run all pre-installation checks"""
    print_header("PRE-INSTALLATION CHECKS")
    
    results = {}
    
    # Step 1: Check connectivity
    results['connectivity'] = check_connectivity()
    
    # Step 2: Check tools
    tools_status = check_tools()
    results['tools'] = tools_status
    
    # Step 3: Create virtual environment
    venv_path = create_virtual_environment()
    results['venv'] = venv_path
    
    # Step 4: Install missing tools
    if venv_path:
        tools_status = install_missing_tools(tools_status)
        results['tools'] = tools_status
    
    # Step 5: Verify imports (if venv exists)
    if venv_path:
        # Activate venv for import check
        venv_python = venv_path / "bin" / "python3"
        
        try:
            # Check if we can import from venv
            result = subprocess.run(
                [str(venv_python), "-c", 
                 "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Virtual environment Python: {result.stdout.strip()}")
            print(f"\n  [PASS] Virtual environment active at: {venv_path}")
        except Exception as e:
            logger.error(f"Virtual environment not active: {e}")
    
    print("\n" + "="*80)
    print(" PRE-INSTALLATION CHECK COMPLETE")
    print("="*80)
    
    return results

# ======================== H200 OPTIMIZED ECOSYSTEM ========================

def detect_cuda_version():
    """Detect CUDA version from nvidia-smi"""
    logger.info("Detecting CUDA version...")
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version,cuda_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.strip()
        if output:
            parts = output.split(',')
            driver_version = parts[0].strip()
            cuda_version = parts[1].strip() if len(parts) > 1 else "Unknown"
            
            logger.info(f"Driver: {driver_version}, CUDA: {cuda_version}")
            print(f"  [PASS] GPU detected: Driver {driver_version}, CUDA {cuda_version}")
            
            try:
                cuda_parts = cuda_version.split('.')
                if cuda_parts:
                    cuda_major = int(cuda_parts[0])
                    cuda_minor = int(cuda_parts[1]) if len(cuda_parts) > 1 else 0
                    return cuda_major, cuda_minor, driver_version
            except Exception as e:
                logger.warning(f"Could not parse CUDA version: {e}")
                return 13, 0, driver_version
            
        return 13, 0, "Unknown"
    except Exception as e:
        logger.warning(f"Could not detect CUDA: {e}")
        return 13, 0, "Unknown"

CUDA_MAJOR, CUDA_MINOR, DRIVER_VERSION = detect_cuda_version()
CUDA_VERSION = f"{CUDA_MAJOR}.{CUDA_MINOR}"

# Based on CUDA version, select appropriate package versions
if CUDA_MAJOR >= 13:
    TORCH_VERSION = "2.5.0"
    TORCH_CUDA = "cu124"
    VLLM_VERSION = "0.6.0"
    FLASH_ATTN_VERSION = "2.6.0"
    XFORMERS_VERSION = "0.0.28"
else:
    TORCH_VERSION = "2.4.0"
    TORCH_CUDA = "cu124"
    VLLM_VERSION = "0.5.0"
    FLASH_ATTN_VERSION = "2.5.9"
    XFORMERS_VERSION = "0.0.27"

DOCKER_IMAGES = [
    ("ghcr.io/open-webui/open-webui:main", "Open WebUI"),
    ("vllm/vllm-openai:latest", "vLLM Inference Server"),
    (f"nvidia/cuda:{CUDA_VERSION}-runtime-ubuntu22.04", f"CUDA {CUDA_VERSION} Runtime"),
    ("pgvector/pgvector:pg16", "PostgreSQL+pgvector"),
    ("milvusdb/milvus:latest", "Milvus Vector DB"),
    ("qdrant/qdrant:latest", "Qdrant Vector DB"),
    ("redis:7-alpine", "Redis"),
]

PYTHON_PACKAGES = [
    f"torch=={TORCH_VERSION}+{TORCH_CUDA}",
    f"torchvision=={TORCH_VERSION}+{TORCH_CUDA}",
    f"torchaudio=={TORCH_VERSION}+{TORCH_CUDA}",
    f"xformers=={XFORMERS_VERSION}+{TORCH_CUDA}",
    f"flash-attn=={FLASH_ATTN_VERSION}+{TORCH_CUDA}",
    f"triton==3.0.0+{TORCH_CUDA}",
    f"vllm=={VLLM_VERSION}+{TORCH_CUDA}",
    "sglang==0.3.0",
    "transformers==4.44.0",
    "accelerate==0.33.0",
    "bitsandbytes==0.43.3",
    "sentence-transformers==3.0.1",
    "faiss-gpu==1.8.0",
    "cupy-cuda12x==13.2.0",
    "fastapi", "pydantic", "uvicorn", "httpx", "aiohttp",
    "docling", "unstructured", "pypdf", "pdfplumber", "markdown",
    "langchain", "langgraph", "llama-index", "chromadb",
    "pymilvus", "qdrant-client", "redis",
    "ragas", "deepeval", "litellm", "openai",
    "scipy", "numpy", "pandas",
]

CUDA_EXTRA_PACKAGES = [
    f"cuda-python=={CUDA_VERSION}.0",
    "pycuda==2024.1",
    "numba==0.60.0",
]

MODELS = {
    "TheBloke/Llama-3.2-3B-Instruct-GGUF": "Llama 3.2 3B (Q4_K_M)",
    "TheBloke/Mistral-7B-Instruct-v0.3-GGUF": "Mistral 7B (Q4_K_M)",
    "TheBloke/Qwen2.5-7B-Instruct-GGUF": "Qwen 7B (Q4_K_M)",
    "TheBloke/Phi-3-mini-4k-instruct-GGUF": "Phi-3 Mini (Q4_K_M)",
    "BAAI/bge-small-en-v1.5": "BGE Small Embeddings",
    "sentence-transformers/all-MiniLM-L6-v2": "MiniLM Embeddings",
}

SAMPLE_PROJECTS = [
    {"name": "dify", "url": "https://github.com/langgenius/dify.git"},
    {"name": "anything-llm", "url": "https://github.com/mintplex-labs/anything-llm.git"},
    {"name": "ragflow", "url": "https://github.com/infiniflow/ragflow.git"},
    {"name": "lightrag", "url": "https://github.com/hkuds/lightrag.git"},
]

# ======================== STATE MANAGER ========================
class StateManager:
    def __init__(self):
        self.state = {"items": {}, "retry_count": 0, "max_retries": 3}
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f: self.state = json.load(f)
            except json.JSONDecodeError: 
                self.state = {"items": {}, "retry_count": 0, "max_retries": 3}
        self.retry_queue = []
        if RETRY_QUEUE.exists():
            try:
                with open(RETRY_QUEUE, "r") as f: self.retry_queue = json.load(f)
            except json.JSONDecodeError:
                self.retry_queue = []

    def save(self):
        with open(STATE_FILE, "w") as f: json.dump(self.state, f, indent=2)
        with open(RETRY_QUEUE, "w") as f: json.dump(self.retry_queue, f, indent=2)

    def set_item(self, key, status, category, details=""):
        self.state["items"][key] = {
            "status": status, "category": category, 
            "details": str(details), "updated": datetime.now().isoformat(),
            "retries": self.state["items"].get(key, {}).get("retries", 0)
        }
        if status == "failed":
            self.state["items"][key]["retries"] += 1
            if self.state["items"][key]["retries"] <= self.state.get("max_retries", 3):
                if key not in self.retry_queue:
                    self.retry_queue.append(key)
            logger.failed_task(key, details, self.state["items"][key]["retries"])
        elif status == "completed":
            if key in self.retry_queue:
                self.retry_queue.remove(key)
            logger.info(f"Task completed: {key}")
        self.save()

    def is_completed(self, key):
        return self.state["items"].get(key, {}).get("status") == "completed"
    
    def get_failed_items(self):
        return {k: v for k, v in self.state["items"].items() if v.get("status") == "failed"}
    
    def get_retry_queue(self):
        retry_items = []
        for key in self.retry_queue:
            if key in self.state["items"]:
                retry_count = self.state["items"][key].get("retries", 0)
                max_retries = self.state.get("max_retries", 3)
                if retry_count <= max_retries:
                    retry_items.append(key)
        return retry_items

state = StateManager()
metrics = {"completed": 0, "failed": 0, "total": 0}

# ======================== CORE LOGIC ========================
def run_cmd(cmd, max_retries=3, timeout=600, cwd=None, env=None):
    """Run command with proxy support"""
    logger.debug(f"Running command: {' '.join(cmd)}")
    
    for attempt in range(1, max_retries + 1):
        try:
            run_env = os.environ.copy()
            if env:
                run_env.update(env)
            
            run_env['HTTP_PROXY'] = PROXY_URL
            run_env['HTTPS_PROXY'] = PROXY_URL
            run_env['http_proxy'] = PROXY_URL
            run_env['https_proxy'] = PROXY_URL
            run_env['PATH'] = f"{DIRS['bin']}:{run_env.get('PATH', '')}"
            
            logger.debug(f"Attempt {attempt}/{max_retries}")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=run_env)
            
            if proc.returncode == 0:
                logger.info(f"Command succeeded: {' '.join(cmd[:2])}")
                return True, proc.stdout
            else:
                error_msg = proc.stderr.strip()[:1000]
                logger.warning(f"Attempt {attempt} failed (exit code {proc.returncode}): {error_msg}")
                logger.debug(f"Full stderr: {proc.stderr}")
                
                if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.warning("Network error detected - retrying with longer timeout")
                    timeout = timeout * 1.5
                    
        except subprocess.TimeoutExpired as e:
            logger.warning(f"Timeout on attempt {attempt}")
            logger.debug(f"Timeout details: {str(e)}")
        except Exception as e:
            logger.error(f"Fatal error on attempt {attempt}: {str(e)}", traceback.format_exc())
            
        if attempt < max_retries:
            wait_time = 5 * attempt
            logger.info(f"Retrying in {wait_time}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(wait_time)
    
    logger.error(f"Command failed after {max_retries} attempts: {' '.join(cmd)}")
    return False, "Max retries exceeded"

def pull_docker(image):
    logger.info(f"Pulling Docker image: {image}")
    success, err = run_cmd(["docker", "pull", image], max_retries=3, timeout=1200)
    if not success: 
        return False, err
    
    tar_path = DIRS["docker"] / f"{image.replace('/', '_').replace(':', '_')}.tar"
    logger.info(f"Saving Docker image to: {tar_path}")
    return run_cmd(["docker", "save", "-o", str(tar_path), image], max_retries=2, timeout=600)

def download_pip(pkg, cu124=False):
    logger.info(f"Downloading package: {pkg} (CUDA: {cu124})")
    dest = DIRS["python_cu124"] if cu124 else DIRS["python"]
    
    # Get venv python/pip
    venv_path = BASE_DIR / "venv"
    pip_cmd = str(venv_path / "bin" / "pip")
    
    if cu124:
        cmd = [pip_cmd, "download", pkg, "-d", str(dest), 
               "--index-url", "https://download.pytorch.org/whl/cu124",
               "--extra-index-url", "https://pypi.org/simple",
               "--proxy", PROXY_URL]
    else:
        cmd = [pip_cmd, "download", pkg, "-d", str(dest), 
               "--no-deps", "--proxy", PROXY_URL]
    
    success, err = run_cmd(cmd, max_retries=3, timeout=600)
    if success:
        return True, "pip download success"
    return False, err

def download_hf_model(repo_id):
    logger.info(f"Downloading HuggingFace model: {repo_id}")
    dest_path = DIRS["models_hf"] / repo_id.replace("/", "_")
    
    venv_path = BASE_DIR / "venv"
    cmd = [
        str(venv_path / "bin" / "huggingface-cli"), "download", 
        repo_id, 
        "--local-dir", str(dest_path),
        "--local-dir-use-symlinks", "False",
        "--resume-download",
        "--proxy", PROXY_URL
    ]
    
    env = os.environ.copy()
    if 'HF_TOKEN' in os.environ:
        env['HF_TOKEN'] = os.environ['HF_TOKEN']
        logger.info("Using HF_TOKEN from environment")
    
    env['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
    
    success, err = run_cmd(cmd, max_retries=3, timeout=7200, env=env)
    if success:
        return True, "Model downloaded successfully"
    
    # Try Python API fallback
    logger.info("Trying Python API fallback...")
    try:
        sys.path.insert(0, str(venv_path / "lib" / "python3.12" / "site-packages"))
        from huggingface_hub import snapshot_download
        
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(dest_path),
            local_dir_use_symlinks=False,
            resume_download=True,
            token=os.environ.get('HF_TOKEN', None),
            proxies={"http": PROXY_URL, "https": PROXY_URL}
        )
        return True, "Model downloaded via Python API"
    except Exception as e:
        logger.error(f"Python API fallback failed: {str(e)}", traceback.format_exc())
        return False, f"All download methods failed: {err}"

def setup_project(project):
    name, url = project["name"], project["url"]
    logger.info(f"Setting up project: {name}")
    dest = PROJECTS_DIR / name
    
    if not dest.exists():
        logger.info(f"Cloning project: {name}")
        succ, err = run_cmd(["git", "clone", url, str(dest)], timeout=300)
        if not succ: 
            return False, f"Clone failed: {err}"
    
    req_file = dest / "requirements.txt"
    if req_file.exists():
        logger.info(f"Installing requirements for {name}")
        venv_path = BASE_DIR / "venv"
        pip_cmd = str(venv_path / "bin" / "pip")
        
        succ, err = run_cmd([pip_cmd, "install", "-r", str(req_file), "--proxy", PROXY_URL], 
                           cwd=str(dest), timeout=600)
        if not succ: 
            return False, f"Install failed: {err}"
        return True, "Cloned and installed dependencies"
    
    return True, "Cloned successfully"

def generate_report(import_results=None):
    with open(REPORT_FILE, "w") as f:
        f.write("# H200 Offline Preparation Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"CUDA Version Detected: {CUDA_VERSION}\n")
        f.write(f"Driver Version: {DRIVER_VERSION}\n")
        f.write(f"PyTorch Version: {TORCH_VERSION}+{TORCH_CUDA}\n\n")
        
        total = len(state.state["items"])
        completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
        failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
        
        f.write(f"- Completed: {completed}\n")
        f.write(f"- Failed: {failed}\n")
        f.write(f"- In Retry Queue: {len(state.get_retry_queue())}\n\n")
        
        f.write("### Error Traces:\n")
        for key, data in state.state["items"].items():
            if data["status"] == "failed":
                retries = data.get("retries", 0)
                f.write(f"- {key} (retries: {retries}): {data['details'][:500]}\n")
        
        # Include import report if available
        if import_results:
            f.write("\n### Import Verification Results:\n")
            for pkg, result in import_results.items():
                if result['status'] == 'OK':
                    f.write(f"- PASS: {pkg} (version: {result['version']})\n")
                else:
                    f.write(f"- FAIL: {pkg} - {result['error'][:100]}\n")
        
        f.write("\n### H200 CUDA 13 Optimization Recommendations:\n")
        f.write("1. Your system has CUDA 13 with driver {DRIVER_VERSION}\n")
        f.write("2. Using PyTorch with CUDA 12.4 compatibility (cu124)\n")
        f.write("3. For best performance, use FP8 quantization with vLLM\n")
        f.write("4. Enable flash-attention-2 for faster inference\n")
        f.write("5. Check error logs for failed tasks:\n")
        f.write(f"   - Main log: {LOG_FILE}\n")
        f.write(f"   - Error log: {ERROR_LOG}\n")
        f.write(f"   - Failed tasks: {FAILED_TASKS_LOG}\n")

# ======================== MAIN ORCHESTRATOR ========================
@click.command()
@click.option('--interactive', is_flag=True, help='Interactive selection of components')
@click.option('--auto-retry', is_flag=True, help='Automatically retry failed tasks')
@click.option('--skip-checks', is_flag=True, help='Skip pre-installation checks')
def main(interactive, auto_retry, skip_checks):
    """H200 CUDA Offline Preparation Tool"""
    
    print("="*80)
    print(" H200 CUDA Offline Preparation Tool")
    print(f" Python: {sys.version.split()[0]}")
    print("="*80)
    
    # Step 1: Pre-installation checks
    if not skip_checks:
        pre_check_results = run_pre_installation_checks()
        
        if not pre_check_results['connectivity']:
            print("\nWARNING: Network connectivity issues detected.")
            print(f"Please check your proxy: {PROXY_URL}")
            if not click.confirm("Continue anyway?", default=False):
                return
        
        if not pre_check_results.get('venv'):
            print("\nERROR: Virtual environment creation failed.")
            return
    
    # Step 2: Verify imports (if venv exists)
    venv_path = BASE_DIR / "venv"
    import_results = None
    
    if venv_path.exists():
        print("\n" + "="*80)
        print(" VERIFYING PACKAGE IMPORTS")
        print("="*80)
        import_results = verify_imports()
        
        # Check if critical packages are missing
        critical_failures = [
            pkg for pkg, result in import_results.items() 
            if result['status'] == 'FAIL' and pkg in ['torch', 'transformers']
        ]
        if critical_failures:
            print(f"\nWARNING: Critical packages missing: {', '.join(critical_failures)}")
            if not click.confirm("Continue anyway?", default=False):
                return
    
    # Step 3: Interactive configuration
    if interactive:
        print("\n" + "="*80)
        print(" INTERACTIVE CONFIGURATION")
        print("="*80)
        
        print(f"\nCUDA Version: {CUDA_VERSION}")
        print(f"Driver: {DRIVER_VERSION}")
        print(f"PyTorch: {TORCH_VERSION}+{TORCH_CUDA}")
        
        total = len(state.state["items"])
        completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
        failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
        
        print(f"\nCurrent progress: {completed}/{total} completed, {failed} failed")
        
        if total > 0:
            if not click.confirm("Continue previous installation session?", default=True):
                state.state = {"items": {}, "retry_count": 0, "max_retries": 3}
                state.retry_queue = []
                state.save()
                print("State reset")
        
        max_retries = click.prompt(
            "Max retry attempts for failed downloads",
            default=state.state.get("max_retries", 3),
            type=int
        )
        state.state["max_retries"] = max_retries
        state.save()
    
    # Step 4: Setup progress tracking
    progress_ui = None  # Remove Rich dependency
    
    # Get all tasks
    all_tasks = []
    for img, _ in DOCKER_IMAGES:
        all_tasks.append(("docker", f"docker_{img}", img))
    
    for pkg in PYTHON_PACKAGES:
        is_cuda = any(x in pkg.lower() for x in ['cu124', 'cuda', 'gpu', 'cupy', 'faiss-gpu'])
        all_tasks.append(("pip", f"pip_{pkg}", pkg, is_cuda))
    
    for pkg in CUDA_EXTRA_PACKAGES:
        all_tasks.append(("pip_cuda", f"pip_cuda_{pkg}", pkg, True))
    
    for repo in MODELS.keys():
        all_tasks.append(("model", f"model_{repo}", repo))
    
    for proj in SAMPLE_PROJECTS:
        all_tasks.append(("project", f"project_{proj['name']}", proj))
    
    # Filter tasks
    pending_tasks = []
    for task_tuple in all_tasks:
        key = task_tuple[1]
        if not state.is_completed(key):
            pending_tasks.append(task_tuple)
    
    retry_items = state.get_retry_queue()
    for key in retry_items:
        for task_tuple in all_tasks:
            if task_tuple[1] == key and task_tuple not in pending_tasks:
                pending_tasks.append(task_tuple)
                break
    
    metrics["total"] = len(pending_tasks)
    
    if metrics["total"] == 0:
        print("\nAll tasks completed successfully!")
        return
    
    print(f"\nTotal tasks to process: {metrics['total']}")
    if auto_retry:
        print("Auto-retry mode: ENABLED")
    
    # Execute tasks
    def execute_task(key, category, func, *args, **kwargs):
        if state.is_completed(key):
            return
            
        try:
            print(f"\n[PROCESSING] {key}")
            success, details = func(*args, **kwargs)
            if success:
                state.set_item(key, "completed", category, details)
                metrics["completed"] += 1
                print(f"[COMPLETED] {key}")
            else:
                state.set_item(key, "failed", category, details)
                metrics["failed"] += 1
                print(f"[FAILED] {key}")
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Crash on {key}: {error_msg}")
            state.set_item(key, "failed", category, f"Crash: {str(e)}")
            metrics["failed"] += 1
            print(f"[ERROR] {key}: {str(e)[:50]}")
    
    try:
        while pending_tasks:
            task_tuple = pending_tasks.pop(0)
            task_type = task_tuple[0]
            key = task_tuple[1]
            
            if state.is_completed(key):
                continue
            
            if task_type == "docker":
                img = task_tuple[2]
                execute_task(key, "Docker", pull_docker, img)
                
            elif task_type in ["pip", "pip_cuda"]:
                is_cuda = task_tuple[3] if len(task_tuple) > 3 else False
                pkg = task_tuple[2]
                execute_task(key, "Python_CUDA" if is_cuda else "Python_Libs", 
                           download_pip, pkg, is_cuda)
                
            elif task_type == "model":
                repo = task_tuple[2]
                execute_task(key, "Models", download_hf_model, repo)
                
            elif task_type == "project":
                proj = task_tuple[2]
                execute_task(key, "Sample_Projects", setup_project, proj)
            
            if auto_retry and state.get_retry_queue():
                for retry_key in state.get_retry_queue():
                    for task in all_tasks:
                        if task[1] == retry_key and task not in pending_tasks:
                            pending_tasks.append(task)
                            break
        
        print("\n" + "="*80)
        print(" ALL PHASES COMPLETED")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\n\nInstallation interrupted by user")
        print("State saved. Resume with: python3 setup.py --interactive")
        logger.info("Installation interrupted by user")
    
    # Final verification
    print("\n" + "="*80)
    print(" FINAL IMPORT VERIFICATION")
    print("="*80)
    import_results = verify_imports()
    
    # Generate final report
    generate_report(import_results)
    
    # Print summary
    print("\n" + "="*80)
    print(" FINAL SUMMARY")
    print("="*80)
    
    total = len(state.state["items"])
    completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
    failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
    
    print(f"Total tasks attempted: {total}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print(f"\nFailed tasks logged in:")
        print(f"  - {ERROR_LOG}")
        print(f"  - {FAILED_TASKS_LOG}")
        print(f"  - {BASE_DIR}/failed_tasks.json")
        print(f"\nTo retry failed tasks:")
        print(f"  python3 setup.py --interactive --auto-retry")
    
    print(f"\nReport generated: {REPORT_FILE}")
    print(f"Import report: {IMPORT_REPORT}")
    print(f"Logs: {LOG_FILE}")
    
    # Show import status
    if import_results:
        print("\nImport Status:")
        ok = sum(1 for v in import_results.values() if v['status'] == 'OK')
        fail = sum(1 for v in import_results.values() if v['status'] == 'FAIL')
        print(f"  [OK] {ok} packages")
        print(f"  [FAIL] {fail} packages")
        
        if fail > 0:
            print("\nFailed imports:")
            for pkg, result in import_results.items():
                if result['status'] == 'FAIL':
                    print(f"  - {pkg}: {result['error'][:80]}")

if __name__ == "__main__":
    main()
