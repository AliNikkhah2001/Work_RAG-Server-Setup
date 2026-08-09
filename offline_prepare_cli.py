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
import questionary

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
from rich.layout import Layout
from rich.align import Align

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
console = Console()

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
        
        # Build the ASCII art
        art = f"""
{self.colors['bold']}{self.get_color()}╔══════════════════════════════════════════════════════════════════╗{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.colors['blink']}{self.get_color()}░░░░░ INFINITE PROGRESS BAR ░░░░░{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╠══════════════════════════════════════════════════════════════════╣{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}                                                          {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}[{self.colors['end']}{bar}{self.get_color()}]{self.colors['end']}  {self.get_color()}{self.p:3d}%{self.colors['end']}     {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}                                                          {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╠══════════════════════════════════════════════════════════════════╣{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}SPINNER: {self.colors['end']}{self.get_color()}{self.spinners[0][self.spin_pos]}{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}TASK:   {self.colors['end']}{self.get_color()}{task}{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╠══════════════════════════════════════════════════════════════════╣{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}CPU: {self.colors['end']}{self.get_color()}{cpu:2d}%{self.colors['end']}  {self.get_color()}MEM: {self.colors['end']}{self.get_color()}{mem:2d}%{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}ETA:  {self.colors['end']}{self.colors['red']}∞ INFINITE{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╠══════════════════════════════════════════════════════════════════╣{self.colors['end']}
{self.colors['bold']}{self.get_color()}║{self.colors['end']}  {self.get_color()}{status}{self.colors['end']}  {self.get_color()}PRESS CTRL+C TO EXIT{self.colors['end']}  {self.colors['bold']}{self.get_color()}║{self.colors['end']}
{self.colors['bold']}{self.get_color()}╚══════════════════════════════════════════════════════════════════╝{self.colors['end']}
"""
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
    
    def get_failed_items(self):
        return {k: v for k, v in self.state["items"].items() if v.get("status") == "failed"}

state = StateManager()
metrics = {"completed": 0, "failed": 0, "total": 0}

# ======================== INTERACTIVE SELECTION ========================
def interactive_selection():
    """Allow user to select/modify packages before installation"""
    console.print("\n[bold cyan]🔧 INTERACTIVE CONFIGURATION[/bold cyan]\n")
    
    # Select Docker images
    docker_selected = questionary.checkbox(
        "Select Docker images to download:",
        choices=[(f"{name} ({img})", img) for img, name in DOCKER_IMAGES],
        default=[img for img, _ in DOCKER_IMAGES]
    ).ask()
    
    # Select Python packages
    pkg_selected = questionary.checkbox(
        "Select Python packages to download:",
        choices=PYTHON_PACKAGES,
        default=PYTHON_PACKAGES
    ).ask()
    
    # Select CUDA packages
    cuda_selected = questionary.checkbox(
        "Select CUDA packages to download:",
        choices=CUDA_PACKAGES,
        default=CUDA_PACKAGES
    ).ask()
    
    # Select Models
    model_selected = questionary.checkbox(
        "Select HuggingFace models to download:",
        choices=[(f"{name} ({repo})", repo) for repo, name in MODELS.items()],
        default=list(MODELS.keys())
    ).ask()
    
    # Select Projects
    project_selected = questionary.checkbox(
        "Select GitHub projects to clone:",
        choices=[(p['name'], p['name']) for p in SAMPLE_PROJECTS],
        default=[p['name'] for p in SAMPLE_PROJECTS]
    ).ask()
    
    # Ask about retry settings
    retry_count = questionary.select(
        "Max retry attempts for failed downloads:",
        choices=[1, 2, 3, 5],
        default=3
    ).ask()
    
    # Ask about parallel downloads
    parallel = questionary.confirm(
        "Enable parallel downloads (experimental)?",
        default=False
    ).ask()
    
    return {
        'docker': docker_selected,
        'packages': pkg_selected,
        'cuda': cuda_selected,
        'models': model_selected,
        'projects': project_selected,
        'retries': retry_count,
        'parallel': parallel
    }

def modify_installation():
    """Allow modification of ongoing installation"""
    console.print("\n[bold yellow]🔧 MODIFY INSTALLATION[/bold yellow]")
    
    failed_items = state.get_failed_items()
    if failed_items:
        console.print("\n[red]Failed items:[/red]")
        for key, data in failed_items.items():
            console.print(f"  • [red]{key}[/red]: {data['details'][:100]}")
        
        retry = questionary.confirm("Retry failed items?").ask()
        if retry:
            return {'action': 'retry', 'items': list(failed_items.keys())}
    
    show_logs = questionary.confirm("Show recent logs?").ask()
    if show_logs:
        with open(BASE_DIR / "download.log", "r") as f:
            lines = f.readlines()[-20:]
            console.print("\n[cyan]Recent logs:[/cyan]")
            for line in lines:
                console.print(line.strip())
    
    return {'action': 'continue'}

