#!/bin/bash
set -e

# --- PROXY CONFIGURATION ---
export PROXY_URL="http://192.168.203.2:3128"
export http_proxy="$PROXY_URL"
export https_proxy="$PROXY_URL"
export HTTP_PROXY="$PROXY_URL"
export HTTPS_PROXY="$PROXY_URL"
export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"

echo "🚀 [1/3] Bootstrapping Vanilla Ubuntu OS behind Squid Proxy..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tmux curl git wget build-essential jq libgl1 libglib2.0-0

if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    
    # Configure docker proxy after fresh install
    sudo mkdir -p /etc/systemd/system/docker.service.d
    cat <<EOF | sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=${PROXY_URL}"
Environment="HTTPS_PROXY=${PROXY_URL}"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
    sudo systemctl daemon-reload
    sudo systemctl restart docker
fi

echo "🐍 [2/3] Preparing Master Virtual Environment..."
if [ ! -d "prep_venv" ]; then
    python3 -m venv prep_venv
fi
source prep_venv/bin/activate
pip install --upgrade pip

pip install rich click huggingface-hub questionary uv packaging

echo "🛡️ [3/3] Launching Self-Healing Downloader in Tmux..."
SESSION_NAME="offline_prep"

if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    # Pass proxy variables explicitly into tmux
    tmux new-session -d -s "$SESSION_NAME" "bash -c '
        export http_proxy=\"$PROXY_URL\";
        export https_proxy=\"$PROXY_URL\";
        export HTTP_PROXY=\"$PROXY_URL\";
        export HTTPS_PROXY=\"$PROXY_URL\";
        source prep_venv/bin/activate && python3 offline_prepare_cli.py; 
        exec bash'"
    echo "✅ Started tmux session '$SESSION_NAME'."
    echo "👉 ATTACH WITH: tmux attach -t $SESSION_NAME"
    echo "👉 DETACH WITH: Ctrl+b, then d"
else
    echo "⚠️ Session '$SESSION_NAME' already exists. Attach with: tmux attach -t $SESSION_NAME"
fi