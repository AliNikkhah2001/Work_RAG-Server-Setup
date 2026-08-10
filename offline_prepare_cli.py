#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import logging
import threading
import random
from pathlib import Path
from datetime import datetime
import click

# Rich UI Imports
from rich.live import Live
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn, 
    TimeElapsedColumn, TimeRemainingColumn
)
from rich.table import Table
from rich.panel import Panel
from rich.console import Group, Console
from rich import box
from rich.align import Align
from rich.prompt import Confirm, IntPrompt

# ======================== CONFIGURATION ========================
BASE_DIR = Path("./offline-prep")
STATE_FILE = BASE_DIR / ".state.json"
PROJECTS_DIR = BASE_DIR / "sample-projects"
REPORT_FILE = BASE_DIR / "COMPREHENSIVE_REPORT.md"
RETRY_QUEUE = BASE_DIR / ".retry_queue.json"
LOG_FILE = BASE_DIR / "download.log"

# Proxy configuration (UPDATE WITH YOUR PROXY)
PROXY_URL = "http://192.168.203.2:3128"
PROXY_SETTINGS = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

DIRS = {
    "docker": BASE_DIR / "docker-images",
    "python": BASE_DIR / "python-packages",
    "python_cu124": BASE_DIR / "python-packages-cu124",
    "models_hf": BASE_DIR / "models" / "huggingface",
    "models_gguf": BASE_DIR / "models" / "gguf",
    "inference": BASE_DIR / "inference-engines"
}

for d in DIRS.values(): d.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE)]
)
logger = logging.getLogger(__name__)
console = Console()

# ======================== H200 OPTIMIZED ECOSYSTEM ========================

DOCKER_IMAGES = [
    ("ghcr.io/open-webui/open-webui:main", "Open WebUI"),
    ("vllm/vllm-openai:latest", "vLLM Inference Server"),
    ("nvidia/cuda:12.4.1-runtime-ubuntu22.04", "CUDA 12.4 Runtime"),
    ("pgvector/pgvector:pg16", "PostgreSQL+pgvector"),
    ("milvusdb/milvus:latest", "Milvus Vector DB"),
    ("qdrant/qdrant:latest", "Qdrant Vector DB"),
    ("redis:7-alpine", "Redis"),
]

PYTHON_PACKAGES = [
    # Core
    "fastapi", "pydantic", "uvicorn", "httpx", "aiohttp",
    # Document Processing  
    "docling", "unstructured", "pypdf", "pdfplumber", "markdown",
    # RAG Frameworks
    "langchain", "langgraph", "llama-index", "chromadb",
    # Vector DB Clients
    "pymilvus", "qdrant-client", "redis",
    # Evals & Monitoring
    "ragas", "deepeval", "litellm", "openai",
    # Utilities
    "sentence-transformers", "transformers", "accelerate",
    "bitsandbytes", "scipy", "numpy", "pandas"
]

# H200 OPTIMIZED CUDA PACKAGES
CUDA_PACKAGES = [
    "torch==2.3.0",
    "torchvision==0.18.0", 
    "xformers==0.0.26",
    "flash-attn==2.5.9",
    "vllm==0.5.0",
    "triton==2.3.0",
]

# H200 MODELS - Using GGUF format (no token needed for most)
MODELS = {
    # GGUF Models (Open access, no token needed)
    "TheBloke/Llama-3.2-3B-Instruct-GGUF": "Llama 3.2 3B (Q4_K_M)",
    "TheBloke/Mistral-7B-Instruct-v0.3-GGUF": "Mistral 7B (Q4_K_M)",
    "TheBloke/Qwen2.5-7B-Instruct-GGUF": "Qwen 7B (Q4_K_M)",
    "TheBloke/Phi-3-mini-4k-instruct-GGUF": "Phi-3 Mini (Q4_K_M)",
    # Embedding Models
    "BAAI/bge-small-en-v1.5": "BGE Small Embeddings",
    "sentence-transformers/all-MiniLM-L6-v2": "MiniLM Embeddings",
}

# Inference Engines for H200
INFERENCE_ENGINES = [
    {
        "name": "vLLM",
        "repo": "vllm-project/vllm",
        "cmd": "pip install vllm --index-url https://download.pytorch.org/whl/cu124"
    },
    {
        "name": "llama.cpp",
        "repo": "ggerganov/llama.cpp",
        "cmd": "make LLAMA_CUDA=1 -j"
    },
    {
        "name": "ExLlamaV2",
        "repo": "turboderp/exllamav2",
        "cmd": "pip install exllamav2"
    }
]

