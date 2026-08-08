#!/bin/bash
set -e

echo "🚀 [1/3] Bootstrapping Vanilla Ubuntu OS..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tmux curl git wget build-essential jq libgl1 libglib2.0-0

if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
fi

echo "🐍 [2/3] Preparing Master Virtual Environment..."
if [ ! -d "prep_venv" ]; then
    python3 -m venv prep_venv
fi
source prep_venv/bin/activate
pip install --upgrade pip

# Install the dependencies required for the Python Orchestrator
pip install rich click huggingface-hub questionary uv packaging

echo "🛡️ [3/3] Launching Self-Healing Downloader in Tmux..."
SESSION_NAME="offline_prep"

if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    # Launch in tmux so you can disconnect and the download continues
    tmux new-session -d -s "$SESSION_NAME" "bash -c 'source prep_venv/bin/activate && python3 offline_prepare_cli.py; exec bash'"
    echo "✅ Started tmux session '$SESSION_NAME'."
    echo "👉 ATTACH WITH: tmux attach -t $SESSION_NAME"
    echo "👉 DETACH WITH: Ctrl+b, then d"
else
    echo "⚠️ Session '$SESSION_NAME' already exists. Attach with: tmux attach -t $SESSION_NAME"
fi
