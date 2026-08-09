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

# Rich UI Imports for the CLI Dashboard
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
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.text import Text
from rich.layout import Layout
from rich.columns import Columns

# ======================== CONFIGURATION ========================
BASE_DIR = Path("./offline-prep")
STATE_FILE = BASE_DIR / ".state.json"
PROJECTS_DIR = BASE_DIR / "sample-projects"
REPORT_FILE = BASE_DIR / "COMPREHENSIVE_REPORT.md"
RETRY_QUEUE = BASE_DIR / ".retry_queue.json"
LOG_FILE = BASE_DIR / "download.log"

DIRS = {
    "docker": BASE_DIR / "docker-images",
    "python": BASE_DIR / "python-packages",
    "python_cu124": BASE_DIR / "python-packages-cu124",
    "models_hf": BASE_DIR / "models" / "huggingface"
}

for d in DIRS.values(): d.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Logs go ONLY to file to prevent corrupting the beautiful Rich UI dashboard
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE)]
)
logger = logging.getLogger(__name__)
console = Console()

# ======================== THE 2026 ENTERPRISE ECOSYSTEM ========================

DOCKER_IMAGES = [
    ("ghcr.io/open-webui/open-webui:main", "Open WebUI"),
    ("vllm/vllm-openai:latest", "vLLM Inference Server"),
    ("pgvector/pgvector:pg16", "PostgreSQL+pgvector"),
    ("milvusdb/milvus:latest", "Milvus Vector DB"),
    ("qdrant/qdrant:latest", "Qdrant Vector DB"),
    ("redis:7-alpine", "Redis"),
    ("grafana/grafana-oss:latest", "Grafana Monitoring"),
]

PYTHON_PACKAGES = [
    # Core APIs
    "fastapi", "pydantic", "uvicorn", 
    # State-of-the-Art Document Parsing
    "docling", "docling-parse", "unstructured", "magic-pdf", "marker-pdf",
    # Agent & RAG Frameworks
    "langchain", "langgraph", "llama-index", "smolagents", "lightrag-hku", "llama-stack",
    # Vector DB Clients
    "pymilvus", "qdrant-client", "chromadb", 
    # Evals & Middleware
    "ragas", "deepeval", "nemo-guardrails", "litellm", "openai", "sentence-transformers"
]

CUDA_PACKAGES = [
    "torch", "torchvision", "xformers", "vllm", "sglang", "flash-attn", "unsloth"
]

MODELS = {
    "meta-llama/Llama-3.1-70B-Instruct": "Llama 70B Instruct (Native FP16)",
    "Qwen/Qwen2.5-72B-Instruct": "Qwen 72B Instruct FP16",
    "BAAI/bge-m3": "BGE M3 Multilingual Embeddings",
    "meta-llama/Prompt-Guard-86M": "Llama Prompt Guard"
}

SAMPLE_PROJECTS = [
    {"name": "dify", "url": "https://github.com/langgenius/dify.git"},
    {"name": "anything-llm", "url": "https://github.com/mintplex-labs/anything-llm.git"},
    {"name": "ragflow", "url": "https://github.com/infiniflow/ragflow.git"},
    {"name": "lightrag", "url": "https://github.com/hkuds/lightrag.git"},
    {"name": "guardrail-system-rag", "url": "https://github.com/lamhotsiagian/guardrail-system-rag.git"},
    {"name": "prod-rag-systems", "url": "https://github.com/vishalanandl177/production-rag-systems-engineering.git"}
]