SAMPLE_PROJECTS = [
    {"name": "dify", "url": "https://github.com/langgenius/dify.git"},
    {"name": "anything-llm", "url": "https://github.com/mintplex-labs/anything-llm.git"},
    {"name": "ragflow", "url": "https://github.com/infiniflow/ragflow.git"},
    {"name": "lightrag", "url": "https://github.com/hkuds/lightrag.git"},
]

# ======================== MATRIX STYLE ASCII ART ========================
class MatrixASCII:
    def __init__(self):
        self.running = False
        self.thread = None
        self.current_art = ""
        self.lock = threading.Lock()
        self.width = 40
        self.height = 5
        
        self.chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                     'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                     'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
                     'U', 'V', 'W', 'X', 'Y', 'Z']
        
        self.colors = {
            'green': '\033[92m',
            'dark_green': '\033[32m',
            'bright_green': '\033[96m',
            'bold': '\033[1m',
            'dim': '\033[2m',
            'end': '\033[0m'
        }
        
        self.columns = []
        self.init_columns()
        self.log_lines = []
        self.log_lock = threading.Lock()
        
    def init_columns(self):
        self.columns = []
        for i in range(self.width):
            self.columns.append({
                'x': i,
                'y': random.randint(0, self.height),
                'speed': random.randint(1, 3),
                'length': random.randint(2, 5),
                'char': random.choice(self.chars)
            })
    
    def generate_art(self):
        matrix = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        
        for col in self.columns:
            col['y'] = (col['y'] + col['speed']) % (self.height + col['length'])
            
            for i in range(col['length']):
                y_pos = (col['y'] - i) % self.height
                if 0 <= y_pos < self.height:
                    if i == 0:
                        matrix[y_pos][col['x']] = f"{self.colors['bright_green']}{random.choice(self.chars)}{self.colors['end']}"
                    elif i < col['length'] // 2:
                        matrix[y_pos][col['x']] = f"{self.colors['green']}{random.choice(self.chars)}{self.colors['end']}"
                    else:
                        matrix[y_pos][col['x']] = f"{self.colors['dim']}{self.colors['dark_green']}{random.choice(self.chars)}{self.colors['end']}"
            
            if random.random() < 0.3:
                col['char'] = random.choice(self.chars)
        
        art_lines = []
        for row in matrix:
            line = ''.join(row)
            art_lines.append(line)
        
        art = f"{self.colors['green']}╔{'═' * (self.width + 2)}╗{self.colors['end']}\n"
        for line in art_lines:
            art += f"{self.colors['green']}║{self.colors['end']}{line}{self.colors['green']}║{self.colors['end']}\n"
        art += f"{self.colors['green']}╚{'═' * (self.width + 2)}╝{self.colors['end']}"
        
        return art
    
    def _run(self):
        while self.running:
            with self.lock:
                self.current_art = self.generate_art()
                with self.log_lock:
                    self.update_log_tail()
            time.sleep(random.uniform(0.05, 0.15))
    
    def update_log_tail(self):
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
                self.log_lines = lines[-10:] if lines else ["[INFO] No logs yet..."]
        except Exception:
            self.log_lines = ["[INFO] Waiting for logs..."]
    
    def get_log_tail(self):
        with self.log_lock:
            if not self.log_lines:
                return "[INFO] No logs yet..."
            formatted = []
            for line in self.log_lines[-5:]:
                line = line.strip()
                if not line:
                    continue
                if '[ERROR]' in line:
                    formatted.append(f"[bold red]{line}[/bold red]")
                elif '[WARNING]' in line:
                    formatted.append(f"[bold yellow]{line}[/bold yellow]")
                elif '[INFO]' in line:
                    formatted.append(f"[cyan]{line}[/cyan]")
                else:
                    formatted.append(f"[white]{line}[/white]")
            return '\n'.join(formatted)
    
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def get_art(self):
        with self.lock:
            return self.current_art

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
        elif status == "completed":
            if key in self.retry_queue:
                self.retry_queue.remove(key)
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