# ======================== ENHANCED UI DASHBOARD ========================
def generate_layout(progress_ui, ascii_art=None, current_task=""):
    """Generates the split live-dashboard with ASCII art integration"""
    
    # Main metrics table
    table = Table(title="📊 Live Installation Summary", box=box.ROUNDED, expand=True)
    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Count", style="magenta", justify="right")
    
    table.add_row("Total Tasks Scheduled", str(metrics["total"]))
    table.add_row("✅ Successfully Completed", f"[bold green]{metrics['completed']}[/bold green]")
    table.add_row("❌ Failed / Skipped", f"[bold red]{metrics['failed']}[/bold red]")
    
    # Failed items list (if any)
    failed_items = state.get_failed_items()
    if failed_items:
        fail_table = Table(box=box.MINIMAL, expand=True)
        fail_table.add_column("Failed Items", style="red")
        for key in list(failed_items.keys())[:5]:
            fail_table.add_row(f"  • {key}")
        if len(failed_items) > 5:
            fail_table.add_row(f"  • ... and {len(failed_items) - 5} more")
    else:
        fail_table = Table(box=box.MINIMAL, expand=True)
        fail_table.add_row("[green]✓ No failures[/green]")
    
    # Current task info
    task_panel = Panel(
        f"[bold yellow]Current Task:[/bold yellow] {current_task}",
        border_style="yellow",
        box=box.ROUNDED
    )
    
    # ASCII art panel
    if ascii_art:
        art_panel = Panel(
            Align.center(ascii_art),
            title="🎨 Infinite ASCII Progress",
            border_style="magenta",
            box=box.HEAVY
        )
        return Group(table, fail_table, task_panel, art_panel, progress_ui)
    else:
        # Progress bar panel (fallback)
        prog_panel = Panel(progress_ui, title="🚀 Download & Build Progress", border_style="blue", box=box.ROUNDED)
        return Group(table, fail_table, task_panel, prog_panel)

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
@click.option('--interactive', is_flag=True, help='Interactive selection of components')
@click.option('--skip-ascii', is_flag=True, help='Skip ASCII art animation')
def main(interactive, skip_ascii):
    # Interactive configuration
    config = {'docker': [img for img, _ in DOCKER_IMAGES], 
              'packages': PYTHON_PACKAGES,
              'cuda': CUDA_PACKAGES,
              'models': list(MODELS.keys()),
              'projects': [p['name'] for p in SAMPLE_PROJECTS],
              'retries': 3,
              'parallel': False}
    
    if interactive:
        config = interactive_selection()
    
    # Update total tasks based on selection
    metrics["total"] = (len(config['docker']) + len(config['packages']) + 
                       len(config['cuda']) + len(config['models']) + len(config['projects']))
    
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
        
        # Check for user modification request (simplified - would need key listener)
        if metrics["failed"] > 3:
            console.print("\n[bold yellow]Multiple failures detected![/bold yellow]")
            if questionary.confirm("Show logs and modify?", default=False).ask():
                modify_installation()

    # Main execution loop
    with Live(generate_layout(progress_ui, ascii_art.get_art() if not skip_ascii else None), 
              refresh_per_second=10, 
              get_renderable=lambda: generate_layout(
                  progress_ui, 
                  ascii_art.get_art() if not skip_ascii else None,
                  str(progress_ui.tasks[current_item_task].description) if current_item_task in progress_ui.tasks else ""
              )):
        
        # Phase 1: Docker
        if config['docker']:
            progress_ui.update(phase_task, description="[bold magenta]Phase 1/5: Docker Images", total=len(config['docker']), completed=0)
            for img in config['docker']:
                execute_with_ui(f"docker_{img}", "Docker", pull_docker, img)
        
        # Phase 2: Python Libs
        if config['packages']:
            progress_ui.update(phase_task, description="[bold magenta]Phase 2/5: Python Libs", total=len(config['packages']), completed=0)
            for pkg in config['packages']:
                execute_with_ui(f"pip_{pkg}", "Python_Libs", download_pip, pkg, cu124=False)
        
        # Phase 3: CUDA
        if config['cuda']:
            progress_ui.update(phase_task, description="[bold magenta]Phase 3/5: CUDA Acceleration", total=len(config['cuda']), completed=0)
            for pkg in config['cuda']:
                execute_with_ui(f"pip_cu124_{pkg}", "Python_Libs_CUDA", download_pip, pkg, cu124=True)
        
        # Phase 4: Models
        if config['models']:
            progress_ui.update(phase_task, description="[bold magenta]Phase 4/5: HuggingFace Models", total=len(config['models']), completed=0)
            for repo in config['models']:
                execute_with_ui(f"model_{repo}", "Models", download_hf_model, repo)
        
        # Phase 5: Projects
        if config['projects']:
            progress_ui.update(phase_task, description="[bold magenta]Phase 5/5: Baking GitHub Projects", total=len(config['projects']), completed=0)
            for proj_name in config['projects']:
                proj = next(p for p in SAMPLE_PROJECTS if p['name'] == proj_name)
                execute_with_ui(f"project_{proj['name']}", "Sample_Projects", setup_project, proj)

        progress_ui.update(current_item_task, description="[bold green]✅ All phases completed!")
        time.sleep(2)  # Let user see completion

    # Cleanup
    if not skip_ascii:
        ascii_art.stop()
    
    generate_report()
    console.print(f"\n[bold green]🎉 Setup Finished![/bold green] Report generated at: {REPORT_FILE}")
    
    # Show final summary
    if metrics['failed'] > 0:
        console.print(f"\n[bold red]⚠️ {metrics['failed']} tasks failed![/bold red]")
        console.print("[yellow]Run with --interactive to retry specific components[/yellow]")

if __name__ == "__main__":
    main()