# ======================== MATRIX STYLE ASCII ART (SMALLER) ========================
class MatrixASCII:
    """Matrix-style animated ASCII art (compact version)"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.current_art = ""
        self.lock = threading.Lock()
        self.width = 40  # Smaller width
        self.height = 5  # Smaller height
        
        # Matrix characters
        self.chars = [
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
            'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
            'U', 'V', 'W', 'X', 'Y', 'Z'
        ]
        
        # Color codes
        self.colors = {
            'green': '\033[92m',
            'light_green': '\033[92m',
            'dark_green': '\033[32m',
            'bright_green': '\033[96m',
            'white': '\033[97m',
            'yellow': '\033[93m',
            'bold': '\033[1m',
            'dim': '\033[2m',
            'end': '\033[0m'
        }
        
        # Matrix columns
        self.columns = []
        self.init_columns()
        
        # Log tail
        self.log_lines = []
        self.log_lock = threading.Lock()
        
    def init_columns(self):
        """Initialize matrix columns with random speeds"""
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
        """Generate a compact Matrix-style frame"""
        # Update columns
        matrix = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        
        for col in self.columns:
            # Move column down
            col['y'] = (col['y'] + col['speed']) % (self.height + col['length'])
            
            # Draw column
            for i in range(col['length']):
                y_pos = (col['y'] - i) % self.height
                if 0 <= y_pos < self.height:
                    if i == 0:
                        # Head of the column (bright)
                        matrix[y_pos][col['x']] = f"{self.colors['bright_green']}{random.choice(self.chars)}{self.colors['end']}"
                    elif i < col['length'] // 2:
                        # Body (green)
                        matrix[y_pos][col['x']] = f"{self.colors['green']}{random.choice(self.chars)}{self.colors['end']}"
                    else:
                        # Tail (dim)
                        matrix[y_pos][col['x']] = f"{self.colors['dim']}{self.colors['dark_green']}{random.choice(self.chars)}{self.colors['end']}"
            
            # Randomly change character
            if random.random() < 0.3:
                col['char'] = random.choice(self.chars)
        
        # Build the ASCII art string
        art_lines = []
        for row in matrix:
            line = ''.join(row)
            art_lines.append(line)
        
        # Simple compact border
        art = f"{self.colors['green']}╔{'═' * (self.width + 2)}╗{self.colors['end']}\n"
        for line in art_lines:
            art += f"{self.colors['green']}║{self.colors['end']}{line}{self.colors['green']}║{self.colors['end']}\n"
        art += f"{self.colors['green']}╚{'═' * (self.width + 2)}╝{self.colors['end']}"
        
        return art
    
    def _run(self):
        """Background thread that continuously updates Matrix art"""
        while self.running:
            with self.lock:
                self.current_art = self.generate_art()
                # Update log tail
                with self.log_lock:
                    self.update_log_tail()
            time.sleep(random.uniform(0.05, 0.15))
    
    def update_log_tail(self):
        """Read last few lines from log file"""
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
                self.log_lines = lines[-10:] if lines else ["[INFO] No logs yet..."]
        except Exception:
            self.log_lines = ["[INFO] Waiting for logs..."]
    
    def get_log_tail(self):
        """Get formatted log tail (last 5 lines for compact display)"""
        with self.log_lock:
            if not self.log_lines:
                return "[INFO] No logs yet..."
            
            # Format and colorize logs - show last 5 lines only
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
        """Start the Matrix thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop the Matrix thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def get_art(self):
        """Get the current Matrix art frame"""
        with self.lock:
            return self.current_art

# ======================== STATE & METRICS ========================
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
    
    def get_pending_items(self):
        all_items = set()
        for img, _ in DOCKER_IMAGES: all_items.add(f"docker_{img}")
        for pkg in PYTHON_PACKAGES: all_items.add(f"pip_{pkg}")
        for pkg in CUDA_PACKAGES: all_items.add(f"pip_cu124_{pkg}")
        for repo in MODELS.keys(): all_items.add(f"model_{repo}")
        for proj in SAMPLE_PROJECTS: all_items.add(f"project_{proj['name']}")
        
        completed = set(self.state["items"].keys())
        return list(all_items - completed)
    
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
    """Allow user to select/modify packages before installation"""
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
    
    return {'max_retries': max_retries}