# ======================== INTERACTIVE SELECTION ========================
def interactive_selection():
    console.print("\n[bold cyan]🔧 INTERACTIVE CONFIGURATION[/bold cyan]\n")
    
    total = len(state.state["items"])
    completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
    failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
    
    console.print(f"[yellow]Current progress: {completed}/{total} completed, {failed} failed[/yellow]\n")
    
    if total > 0:
        if not Confirm.ask("[cyan]Continue previous installation session?[/cyan]", default=True):
            state.state = {"items": {}, "retry_count": 0, "max_retries": 3}
            state.retry_queue = []
            state.save()
            console.print("[green]State reset[/green]")
    
    max_retries = IntPrompt.ask(
        "[cyan]Max retry attempts for failed downloads[/cyan]",
        default=state.state.get("max_retries", 3),
        show_default=True
    )
    state.state["max_retries"] = max_retries
    state.save()
    
    # Check if tools are installed
    check_required_tools()
    
    return {'max_retries': max_retries}

def check_required_tools():
    """Check and install required tools"""
    console.print("\n[bold cyan]🔧 Checking required tools...[/bold cyan]")
    
    # Check pip
    try:
        subprocess.run(["pip", "--version"], capture_output=True, check=True)
        console.print("[green]✓ pip found[/green]")
    except:
        console.print("[red]✗ pip not found. Please install pip[/red]")
    
    # Check huggingface-cli
    try:
        subprocess.run(["huggingface-cli", "--version"], capture_output=True, check=True)
        console.print("[green]✓ huggingface-cli found[/green]")
    except:
        console.print("[yellow]⚠️ huggingface-cli not found. Installing...[/yellow]")
        subprocess.run(["pip", "install", "huggingface-hub"], check=True)
        console.print("[green]✓ huggingface-cli installed[/green]")
    
    # Check docker
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        console.print("[green]✓ docker found[/green]")
    except:
        console.print("[red]✗ docker not found. Please install docker[/red]")
    
    # Check git
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        console.print("[green]✓ git found[/green]")
    except:
        console.print("[red]✗ git not found. Please install git[/red]")

# ======================== UI LAYOUT ========================
def generate_layout(progress_ui, matrix_art=None, current_task="", phase_name="", retry_count=0, log_tail=""):
    table = Table(title="📊 Live Installation Summary", box=box.ROUNDED, expand=True)
    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Count", style="magenta", justify="right")
    
    total_items = len(state.state["items"])
    completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
    failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
    
    table.add_row("Tasks Attempted", str(total_items))
    table.add_row("✅ Successfully Completed", f"[bold green]{completed}[/bold green]")
    table.add_row("❌ Failed", f"[bold red]{failed}[/bold red]")
    table.add_row("🔄 Retry Queue", f"[bold yellow]{len(state.get_retry_queue())}[/bold yellow]")
    
    if phase_name:
        table.add_row("Current Phase", f"[bold yellow]{phase_name}[/bold yellow]")
    
    failed_items = state.get_failed_items()
    if failed_items:
        fail_text = "\n".join([f"  • {key[:35]} (retries: {v.get('retries', 0)})" 
                               for key, v in list(failed_items.items())[:3]])
        if len(failed_items) > 3:
            fail_text += f"\n  • ... and {len(failed_items) - 3} more"
        fail_panel = Panel(fail_text, title="⚠️ Failed Items", border_style="red", box=box.ROUNDED)
    else:
        fail_panel = Panel("[green]✓ No failures[/green]", title="✅ Status", border_style="green", box=box.ROUNDED)
    
    task_panel = Panel(
        f"[bold yellow]{current_task or 'Waiting...'}[/bold yellow]",
        title="Current Task",
        border_style="yellow",
        box=box.ROUNDED
    )
    
    art_panel = Panel(
        Align.center(matrix_art or "[dim]Initializing Matrix...[/dim]"),
        title="🖥️ H200 Matrix Downloader",
        border_style="green",
        box=box.HEAVY,
        height=9
    )
    
    log_panel = Panel(
        log_tail or "[dim]Waiting for logs...[/dim]",
        title="📋 Live Log Tail",
        border_style="blue",
        box=box.ROUNDED,
        height=6
    )
    
    top_row = Group(table, fail_panel)
    middle_row = Group(task_panel, art_panel)
    bottom_row = log_panel
    progress_row = progress_ui
    
    return Group(top_row, middle_row, bottom_row, progress_row)

