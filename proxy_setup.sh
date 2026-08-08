#!/bin/bash
set -e

PROXY_URL="http://192.168.203.2:3128"

echo "⚙️ Setting up system-wide proxy for ${PROXY_URL}..."

# 1. Update Current Shell Environment & persistent ~/.bashrc
export http_proxy="${PROXY_URL}"
export https_proxy="${PROXY_URL}"
export HTTP_PROXY="${PROXY_URL}"
export HTTPS_PROXY="${PROXY_URL}"
export no_proxy="localhost,127.0.0.1,localaddress,.localdomain.com"
export NO_PROXY="localhost,127.0.0.1,localaddress,.localdomain.com"

# Append to ~/.bashrc for future/tmux shells
if ! grep -q "http_proxy=" ~/.bashrc; then
    cat <<EOF >> ~/.bashrc

# Proxy Settings
export http_proxy="${PROXY_URL}"
export https_proxy="${PROXY_URL}"
export HTTP_PROXY="${PROXY_URL}"
export HTTPS_PROXY="${PROXY_URL}"
export no_proxy="localhost,127.0.0.1,localaddress,.localdomain.com"
export NO_PROXY="localhost,127.0.0.1,localaddress,.localdomain.com"
EOF
fi

# 2. Configure APT Proxy
echo "📦 Configuring APT..."
cat <<EOF | sudo tee /etc/apt/apt.conf.d/99proxy
Acquire::http::Proxy "${PROXY_URL}/";
Acquire::https::Proxy "${PROXY_URL}/";
EOF

# 3. Configure Git Proxy
echo "🐙 Configuring Git..."
git config --global http.proxy "${PROXY_URL}"
git config --global https.proxy "${PROXY_URL}"

# 4. Configure Docker Daemon Proxy
echo "🐳 Configuring Docker Daemon..."
sudo mkdir -p /etc/systemd/system/docker.service.d
cat <<EOF | sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=${PROXY_URL}"
Environment="HTTPS_PROXY=${PROXY_URL}"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF

# Restart Docker service if Docker is installed
if command -v docker &> /dev/null; then
    sudo systemctl daemon-reload
    sudo systemctl restart docker
fi

echo "✅ Proxy successfully set across Ubuntu Shell, APT, Git, and Docker!"