# ======================== ENHANCED UI DASHBOARD ========================
def generate_layout(progress_ui, matrix_art=None, current_task="", phase_name="", retry_count=0, log_tail=""):
    """Generates the split live-dashboard with compact Matrix art and log tail"""
    
    # Main metrics table (left side)
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
    
    # Failed items list (right side, compact)
    failed_items = state.get_failed_items()
    if failed_items:
        fail_text = "\n".join([f"  • {key[:35]} (retries: {v.get('retries', 0)})" 
                               for key, v in list(failed_items.items())[:3]])
        if len(failed_items) > 3:
            fail_text += f"\n  • ... and {len(failed_items) - 3} more"
        fail_panel = Panel(fail_text, title="⚠️ Failed Items", border_style="red", box=box.ROUNDED)
    else:
        fail_panel = Panel("[green]✓ No failures[/green]", title="✅ Status", border_style="green", box=box.ROUNDED)
    
    # Current task info
    task_panel = Panel(
        f"[bold yellow]{current_task or 'Waiting...'}[/bold yellow]",
        title="Current Task",
        border_style="yellow",
        box=box.ROUNDED
    )
    
    # Matrix art panel (compact)
    art_panel = Panel(
        Align.center(matrix_art or "[dim]Initializing Matrix...[/dim]"),
        title="🖥️ Matrix Downloader",
        border_style="green",
        box=box.HEAVY,
        height=9  # Fixed height
    )
    
    # Log tail panel (always visible at bottom)
    log_panel = Panel(
        log_tail or "[dim]Waiting for logs...[/dim]",
        title="📋 Live Log Tail",
        border_style="blue",
        box=box.ROUNDED,
        height=6  # Fixed height
    )
    
    # Combine components in a vertical layout
    # Top: Metrics and Status (2 columns)
    top_row = Group(table, fail_panel)  # This creates a horizontal grouping
    
    # Middle: Task + Matrix
    middle_row = Group(task_panel, art_panel)
    
    # Bottom: Log tail
    bottom_row = log_panel
    
    # Progress at the very bottom
    progress_row = progress_ui
    
    # Combine everything
    return Group(top_row, middle_row, bottom_row, progress_row)