# ======================== CORE LOGIC ========================
def run_cmd(cmd, max_retries=3, timeout=600, cwd=None, env=None):
    """Run command with proxy support"""
    for attempt in range(1, max_retries + 1):
        try:
            run_env = os.environ.copy()
            if env:
                run_env.update(env)
            
            # Add proxy
            run_env['HTTP_PROXY'] = PROXY_URL
            run_env['HTTPS_PROXY'] = PROXY_URL
            run_env['http_proxy'] = PROXY_URL
            run_env['https_proxy'] = PROXY_URL
            
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=run_env)
            if proc.returncode == 0: 
                logger.info(f"Command succeeded: {' '.join(cmd[:2])}")
                return True, proc.stdout
            logger.warning(f"Attempt {attempt} failed: {proc.stderr.strip()[:200]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout on attempt {attempt}")
        except Exception as e:
            logger.warning(f"Fatal error on attempt {attempt}: {str(e)}")
        if attempt < max_retries: 
            time.sleep(5 * attempt)
            logger.info(f"Retrying... (attempt {attempt+1}/{max_retries})")
    return False, "Max retries exceeded"

def pull_docker(image):
    logger.info(f"Pulling Docker image: {image}")
    success, err = run_cmd(["docker", "pull", image], max_retries=3, timeout=1200)
    if not success: return False, err
    tar_path = DIRS["docker"] / f"{image.replace('/', '_').replace(':', '_')}.tar"
    logger.info(f"Saving Docker image to: {tar_path}")
    return run_cmd(["docker", "save", "-o", str(tar_path), image], max_retries=2, timeout=600)

def download_pip(pkg, cu124=False):
    logger.info(f"Downloading Python package: {pkg} (CUDA: {cu124})")
    dest = DIRS["python_cu124"] if cu124 else DIRS["python"]
    
    cmd = ["pip", "download", pkg, "-d", str(dest), "--no-deps"]
    if cu124:
        cmd.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    
    success, err = run_cmd(cmd, max_retries=3, timeout=600)
    if success:
        return True, "pip download success"
    return False, err

