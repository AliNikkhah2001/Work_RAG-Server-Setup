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
import traceback
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
ERROR_LOG = BASE_DIR / "errors.log"
FAILED_TASKS_LOG = BASE_DIR / "failed_tasks.log"
DEBUG_LOG = BASE_DIR / "debug.log"

# Proxy configuration
PROXY_URL = "http://192.168.203.2:3128"

DIRS = {
    "docker": BASE_DIR / "docker-images",
    "python": BASE_DIR / "python-packages",
    "python_cu124": BASE_DIR / "python-packages-cu124",
    "models_hf": BASE_DIR / "models" / "huggingface",
    "models_gguf": BASE_DIR / "models" / "gguf",
    "inference": BASE_DIR / "inference-engines",
    "bin": BASE_DIR / "bin",
    "logs": BASE_DIR / "logs"  # New logs directory
}

for d in DIRS.values(): d.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Add bin to PATH
os.environ["PATH"] = f"{DIRS['bin']}:{os.environ.get('PATH', '')}"

# ======================== COMPREHENSIVE LOGGING SETUP ========================
class ComprehensiveLogger:
    """Handle all logging with multiple log files"""
    
    def __init__(self):
        self.base_dir = BASE_DIR
        self.setup_logging()
        
    def setup_logging(self):
        """Setup multiple log handlers"""
        
        # Main logger - INFO level
        main_logger = logging.getLogger('main')
        main_logger.setLevel(logging.INFO)
        main_handler = logging.FileHandler(LOG_FILE)
        main_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        main_logger.addHandler(main_handler)
        
        # Error logger - ERROR level only
        error_logger = logging.getLogger('error')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(ERROR_LOG)
        error_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s\n%(exc_info)s\n'))
        error_logger.addHandler(error_handler)
        
        # Debug logger - DEBUG level
        debug_logger = logging.getLogger('debug')
        debug_logger.setLevel(logging.DEBUG)
        debug_handler = logging.FileHandler(DEBUG_LOG)
        debug_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        debug_logger.addHandler(debug_handler)
        
        # Failed tasks logger
        failed_logger = logging.getLogger('failed')
        failed_logger.setLevel(logging.INFO)
        failed_handler = logging.FileHandler(FAILED_TASKS_LOG)
        failed_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        failed_logger.addHandler(failed_handler)
        
        self.main_logger = main_logger
        self.error_logger = error_logger
        self.debug_logger = debug_logger
        self.failed_logger = failed_logger
        
        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.main_logger.addHandler(console_handler)
    
    def log_info(self, msg):
        self.main_logger.info(msg)
        self.debug_logger.info(msg)
    
    def log_warning(self, msg):
        self.main_logger.warning(msg)
        self.debug_logger.warning(msg)
    
    def log_error(self, msg, exc_info=None):
        self.main_logger.error(msg)
        self.error_logger.error(msg, exc_info=exc_info)
        self.debug_logger.error(msg, exc_info=exc_info)
        self.failed_logger.error(msg)
        if exc_info:
            self.failed_logger.error(f"Traceback: {exc_info}")
    
    def log_debug(self, msg):
        self.debug_logger.debug(msg)
    
    def log_failed_task(self, task_name, error_msg, retries=0):
        """Log failed task with full details"""
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
        
        # Also append to a structured JSON log for easy parsing
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
            self.log_error(f"Failed to write failed_tasks.json: {e}")

logger = ComprehensiveLogger()
console = Console()

# ======================== TOOL CHECK AND INSTALL ========================
def install_uv():
    """Install uv package manager"""
    console.print("[bold cyan]📦 Installing uv package manager...[/bold cyan]")
    logger.log_info("Checking/Installing uv")
    
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, check=True)
        logger.log_info(f"uv already installed: {result.stdout.strip()}")
        console.print("[green]✓ uv already installed[/green]")
        return True
    except:
        pass
    
    try:
        logger.log_info("Installing uv via pip")
        console.print("[yellow]Installing uv via pip...[/yellow]")
        subprocess.run(
            ["pip", "install", "uv", "--target", str(DIRS["bin"]), "--upgrade"],
            check=True,
            env={**os.environ, "HTTP_PROXY": PROXY_URL, "HTTPS_PROXY": PROXY_URL}
        )
        
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, check=True)
            logger.log_info(f"uv installed successfully: {result.stdout.strip()}")
            console.print("[green]✓ uv installed successfully[/green]")
            return True
        except Exception as e:
            logger.log_error(f"uv installation verification failed: {e}", traceback.format_exc())
            console.print("[red]✗ uv installation failed[/red]")
            return False
            
    except Exception as e:
        logger.log_error(f"Failed to install uv: {e}", traceback.format_exc())
        console.print(f"[red]✗ Failed to install uv: {e}[/red]")
        return False