# ======================== CORE LOGIC ========================
def run_cmd(cmd, max_retries=3, timeout=600, cwd=None):
    for attempt in range(1, max_retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
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
    cmd = ["uv", "pip", "download", pkg, "-d", str(dest)]
    if cu124: cmd.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    
    success, _ = run_cmd(cmd, max_retries=2)
    if success: return True, "uv success"
    
    fallback = ["pip", "download", pkg, "-d", str(dest)]
    if cu124: fallback.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    return run_cmd(fallback, max_retries=2)

def download_hf_model(repo_id):
    logger.info(f"Downloading HuggingFace model: {repo_id}")
    dest_path = DIRS["models_hf"] / repo_id.replace("/", "_")
    cmd = ["huggingface-cli", "download", repo_id, "--local-dir", str(dest_path), "--local-dir-use-symlinks", "False", "--resume-download"]
    return run_cmd(cmd, max_retries=5, timeout=7200)

def test_venv_imports(venv_python, packages):
    test_script = "; ".join([f"import {pkg.replace('-', '_')}" for pkg in packages[:3]])
    success, _ = run_cmd([venv_python, "-c", test_script], timeout=60)
    return success

def setup_project(project):
    name, url = project["name"], project["url"]
    logger.info(f"Setting up project: {name}")
    dest = PROJECTS_DIR / name
    
    if not dest.exists():
        succ, err = run_cmd(["git", "clone", url, str(dest)], timeout=300)
        if not succ: return False, f"Clone failed: {err}"
        
    venv_dir = dest / ".venv"
    if not venv_dir.exists(): run_cmd(["uv", "venv", str(venv_dir)], cwd=str(dest))
    venv_python = str(venv_dir / "bin" / "python")
    
    req_file, pyproj = dest / "requirements.txt", dest / "pyproject.toml"
    
    if req_file.exists():
        succ, err = run_cmd(["uv", "pip", "install", "-p", venv_python, "-r", "requirements.txt"], cwd=str(dest), timeout=600)
        if not succ: return False, f"Install failed: {err}"
        
        with open(req_file, "r") as f:
            pkgs = [line.split("==")[0].strip() for line in f if line.strip() and not line.startswith(("#", "-"))]
        if pkgs and test_venv_imports(venv_python, pkgs):
            return True, "Cloned, installed, and load-tested successfully."
        return True, "Cloned and installed, but load test failed or was skipped."
        
    elif pyproj.exists():
        succ, err = run_cmd(["uv", "sync"], cwd=str(dest), timeout=600)
        if not succ: return False, f"uv sync failed: {err}"
        return True, "Cloned and synced via pyproject.toml"
        
    return True, "Cloned, but no Python dependencies found."

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
        
        f.write("\n### Pending Items:\n")
        pending = state.get_pending_items()
        if pending:
            for item in pending:
                f.write(f"- {item}\n")
        else:
            f.write("- None (all tasks completed or in retry queue)\n")
        
        f.write("\nCheck `download.log` for full console outputs.\n")

# ======================== MAIN ORCHESTRATOR ========================
@click.command()
@click.option('--interactive', is_flag=True, help='Interactive selection of components')
@click.option('--skip-matrix', is_flag=True, help='Skip Matrix ASCII animation')
@click.option('--auto-retry', is_flag=True, help='Automatically retry failed tasks without prompting')
def main(interactive, skip_matrix, auto_retry):
    # Interactive configuration
    if interactive:
        config = interactive_selection()
        max_retries = config.get('max_retries', 3)
        state.state["max_retries"] = max_retries
        state.save()
    else:
        max_retries = state.state.get("max_retries", 3)
    
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
    
    # Filter tasks - only pending or retry
    pending_tasks = []
    for task_tuple in all_tasks:
        key = task_tuple[1]
        if not state.is_completed(key):
            pending_tasks.append(task_tuple)
    
    # Add retry queue tasks
    retry_items = state.get_retry_queue()
    for key in retry_items:
        for task_tuple in all_tasks:
            if task_tuple[1] == key and task_tuple not in pending_tasks:
                pending_tasks.append(task_tuple)
                break
    
    metrics["total"] = len(pending_tasks)
    
    if metrics["total"] == 0 and retry_items:
        console.print("[yellow]All tasks completed, but some failed items in retry queue[/yellow]")
        if Confirm.ask("[cyan]Retry failed tasks?[/cyan]", default=True):
            for key in retry_items:
                for task_tuple in all_tasks:
                    if task_tuple[1] == key:
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

    # Main execution loop
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
                    phase_name = f"Docker Images"
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
                
                # Auto-retry logic
                if auto_retry and state.get_retry_queue():
                    for retry_key in state.get_retry_queue():
                        for task in all_tasks:
                            if task[1] == retry_key and task not in pending_tasks:
                                pending_tasks.append(task)
                                break
            
            # Final update
            live.update(generate_layout(progress_ui, 
                                       matrix.get_art() if not skip_matrix else None,
                                       "✅ All phases completed!",
                                       "Complete",
                                       len(state.get_retry_queue()),
                                       matrix.get_log_tail() if not skip_matrix else ""))
            time.sleep(2)
    
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️ Installation interrupted by user[/bold yellow]")
        console.print("[cyan]State saved. You can resume later with: python3 enhanced_installer.py --interactive[/cyan]")
        
    finally:
        if not skip_matrix:
            matrix.stop()
        
        generate_report()
        console.print(f"\n[bold green]📊 Report generated: {REPORT_FILE}[/bold green]")
        
        total = len(state.state["items"])
        completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
        failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
        retry_count = len(state.get_retry_queue())
        
        console.print("\n[bold cyan]=== FINAL SUMMARY ===[/bold cyan]")
        console.print(f"Total tasks attempted: {total}")
        console.print(f"[green]✅ Completed: {completed}[/green]")
        console.print(f"[red]❌ Failed: {failed}[/red]")
        console.print(f"[yellow]🔄 In retry queue: {retry_count}[/yellow]")
        
        if failed > 0:
            console.print("\n[bold yellow]💡 To retry failed tasks:[/bold yellow]")
            console.print("  python3 enhanced_installer.py --interactive --auto-retry")

if __name__ == "__main__":
    main()