def download_hf_model(repo_id):
    """Download HuggingFace model with or without token"""
    logger.info(f"Downloading HuggingFace model: {repo_id}")
    dest_path = DIRS["models_hf"] / repo_id.replace("/", "_")
    
    # Check if it's a gated model
    is_gated = "meta-llama" in repo_id or "gated" in repo_id.lower()
    
    if is_gated:
        logger.warning(f"⚠️ {repo_id} is a gated model. You need to:")
        logger.warning("1. Accept terms at: https://huggingface.co/{repo_id}")
        logger.warning("2. Set HF_TOKEN environment variable")
        logger.warning("Trying with anonymous access anyway...")
    
    # Try with huggingface-cli
    cmd = [
        "huggingface-cli", "download", 
        repo_id, 
        "--local-dir", str(dest_path),
        "--local-dir-use-symlinks", "False",
        "--resume-download"
    ]
    
    # Use token if available
    env = os.environ.copy()
    if 'HF_TOKEN' in os.environ:
        env['HF_TOKEN'] = os.environ['HF_TOKEN']
        logger.info("Using HF_TOKEN from environment")
    
    env['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
    
    success, err = run_cmd(cmd, max_retries=3, timeout=7200, env=env)
    if success:
        return True, "Model downloaded successfully"
    
    # If huggingface-cli fails, try with Python API (more reliable)
    logger.info("Trying Python API fallback...")
    try:
        from huggingface_hub import snapshot_download
        import os as os_module
        
        # Set proxy for Python
        os_module.environ['HTTP_PROXY'] = PROXY_URL
        os_module.environ['HTTPS_PROXY'] = PROXY_URL
        
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
        logger.error(f"Python API fallback failed: {str(e)}")
        return False, f"All download methods failed: {err}"

def setup_project(project):
    name, url = project["name"], project["url"]
    logger.info(f"Setting up project: {name}")
    dest = PROJECTS_DIR / name
    
    if not dest.exists():
        succ, err = run_cmd(["git", "clone", url, str(dest)], timeout=300)
        if not succ: return False, f"Clone failed: {err}"
    
    req_file = dest / "requirements.txt"
    if req_file.exists():
        succ, err = run_cmd(["pip", "install", "-r", str(req_file)], cwd=str(dest), timeout=600)
        if not succ: return False, f"Install failed: {err}"
        return True, "Cloned and installed dependencies"
    
    return True, "Cloned successfully"

def generate_report():
    with open(REPORT_FILE, "w") as f:
        f.write("# 🚀 H200 Offline Preparation Report\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        total = len(state.state["items"])
        completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
        failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
        
        f.write(f"- **✅ Completed:** {completed}\n")
        f.write(f"- **❌ Failed:** {failed}\n")
        f.write(f"- **🔄 In Retry Queue:** {len(state.get_retry_queue())}\n\n")
        
        f.write("### Error Traces:\n")
        for key, data in state.state["items"].items():
            if data["status"] == "failed":
                retries = data.get("retries", 0)
                f.write(f"- **{key}** (retries: {retries}): {data['details'][:200]}\n")
        
        f.write("\n### H200 Optimization Recommendations:\n")
        f.write("1. Use vLLM with FP8 quantization for best performance\n")
        f.write("2. Use GGUF models (Q4_K_M) for memory-efficient inference\n")
        f.write("3. Enable flash-attention-2 for faster inference\n")
        f.write("4. Use batch inference for higher throughput\n")
        f.write("5. Consider using TensorRT-LLM for production deployment\n")

# ======================== MAIN ORCHESTRATOR ========================
@click.command()
@click.option('--interactive', is_flag=True, help='Interactive selection of components')
@click.option('--skip-matrix', is_flag=True, help='Skip Matrix ASCII animation')
@click.option('--auto-retry', is_flag=True, help='Automatically retry failed tasks')
def main(interactive, skip_matrix, auto_retry):
    console.print("[bold cyan]🚀 H200 Offline Preparation Tool[/bold cyan]")
    console.print("[yellow]Optimized for NVIDIA H200 GPUs[/yellow]")
    console.print("[dim]Using proxy: {}[/dim]\n".format(PROXY_URL))
    
    if interactive:
        config = interactive_selection()
        max_retries = config.get('max_retries', 3)
        state.state["max_retries"] = max_retries
        state.save()
    else:
        max_retries = state.state.get("max_retries", 3)
    
    # Check for HuggingFace token
    if 'HF_TOKEN' in os.environ:
        console.print("[green]✓ HF_TOKEN found in environment[/green]")
    else:
        console.print("[yellow]⚠️ No HF_TOKEN found. Public models only.[/yellow]")
        console.print("[dim]For gated models (like Llama 3.1), set: export HF_TOKEN=your_token[/dim]")
    
    # Start Matrix thread
    matrix = MatrixASCII()
    if not skip_matrix:
        matrix.start()
    
    # Setup progress UI
    progress_ui = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
    
    # Get all tasks
    all_tasks = []
    for img, _ in DOCKER_IMAGES:
        all_tasks.append(("docker", f"docker_{img}", img))
    for pkg in PYTHON_PACKAGES:
        all_tasks.append(("pip", f"pip_{pkg}", pkg, False))
    for pkg in CUDA_PACKAGES:
        all_tasks.append(("pip_cuda", f"pip_cu124_{pkg}", pkg, True))
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
        console.print("[green]All tasks completed successfully! 🎉[/green]")
        return
    
    overall_task = progress_ui.add_task("[bold cyan]Total Progress", total=metrics["total"], completed=0)
    phase_task = progress_ui.add_task("[bold magenta]Current Phase", total=0)
    current_item_task = progress_ui.add_task("[bold yellow]Waiting to start...", total=None)
    
    def execute_with_ui(key, category, func, *args, **kwargs):
        if state.is_completed(key):
            progress_ui.advance(overall_task)
            progress_ui.advance(phase_task)
            return
            
        progress_ui.update(current_item_task, description=f"[bold yellow]{key}")
        
        try:
            success, details = func(*args, **kwargs)
            if success:
                state.set_item(key, "completed", category, details)
                metrics["completed"] += 1
            else:
                state.set_item(key, "failed", category, details)
                metrics["failed"] += 1
        except Exception as e:
            logger.error(f"Crash on {key}: {str(e)}")
            state.set_item(key, "failed", category, f"Crash: {str(e)}")
            metrics["failed"] += 1
            
        progress_ui.advance(overall_task)
        progress_ui.advance(phase_task)
    
    try:
        with Live(generate_layout(progress_ui, 
                                 matrix.get_art() if not skip_matrix else None,
                                 "Waiting to start...",
                                 "Initializing",
                                 len(state.get_retry_queue()),
                                 matrix.get_log_tail() if not skip_matrix else ""),
                  refresh_per_second=10, 
                  screen=True) as live:
            
            while pending_tasks:
                task_tuple = pending_tasks.pop(0)
                task_type = task_tuple[0]
                key = task_tuple[1]
                
                if state.is_completed(key):
                    progress_ui.advance(overall_task)
                    continue
                
                if task_type == "docker":
                    phase_name = "Docker Images"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]=='docker']), completed=0)
                    img = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               matrix.get_art() if not skip_matrix else None,
                                               f"docker: {img[:30]}",
                                               phase_name,
                                               len(state.get_retry_queue()),
                                               matrix.get_log_tail() if not skip_matrix else ""))
                    execute_with_ui(key, "Docker", pull_docker, img)
                    
                elif task_type in ["pip", "pip_cuda"]:
                    phase_name = "CUDA Packages" if task_type == "pip_cuda" else "Python Packages"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]==task_type]), completed=0)
                    pkg = task_tuple[2]
                    cu124 = task_tuple[3] if len(task_tuple) > 3 else False
                    live.update(generate_layout(progress_ui, 
                                               matrix.get_art() if not skip_matrix else None,
                                               f"{'cuda' if cu124 else 'pip'}: {pkg}",
                                               phase_name,
                                               len(state.get_retry_queue()),
                                               matrix.get_log_tail() if not skip_matrix else ""))
                    execute_with_ui(key, "Python_Libs" if not cu124 else "Python_Libs_CUDA", 
                                  download_pip, pkg, cu124)
                    
                elif task_type == "model":
                    phase_name = "HuggingFace Models"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]=='model']), completed=0)
                    repo = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               matrix.get_art() if not skip_matrix else None,
                                               f"model: {repo[:40]}",
                                               phase_name,
                                               len(state.get_retry_queue()),
                                               matrix.get_log_tail() if not skip_matrix else ""))
                    execute_with_ui(key, "Models", download_hf_model, repo)
                    
                elif task_type == "project":
                    phase_name = "GitHub Projects"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]=='project']), completed=0)
                    proj = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               matrix.get_art() if not skip_matrix else None,
                                               f"project: {proj['name']}",
                                               phase_name,
                                               len(state.get_retry_queue()),
                                               matrix.get_log_tail() if not skip_matrix else ""))
                    execute_with_ui(key, "Sample_Projects", setup_project, proj)
                
                if auto_retry and state.get_retry_queue():
                    for retry_key in state.get_retry_queue():
                        for task in all_tasks:
                            if task[1] == retry_key and task not in pending_tasks:
                                pending_tasks.append(task)
                                break
            
            live.update(generate_layout(progress_ui, 
                                       matrix.get_art() if not skip_matrix else None,
                                       "✅ All phases completed!",
                                       "Complete",
                                       len(state.get_retry_queue()),
                                       matrix.get_log_tail() if not skip_matrix else ""))
            time.sleep(2)
    
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️ Installation interrupted by user[/bold yellow]")
        console.print("[cyan]State saved. Resume with: python3 enhanced_installer.py --interactive[/cyan]")
        
    finally:
        if not skip_matrix:
            matrix.stop()
        
        generate_report()
        console.print(f"\n[bold green]📊 Report generated: {REPORT_FILE}[/bold green]")
        
        total = len(state.state["items"])
        completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
        failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
        
        console.print("\n[bold cyan]=== FINAL SUMMARY ===[/bold cyan]")
        console.print(f"Total tasks attempted: {total}")
        console.print(f"[green]✅ Completed: {completed}[/green]")
        console.print(f"[red]❌ Failed: {failed}[/red]")
        
        if failed > 0:
            console.print("\n[bold yellow]💡 To retry failed tasks:[/bold yellow]")
            console.print("  python3 enhanced_installer.py --interactive --auto-retry")
        
        console.print("\n[bold cyan]💡 H200 Optimization Tips:[/bold cyan]")
        console.print("1. Use vLLM with FP8 quantization for best performance")
        console.print("2. Use GGUF models (Q4_K_M) for memory-efficient inference")
        console.print("3. Enable flash-attention-2 for faster inference")
        console.print("4. Consider using TensorRT-LLM for production deployment")

if __name__ == "__main__":
    main()