def check_required_tools():
    """Check and install required tools with detailed logging"""
    console.print("\n[bold cyan]🔧 Checking required tools...[/bold cyan]")
    logger.log_info("Checking required tools")
    
    tools_status = {}
    
    # Check uv
    tools_status['uv'] = install_uv()
    
    # Check pip
    try:
        result = subprocess.run(["pip", "--version"], capture_output=True, check=True)
        logger.log_info(f"pip found: {result.stdout.strip()}")
        console.print("[green]✓ pip found[/green]")
        tools_status['pip'] = True
    except Exception as e:
        logger.log_error("pip not found", traceback.format_exc())
        console.print("[red]✗ pip not found[/red]")
        tools_status['pip'] = False
    
    # Check huggingface-cli
    try:
        result = subprocess.run(["huggingface-cli", "--version"], capture_output=True, check=True)
        logger.log_info(f"huggingface-cli found: {result.stdout.strip()}")
        console.print("[green]✓ huggingface-cli found[/green]")
        tools_status['huggingface'] = True
    except:
        logger.log_info("huggingface-cli not found, installing...")
        console.print("[yellow]⚠️ huggingface-cli not found. Installing...[/yellow]")
        try:
            result = subprocess.run(
                ["pip", "install", "huggingface-hub"],
                check=True,
                capture_output=True,
                env={**os.environ, "HTTP_PROXY": PROXY_URL, "HTTPS_PROXY": PROXY_URL}
            )
            logger.log_info(f"huggingface-cli installed: {result.stdout}")
            console.print("[green]✓ huggingface-cli installed[/green]")
            tools_status['huggingface'] = True
        except Exception as e:
            logger.log_error(f"Failed to install huggingface-cli: {e}", traceback.format_exc())
            console.print("[red]✗ Failed to install huggingface-cli[/red]")
            tools_status['huggingface'] = False
    
    # Check docker
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, check=True)
        logger.log_info(f"docker found: {result.stdout.strip()}")
        console.print("[green]✓ docker found[/green]")
        tools_status['docker'] = True
    except Exception as e:
        logger.log_error("docker not found", traceback.format_exc())
        console.print("[red]✗ docker not found[/red]")
        tools_status['docker'] = False
    
    # Check git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, check=True)
        logger.log_info(f"git found: {result.stdout.strip()}")
        console.print("[green]✓ git found[/green]")
        tools_status['git'] = True
    except Exception as e:
        logger.log_error("git not found", traceback.format_exc())
        console.print("[red]✗ git not found[/red]")
        tools_status['git'] = False
    
    return tools_status

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

# PYTHON PACKAGES - CUDA ENABLED VERSIONS
PYTHON_PACKAGES = [
    # Core with CUDA
    "torch==2.3.0+cu124",
    "torchvision==0.18.0+cu124",
    "torchaudio==2.3.0+cu124",
    
    # CUDA-accelerated libraries
    "xformers==0.0.26+cu124",
    "flash-attn==2.5.9+cu124",
    "triton==2.3.0+cu124",
    
    # Inference engines (CUDA)
    "vllm==0.5.0+cu124",
    "sglang==0.2.0+cu124",
    "tensorrt-llm==0.11.0+cu124",
    
    # RAG & ML with CUDA support
    "transformers==4.40.0",
    "accelerate==0.30.0",
    "bitsandbytes==0.43.0",
    "sentence-transformers==2.7.0",
    "faiss-gpu==1.8.0",
    "cupy-cuda12x==13.0.0",
    
    # Standard libs
    "fastapi", "pydantic", "uvicorn", "httpx", "aiohttp",
    "docling", "unstructured", "pypdf", "pdfplumber", "markdown",
    "langchain", "langgraph", "llama-index", "chromadb",
    "pymilvus", "qdrant-client", "redis",
    "ragas", "deepeval", "litellm", "openai",
    "scipy", "numpy", "pandas",
]

