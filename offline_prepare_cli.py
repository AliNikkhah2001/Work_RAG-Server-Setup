#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
import click
import questionary

# Rich UI Imports for the CLI Dashboard
from rich.live import Live
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn, 
    TimeElapsedColumn, TimeRemainingColumn
)
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich import box

# ======================== CONFIGURATION ========================
BASE_DIR = Path("./offline-prep")
STATE_FILE = BASE_DIR / ".state.json"
PROJECTS_DIR = BASE_DIR / "sample-projects"
REPORT_FILE = BASE_DIR / "COMPREHENSIVE_REPORT.md"

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

TOTAL_TASKS = len(DOCKER_IMAGES) + len(PYTHON_PACKAGES) + len(CUDA_PACKAGES) + len(MODELS) + len(SAMPLE_PROJECTS)

# ======================== STATE & METRICS ========================
class StateManager:
    def __init__(self):
        self.state = {"items": {}}
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f: self.state = json.load(f)
            except json.JSONDecodeError: pass

    def save(self):
        with open(STATE_FILE, "w") as f: json.dump(self.state, f, indent=2)

    def set_item(self, key, status, category, details=""):
        self.state["items"][key] = {
            "status": status, "category": category, 
            "details": str(details), "updated": datetime.now().isoformat()
        }
        self.save()

    def is_completed(self, key):
        return self.state["items"].get(key, {}).get("status") == "completed"

state = StateManager()
metrics = {"completed": 0, "failed": 0, "total": TOTAL_TASKS}

for k, v in state.state["items"].items():
    if v.get("status") == "completed": metrics["completed"] += 1
    elif v.get("status") == "failed": metrics["failed"] += 1

# ======================== UI DASHBOARD ========================
def generate_layout(progress_ui):
    """Generates the split live-dashboard (Table + Progress Bars)"""
    table = Table(title="📊 Live Installation Summary", box=box.ROUNDED, expand=True)
    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Count", style="magenta", justify="right")
    
    table.add_row("Total Tasks Scheduled", str(metrics["total"]))
    table.add_row("✅ Successfully Completed", f"[bold green]{metrics['completed']}[/bold green]")
    table.add_row("❌ Failed / Skipped", f"[bold red]{metrics['failed']}[/bold red]")
    
    prog_panel = Panel(progress_ui, title="🚀 Download & Build Progress", border_style="blue", box=box.ROUNDED)
    return Group(table, prog_panel)

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
        if attempt < max_retries: time.sleep(5 * attempt)
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
        
        # Smoke Test
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
        f.write(f"- **✅ Completed:** {metrics['completed']}\n")
        f.write(f"- **❌ Failed:** {metrics['failed']}\n\n")
        
        f.write("### Error Traces:\n")
        for key, data in state.state["items"].items():
            if data["status"] == "failed":
                f.write(f"- **{key}**: {data['details']}\n")
        
        f.write("\nCheck `download.log` for full console outputs.\n")

# ======================== MAIN ORCHESTRATOR ========================
@click.command()
def main():
    progress_ui = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
    
    overall_task = progress_ui.add_task("[bold cyan]Total Overall Progress", total=metrics["total"], completed=metrics["completed"]+metrics["failed"])
    phase_task = progress_ui.add_task("[bold magenta]Current Phase", total=0)
    current_item_task = progress_ui.add_task("[bold yellow]Waiting to start...", total=None)
    
    def execute_with_ui(key, category, func, *args, **kwargs):
        if state.is_completed(key): 
            progress_ui.advance(overall_task)
            progress_ui.advance(phase_task)
            return
            
        progress_ui.update(current_item_task, description=f"[bold yellow]Current Task:[/] {key}")
        
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

    with Live(generate_layout(progress_ui), refresh_per_second=4, get_renderable=lambda: generate_layout(progress_ui)):
        
        progress_ui.update(phase_task, description="[bold magenta]Phase 1/5: Docker Images", total=len(DOCKER_IMAGES), completed=0)
        for img, _ in DOCKER_IMAGES:
            execute_with_ui(f"docker_{img}", "Docker", pull_docker, img)
            
        progress_ui.update(phase_task, description="[bold magenta]Phase 2/5: Python Libs", total=len(PYTHON_PACKAGES), completed=0)
        for pkg in PYTHON_PACKAGES:
            execute_with_ui(f"pip_{pkg}", "Python_Libs", download_pip, pkg, cu124=False)
            
        progress_ui.update(phase_task, description="[bold magenta]Phase 3/5: CUDA Acceleration", total=len(CUDA_PACKAGES), completed=0)
        for pkg in CUDA_PACKAGES:
            execute_with_ui(f"pip_cu124_{pkg}", "Python_Libs_CUDA", download_pip, pkg, cu124=True)
            
        progress_ui.update(phase_task, description="[bold magenta]Phase 4/5: HuggingFace Models", total=len(MODELS), completed=0)
        for repo in MODELS.keys():
            execute_with_ui(f"model_{repo}", "Models", download_hf_model, repo)
            
        progress_ui.update(phase_task, description="[bold magenta]Phase 5/5: Baking GitHub Projects", total=len(SAMPLE_PROJECTS), completed=0)
        for proj in SAMPLE_PROJECTS:
            execute_with_ui(f"project_{proj['name']}", "Sample_Projects", setup_project, proj)

        progress_ui.update(current_item_task, description="[bold green]✅ All phases completed!")

    generate_report()
    print(f"\n🎉 Setup Finished! Report generated at: {REPORT_FILE}")

if __name__ == "__main__":
    main()
