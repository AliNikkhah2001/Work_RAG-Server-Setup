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

# ======================== CONFIGURATION ========================
BASE_DIR = Path("./offline-prep")
STATE_FILE = BASE_DIR / ".state.json"
PROJECTS_DIR = BASE_DIR / "sample-projects"
REPORT_FILE = BASE_DIR / "COMPREHENSIVE_REPORT.md"
RETRY_QUEUE = BASE_DIR / ".retry_queue.json"

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
    handlers=[logging.FileHandler(BASE_DIR / "download.log")]
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

# ======================== ASCII ART INFINITE PROGRESS ========================
class ASCIIArtProgress:
    """Threaded ASCII art generator that runs in the background"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.current_art = ""
        self.lock = threading.Lock()
        self.p = 0
        self.direction = 1
        self.bar_idx = 0
        self.spin_pos = 0
        
        # ANSI color codes
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'bold': '\033[1m',
            'blink': '\033[5m',
            'end': '\033[0m'
        }
        
        self.bar_chars = [
            ['█', '░'],
            ['▓', '▒'],
            ['■', '□'],
            ['●', '○'],
            ['◄', '►'],
            ['▀', '▄'],
            ['┃', '━'],
        ]
        
        self.spinners = [
            ['|', '/', '-', '\\'],
            ['◢', '◣', '◤', '◥'],
            ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
            ['┤', '┘', '┴', '└', '├', '┌', '┬', '┐'],
        ]
        
        self.tasks = [
            "COMPILING KERNEL",
            "DECRYPTING FILES",
            "RENDERING FRAMES",
            "INDEXING DATA",
            "SYNCHRONIZING",
            "OPTIMIZING CODE",
            "CALCULATING PI",
            "DEFRAGMENTING",
            "GENERATING KEYS",
            "LOADING MODULES"
        ]
        
        self.status_messages = [
            "PROCESSING...",
            "WORKING...",
            "IN PROGRESS...",
            "CALCULATING...",
            "LOADING...",
            "EXECUTING..."
        ]
    
    def get_color(self):
        return random.choice([
            self.colors['red'], self.colors['green'], self.colors['yellow'],
            self.colors['blue'], self.colors['magenta'], self.colors['cyan']
        ])
    
    def generate_art(self):
        """Generate a single frame of ASCII art"""
        # Update progress with bounce
        self.p += self.direction * random.randint(1, 3)
        if self.p >= 100:
            self.p = 100
            self.direction = -1
            self.bar_idx = (self.bar_idx + 1) % len(self.bar_chars)
        elif self.p <= 0:
            self.p = 0
            self.direction = 1
            self.bar_idx = (self.bar_idx + 1) % len(self.bar_chars)
        
        self.spin_pos = (self.spin_pos + 1) % len(self.spinners[0])
        
        # Build the bar
        filled = int(self.p / 2)
        empty = 50 - filled
        bar_style = self.bar_chars[self.bar_idx]
        
        bar = f"{self.get_color()}{bar_style[0] * filled}{self.colors['end']}"
        bar += f"{self.colors['white']}{bar_style[1] * empty}{self.colors['end']}"
        
        # Generate random status
        task = random.choice(self.tasks)
        status = random.choice(self.status_messages)
        cpu = random.randint(1, 99)
        mem = random.randint(1, 99)
        
        # Build the ASCII art - condensed version for panel display
        art = f"""{self.colors['bold']}{self.get_color()}╔══════════════════════════════════════════════╗{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.colors['blink']}{self.get_color()}░░░ INFINITE PROGRESS ░░░{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╠══════════════════════════════════════════════╣{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}[{self.colors['end']}{bar}{self.get_color()}]{self.colors['end']} {self.get_color()}{self.p:3d}%{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╠══════════════════════════════════════════════╣{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}▶ {self.colors['end']}{self.get_color()}{self.spinners[0][self.spin_pos]}{self.colors['end']}  {self.get_color()}{task[:20]}{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}⚡ {self.colors['end']}{self.get_color()}CPU:{cpu:2d}% MEM:{mem:2d}%{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}⌛ {self.colors['end']}{self.colors['red']}∞ ETA{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╚══════════════════════════════════════════════╝{self.colors['end']}"""
        return art
    
    def _run(self):
        """Background thread that continuously updates ASCII art"""
        while self.running:
            with self.lock:
                self.current_art = self.generate_art()
            time.sleep(random.uniform(0.08, 0.2))
    
    def start(self):
        """Start the ASCII art thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop the ASCII art thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def get_art(self):
        """Get the current ASCII art frame"""
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
            # Add to retry queue if under max retries
            if self.state["items"][key]["retries"] <= self.state.get("max_retries", 3):
                if key not in self.retry_queue:
                    self.retry_queue.append(key)
        elif status == "completed":
            # Remove from retry queue if completed
            if key in self.retry_queue:
                self.retry_queue.remove(key)
        self.save()

    def is_completed(self, key):
        return self.state["items"].get(key, {}).get("status") == "completed"
    
    def get_failed_items(self):
        return {k: v for k, v in self.state["items"].items() if v.get("status") == "failed"}
    
    def get_pending_items(self):
        """Get items that haven't been attempted yet"""
        all_items = set()
        for img, _ in DOCKER_IMAGES: all_items.add(f"docker_{img}")
        for pkg in PYTHON_PACKAGES: all_items.add(f"pip_{pkg}")
        for pkg in CUDA_PACKAGES: all_items.add(f"pip_cu124_{pkg}")
        for repo in MODELS.keys(): all_items.add(f"model_{repo}")
        for proj in SAMPLE_PROJECTS: all_items.add(f"project_{proj['name']}")
        
        completed = set(self.state["items"].keys())
        return list(all_items - completed)
    
    def get_retry_queue(self):
        """Get items that need retrying"""
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
    
    # Show current state summary
    total = len(state.state["items"])
    completed = sum(1 for v in state.state["items"].values() if v.get("status") == "completed")
    failed = sum(1 for v in state.state["items"].values() if v.get("status") == "failed")
    
    console.print(f"[yellow]Current progress: {completed}/{total} completed, {failed} failed[/yellow]\n")
    
    # Ask if user wants to continue previous session
    if total > 0:
        if not Confirm.ask("[cyan]Continue previous installation session?[/cyan]", default=True):
            # Reset state
            state.state = {"items": {}, "retry_count": 0, "max_retries": 3}
            state.retry_queue = []
            state.save()
            console.print("[green]State reset[/green]")
    
    # Configure retry settings
    max_retries = IntPrompt.ask(
        "[cyan]Max retry attempts for failed downloads[/cyan]",
        default=state.state.get("max_retries", 3),
        show_default=True
    )
    state.state["max_retries"] = max_retries
    state.save()
    
    # Show available tasks
    pending = state.get_pending_items()
    if pending:
        console.print(f"\n[green]📋 {len(pending)} tasks pending[/green]")
        if not Confirm.ask("[cyan]Install all pending tasks?[/cyan]", default=True):
            # If not, we'll continue with all tasks
            pass
    
    # Show retry queue
    retry_items = state.get_retry_queue()
    if retry_items:
        console.print(f"\n[yellow]🔄 {len(retry_items)} tasks in retry queue[/yellow]")
        if Confirm.ask("[cyan]Retry failed tasks now?[/cyan]", default=True):
            # This will be handled in the main loop
            pass
    
    return {
        'max_retries': max_retries,
        'retry_failed': True
    }

# ======================== ENHANCED UI DASHBOARD ========================
def generate_layout(progress_ui, ascii_art=None, current_task="", phase_name="", retry_count=0):
    """Generates the split live-dashboard with ASCII art integration"""
    
    # Main metrics table
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
    
    # Failed items list (if any)
    failed_items = state.get_failed_items()
    if failed_items:
        fail_table = Table(box=box.MINIMAL, expand=True)
        fail_table.add_column("⚠️ Failed Items", style="red")
        for key in list(failed_items.keys())[:5]:
            retries = failed_items[key].get("retries", 0)
            fail_table.add_row(f"  • {key} (retries: {retries})")
        if len(failed_items) > 5:
            fail_table.add_row(f"  • ... and {len(failed_items) - 5} more")
    else:
        fail_table = Table(box=box.MINIMAL, expand=True)
        fail_table.add_row("[green]✓ No failures[/green]")
    
    # Current task info
    task_panel = Panel(
        f"[bold yellow]Current Task:[/bold yellow] {current_task or 'Waiting...'}",
        border_style="yellow",
        box=box.ROUNDED
    )
    
    # Combine components
    components = [table, fail_table, task_panel]
    
    # Add ASCII art panel if available
    if ascii_art:
        art_panel = Panel(
            Align.center(ascii_art),
            title="🎨 Infinite ASCII Progress",
            border_style="magenta",
            box=box.HEAVY
        )
        components.append(art_panel)
    
    # Add progress bar
    components.append(progress_ui)
    
    return Group(*components)

# ======================== CORE LOGIC ========================
def run_cmd(cmd, max_retries=3, timeout=600, cwd=None):
    for attempt in range(1, max_retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
            if proc.returncode == 0: return True, proc.stdout
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
    success, err = run_cmd(["docker", "pull", image], max_retries=3, timeout=1200)
    if not success: return False, err
    tar_path = DIRS["docker"] / f"{image.replace('/', '_').replace(':', '_')}.tar"
    return run_cmd(["docker", "save", "-o", str(tar_path), image], max_retries=2, timeout=600)

def download_pip(pkg, cu124=False):
    dest = DIRS["python_cu124"] if cu124 else DIRS["python"]
    cmd = ["uv", "pip", "download", pkg, "-d", str(dest)]
    if cu124: cmd.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    
    success, _ = run_cmd(cmd, max_retries=2)
    if success: return True, "uv success"
    
    fallback = ["pip", "download", pkg, "-d", str(dest)]
    if cu124: fallback.extend(["--index-url", "https://download.pytorch.org/whl/cu124"])
    return run_cmd(fallback, max_retries=2)

def download_hf_model(repo_id):
    dest_path = DIRS["models_hf"] / repo_id.replace("/", "_")
    cmd = ["huggingface-cli", "download", repo_id, "--local-dir", str(dest_path), "--local-dir-use-symlinks", "False", "--resume-download"]
    return run_cmd(cmd, max_retries=5, timeout=7200)

def test_venv_imports(venv_python, packages):
    test_script = "; ".join([f"import {pkg.replace('-', '_')}" for pkg in packages[:3]])
    success, _ = run_cmd([venv_python, "-c", test_script], timeout=60)
    return success

def setup_project(project):
    name, url = project["name"], project["url"]
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
@click.option('--skip-ascii', is_flag=True, help='Skip ASCII art animation')
@click.option('--auto-retry', is_flag=True, help='Automatically retry failed tasks without prompting')
def main(interactive, skip_ascii, auto_retry):
    # Interactive configuration
    if interactive:
        config = interactive_selection()
        max_retries = config.get('max_retries', 3)
        state.state["max_retries"] = max_retries
        state.save()
    else:
        max_retries = state.state.get("max_retries", 3)
    
    # Start ASCII art thread
    ascii_art = ASCIIArtProgress()
    if not skip_ascii:
        ascii_art.start()
    
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
    
    # Add retry queue tasks (if not already in pending)
    retry_items = state.get_retry_queue()
    for key in retry_items:
        # Find the task tuple for this key
        for task_tuple in all_tasks:
            if task_tuple[1] == key and task_tuple not in pending_tasks:
                pending_tasks.append(task_tuple)
                break
    
    # Calculate total tasks
    metrics["total"] = len(pending_tasks)
    
    # If no tasks pending, check if we need to retry
    if metrics["total"] == 0 and retry_items:
        console.print("[yellow]All tasks completed, but some failed items in retry queue[/yellow]")
        if Confirm.ask("[cyan]Retry failed tasks?[/cyan]", default=True):
            # Add retry items to pending
            for key in retry_items:
                for task_tuple in all_tasks:
                    if task_tuple[1] == key:
                        pending_tasks.append(task_tuple)
                        break
            metrics["total"] = len(pending_tasks)
    
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
        
        # Check if we should auto-retry
        retry_items = state.get_retry_queue()
        if retry_items and auto_retry:
            # Process retry queue immediately
            process_retry_queue()

    def process_retry_queue():
        """Process items in the retry queue"""
        retry_items = state.get_retry_queue()
        if not retry_items:
            return
        
        # Add retry items to pending tasks
        for key in retry_items:
            for task_tuple in all_tasks:
                if task_tuple[1] == key:
                    # Add back to pending
                    if task_tuple not in pending_tasks:
                        pending_tasks.append(task_tuple)
                    break

    # Main execution loop with Live display
    try:
        with Live(generate_layout(progress_ui, 
                                 ascii_art.get_art() if not skip_ascii else None,
                                 "Waiting to start...",
                                 "Initializing"),
                  refresh_per_second=10, 
                  screen=True) as live:
            
            # Process all pending tasks
            while pending_tasks:
                # Get next task
                task_tuple = pending_tasks.pop(0)
                task_type = task_tuple[0]
                key = task_tuple[1]
                
                # Skip if already completed
                if state.is_completed(key):
                    progress_ui.advance(overall_task)
                    continue
                
                # Execute based on type
                if task_type == "docker":
                    phase_name = f"Docker Images ({len([t for t in all_tasks if t[0]=='docker'])})"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]=='docker']), completed=0)
                    img = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               ascii_art.get_art() if not skip_ascii else None,
                                               f"docker: {img}",
                                               phase_name,
                                               len(state.get_retry_queue())))
                    execute_with_ui(key, "Docker", pull_docker, img)
                    
                elif task_type in ["pip", "pip_cuda"]:
                    phase_name = "Python Packages (CUDA)" if task_type == "pip_cuda" else "Python Packages"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]==task_type]), completed=0)
                    pkg = task_tuple[2]
                    cu124 = task_tuple[3] if len(task_tuple) > 3 else False
                    live.update(generate_layout(progress_ui, 
                                               ascii_art.get_art() if not skip_ascii else None,
                                               f"{'cuda' if cu124 else 'pip'}: {pkg}",
                                               phase_name,
                                               len(state.get_retry_queue())))
                    execute_with_ui(key, "Python_Libs" if not cu124 else "Python_Libs_CUDA", 
                                  download_pip, pkg, cu124)
                    
                elif task_type == "model":
                    phase_name = "HuggingFace Models"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]=='model']), completed=0)
                    repo = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               ascii_art.get_art() if not skip_ascii else None,
                                               f"model: {repo}",
                                               phase_name,
                                               len(state.get_retry_queue())))
                    execute_with_ui(key, "Models", download_hf_model, repo)
                    
                elif task_type == "project":
                    phase_name = "GitHub Projects"
                    progress_ui.update(phase_task, description=f"[bold magenta]{phase_name}", 
                                     total=len([t for t in all_tasks if t[0]=='project']), completed=0)
                    proj = task_tuple[2]
                    live.update(generate_layout(progress_ui, 
                                               ascii_art.get_art() if not skip_ascii else None,
                                               f"project: {proj['name']}",
                                               phase_name,
                                               len(state.get_retry_queue())))
                    execute_with_ui(key, "Sample_Projects", setup_project, proj)
                
                # After each task, check if we need to add retries back to queue
                if not auto_retry:
                    retry_items = state.get_retry_queue()
                    if retry_items:
                        # Ask if user wants to retry now
                        live.update(generate_layout(progress_ui, 
                                                   ascii_art.get_art() if not skip_ascii else None,
                                                   f"⚠️ {len(retry_items)} tasks failed",
                                                   "Waiting for retry decision",
                                                   len(retry_items)))
                        # We'll handle this in the next loop iteration
                        time.sleep(0.5)
                
                # If auto-retry is enabled, retry queue items will be processed immediately
                if auto_retry and state.get_retry_queue():
                    # Add retry items back to pending
                    for retry_key in state.get_retry_queue():
                        for task in all_tasks:
                            if task[1] == retry_key and task not in pending_tasks:
                                pending_tasks.append(task)
                                break
            
            # Final update - all done
            live.update(generate_layout(progress_ui, 
                                       ascii_art.get_art() if not skip_ascii else None,
                                       "✅ All phases completed!",
                                       "Complete",
                                       len(state.get_retry_queue())))
            time.sleep(2)
    
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️ Installation interrupted by user[/bold yellow]")
        console.print("[cyan]State saved. You can resume later with: python3 enhanced_installer.py --interactive[/cyan]")
        
    finally:
        # Cleanup
        if not skip_ascii:
            ascii_art.stop()
        
        generate_report()
        console.print(f"\n[bold green]📊 Report generated: {REPORT_FILE}[/bold green]")
        
        # Show final summary
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
        elif retry_count > 0:
            console.print("\n[bold yellow]💡 Tasks in retry queue. Run:[/bold yellow]")
            console.print("  python3 enhanced_installer.py --interactive --auto-retry")

if __name__ == "__main__":
    main()