# CUDA PACKAGES - Additional CUDA-only packages
CUDA_EXTRA_PACKAGES = [
    "cuda-python==12.4.0",
    "pycuda==2024.1",
    "numba==0.59.0",
    "cudf==24.4.0",
    "cuml==24.4.0",
    "cugraph==24.4.0",
]

# H200 MODELS
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
            # Log failed task
            logger.log_failed_task(key, details, self.state["items"][key]["retries"])
        elif status == "completed":
            if key in self.retry_queue:
                self.retry_queue.remove(key)
            logger.log_info(f"Task completed: {key}")
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
    
    tools_status = check_required_tools()
    
    console.print("\n[bold cyan]📋 Tool Status:[/bold cyan]")
    for tool, status in tools_status.items():
        icon = "✅" if status else "❌"
        console.print(f"  {icon} {tool}")
    
    if not tools_status.get('uv', False):
        console.print("\n[bold red]⚠️ uv is required![/bold red]")
        console.print("[yellow]Install manually: pip install uv[/yellow]")
        if not Confirm.ask("[cyan]Continue without uv? (will use pip)[/cyan]", default=False):
            sys.exit(1)
    
    return {'max_retries': max_retries, 'tools_status': tools_status}

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
        title="🖥️ H200 CUDA Matrix Downloader",
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
    """Run command with proxy support and comprehensive logging"""
    logger.log_debug(f"Running command: {' '.join(cmd)}")
    logger.log_debug(f"Timeout: {timeout}s, Max retries: {max_retries}")
    
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
            
            # Add custom bin path for uv
            run_env['PATH'] = f"{DIRS['bin']}:{run_env.get('PATH', '')}"
            
            logger.log_debug(f"Attempt {attempt}/{max_retries}")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=run_env)
            
            if proc.returncode == 0:
                logger.log_info(f"Command succeeded: {' '.join(cmd[:2])}")
                logger.log_debug(f"Stdout: {proc.stdout[:500]}")
                return True, proc.stdout
            else:
                error_msg = proc.stderr.strip()[:1000]
                logger.log_warning(f"Attempt {attempt} failed (exit code {proc.returncode}): {error_msg}")
                logger.log_debug(f"Full stderr: {proc.stderr}")
                
                # Check if it's a network error
                if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.log_warning("Network error detected - retrying with longer timeout")
                    timeout = timeout * 1.5
                    
        except subprocess.TimeoutExpired as e:
            logger.log_warning(f"Timeout on attempt {attempt}")
            logger.log_debug(f"Timeout details: {str(e)}")
        except Exception as e:
            logger.log_error(f"Fatal error on attempt {attempt}: {str(e)}", traceback.format_exc())
            
        if attempt < max_retries:
            wait_time = 5 * attempt
            logger.log_info(f"Retrying in {wait_time}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(wait_time)
    
    logger.log_error(f"Command failed after {max_retries} attempts: {' '.join(cmd)}")
    return False, "Max retries exceeded"

def pull_docker(image):
    logger.log_info(f"Pulling Docker image: {image}")
    success, err = run_cmd(["docker", "pull", image], max_retries=3, timeout=1200)
    if not success: 
        return False, err
    
    tar_path = DIRS["docker"] / f"{image.replace('/', '_').replace(':', '_')}.tar"
    logger.log_info(f"Saving Docker image to: {tar_path}")
    return run_cmd(["docker", "save", "-o", str(tar_path), image], max_retries=2, timeout=600)

def download_pip(pkg, cu124=False):
    """Download Python packages with comprehensive logging"""
    logger.log_info(f"Downloading package: {pkg} (CUDA: {cu124})")
    dest = DIRS["python_cu124"] if cu124 else DIRS["python"]
    
    # For CUDA packages, use the CUDA index
    if cu124:
        # Try uv first
        uv_cmd = ["uv", "pip", "download", pkg, "-d", str(dest), 
                  "--index-url", "https://download.pytorch.org/whl/cu124",
                  "--extra-index-url", "https://pypi.org/simple"]
        
        logger.log_debug(f"UV CUDA command: {' '.join(uv_cmd)}")
        success, err = run_cmd(uv_cmd, max_retries=3, timeout=600)
        if success:
            logger.log_info(f"Downloaded {pkg} with uv (CUDA)")
            return True, "uv CUDA download success"
        
        # Fallback to pip
        pip_cmd = ["pip", "download", pkg, "-d", str(dest), 
                   "--index-url", "https://download.pytorch.org/whl/cu124",
                   "--extra-index-url", "https://pypi.org/simple",
                   "--no-deps"]
        
        logger.log_debug(f"Pip CUDA command: {' '.join(pip_cmd)}")
        success, err = run_cmd(pip_cmd, max_retries=3, timeout=600)
        if success:
            logger.log_info(f"Downloaded {pkg} with pip (CUDA)")
            return True, "pip CUDA download success"
        
        return False, err
    
    # Non-CUDA packages
    uv_cmd = ["uv", "pip", "download", pkg, "-d", str(dest)]
    logger.log_debug(f"UV command: {' '.join(uv_cmd)}")
    success, err = run_cmd(uv_cmd, max_retries=3, timeout=600)
    if success:
        logger.log_info(f"Downloaded {pkg} with uv")
        return True, "uv download success"
    
    pip_cmd = ["pip", "download", pkg, "-d", str(dest), "--no-deps"]
    logger.log_debug(f"Pip command: {' '.join(pip_cmd)}")
    success, err = run_cmd(pip_cmd, max_retries=3, timeout=600)
    if success:
        logger.log_info(f"Downloaded {pkg} with pip")
        return True, "pip download success"
    
    return False, err

def download_hf_model(repo_id):
    """Download HuggingFace model with comprehensive logging"""
    logger.log_info(f"Downloading HuggingFace model: {repo_id}")
    dest_path = DIRS["models_hf"] / repo_id.replace("/", "_")
    
    cmd = [
        "huggingface-cli", "download", 
        repo_id, 
        "--local-dir", str(dest_path),
        "--local-dir-use-symlinks", "False",
        "--resume-download"
    ]
    
    logger.log_debug(f"HF download command: {' '.join(cmd)}")
    
    env = os.environ.copy()
    if 'HF_TOKEN' in os.environ:
        env['HF_TOKEN'] = os.environ['HF_TOKEN']
        logger.log_info("Using HF_TOKEN from environment")
    
    env['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
    
    success, err = run_cmd(cmd, max_retries=3, timeout=7200, env=env)
    if success:
        logger.log_info(f"Model downloaded successfully: {repo_id}")
        return True, "Model downloaded successfully"
    
    # Try Python API fallback
    logger.log_info("Trying Python API fallback...")
    try:
        from huggingface_hub import snapshot_download
        import os as os_module
        
        os_module.environ['HTTP_PROXY'] = PROXY_URL
        os_module.environ['HTTPS_PROXY'] = PROXY_URL
        
        logger.log_debug(f"Attempting snapshot_download for {repo_id}")
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(dest_path),
            local_dir_use_symlinks=False,
            resume_download=True,
            token=os.environ.get('HF_TOKEN', None),
            proxies={"http": PROXY_URL, "https": PROXY_URL}
        )
        logger.log_info(f"Model downloaded via Python API: {repo_id}")
        return True, "Model downloaded via Python API"
    except Exception as e:
        logger.log_error(f"Python API fallback failed: {str(e)}", traceback.format_exc())
        return False, f"All download methods failed: {err}"

def setup_project(project):
    name, url = project["name"], project["url"]
    logger.log_info(f"Setting up project: {name}")
    dest = PROJECTS_DIR / name
    
    if not dest.exists():
        logger.log_info(f"Cloning project: {name}")
        succ, err = run_cmd(["git", "clone", url, str(dest)], timeout=300)
        if not succ: 
            return False, f"Clone failed: {err}"
    
    req_file = dest / "requirements.txt"
    if req_file.exists():
        logger.log_info(f"Installing requirements for {name}")
        uv_succ, _ = run_cmd(["uv", "pip", "install", "-r", str(req_file)], cwd=str(dest), timeout=600)
        if uv_succ:
            logger.log_info(f"Installed {name} with uv")
            return True, "Cloned and installed with uv"
        
        logger.log_info(f"Falling back to pip for {name}")
        succ, err = run_cmd(["pip", "install", "-r", str(req_file)], cwd=str(dest), timeout=600)
        if not succ: 
            return False, f"Install failed: {err}"
        return True, "Cloned and installed with pip"
    
    return True, "Cloned successfully"

def generate_report():
    """Generate comprehensive report with all logs"""
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
                f.write(f"- **{key}** (retries: {retries}): {data['details'][:500]}\n")
        
        # Include failed tasks JSON
        failed_file = BASE_DIR / "failed_tasks.json"
        if failed_file.exists():
            f.write("\n### Detailed Failed Tasks Log:\n")
            with open(failed_file, 'r') as ff:
                f.write("```json\n")
                f.write(ff.read())
                f.write("\n```\n")
        
        # Include error log
        if ERROR_LOG.exists():
            f.write("\n### Error Log (last 50 lines):\n")
            f.write("```\n")
            with open(ERROR_LOG, 'r') as ff:
                lines = ff.readlines()
                f.write(''.join(lines[-50:]))
            f.write("```\n")
        
        f.write("\n### H200 CUDA Optimization Recommendations:\n")
        f.write("1. All CUDA packages installed from pytorch/cu124 index\n")
        f.write("2. Use vLLM with FP8 quantization for best performance\n")
        f.write("3. Enable flash-attention-2 for faster inference\n")
        f.write("4. Use batch inference for higher throughput\n")
        f.write("5. Check error logs for failed tasks:\n")
        f.write(f"   - Main log: {LOG_FILE}\n")
        f.write(f"   - Error log: {ERROR_LOG}\n")
        f.write(f"   - Failed tasks: {FAILED_TASKS_LOG}\n")
        f.write(f"   - Debug log: {DEBUG_LOG}\n")

# ======================== MAIN ORCHESTRATOR ========================
@click.command()
@click.option('--interactive', is_flag=True, help='Interactive selection of components')
@click.option('--skip-matrix', is_flag=True, help='Skip Matrix ASCII animation')
@click.option('--auto-retry', is_flag=True, help='Automatically retry failed tasks')
def main(interactive, skip_matrix, auto_retry):
    console.print("[bold cyan]🚀 H200 CUDA Offline Preparation Tool[/bold cyan]")
    console.print("[yellow]Optimized for NVIDIA H200 GPUs - All CUDA Enabled[/yellow]")
    console.print(f"[dim]Using proxy: {PROXY_URL}[/dim]\n")
    console.print("[dim]Logs saved to: offline-prep/logs/[/dim]\n")
    
    if 'HF_TOKEN' in os.environ:
        console.print("[green]✓ HF_TOKEN found in environment[/green]")
    else:
        console.print("[yellow]⚠️ No HF_TOKEN found. Public models only.[/yellow]")
    
    if interactive:
        config = interactive_selection()
        max_retries = config.get('max_retries', 3)
        state.state["max_retries"] = max_retries
        state.save()
    else:
        max_retries = state.state.get("max_retries", 3)
        check_required_tools()
    
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
                logger.log_error(f"Task {key} failed: {details}")
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.log_error(f"Crash on {key}: {error_msg}")
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
                    is_cuda = task_tuple[3] if len(task_tuple) > 3 else False
                    phase_name = "CUDA Packages" if is_cuda else "Python Packages"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]==task_type and (t[3] if len(t)>3 else False) == is_cuda]), completed=0)
                    pkg = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               matrix.get_art() if not skip_matrix else None,
                                               f"{'cuda' if is_cuda else 'pip'}: {pkg}",
                                               phase_name,
                                               len(state.get_retry_queue()),
                                               matrix.get_log_tail() if not skip_matrix else ""))
                    execute_with_ui(key, "Python_CUDA" if is_cuda else "Python_Libs", 
                                  download_pip, pkg, is_cuda)
                    
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
        logger.log_info("Installation interrupted by user")
        
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
            console.print("\n[bold yellow]💡 Failed tasks logged in:[/bold yellow]")
            console.print(f"  - {ERROR_LOG}")
            console.print(f"  - {FAILED_TASKS_LOG}")
            console.print(f"  - {BASE_DIR}/failed_tasks.json")
            console.print("\n[bold yellow]💡 To retry failed tasks:[/bold yellow]")
            console.print("  python3 enhanced_installer.py --interactive --auto-retry")
        
        console.print("\n[bold cyan]💡 Log files location:[/bold cyan]")
        console.print(f"  - Main log: {LOG_FILE}")
        console.print(f"  - Error log: {ERROR_LOG}")
        console.print(f"  - Debug log: {DEBUG_LOG}")
        console.print(f"  - Failed tasks: {FAILED_TASKS_LOG}")

if __name__ == "__main__":
    main()
