#!/bin/bash
# fix_environment.sh - Fix Python environment for H200 setup

# Set proxy
export HTTP_PROXY="http://192.168.203.2:3128"
export HTTPS_PROXY="http://192.168.203.2:3128"
export http_proxy="http://192.168.203.2:3128"
export https_proxy="http://192.168.203.2:3128"

echo "🔧 Fixing Python environment..."

# Remove broken venv
if [ -d "prep_venv" ]; then
    echo "Removing broken virtual environment..."
    rm -rf prep_venv
fi

# Create new venv
echo "Creating new virtual environment..."
python3 -m venv prep_venv

# Activate and install packages
echo "Activating virtual environment and installing packages..."
source prep_venv/bin/activate

# Upgrade pip first
pip install --upgrade pip --proxy http://192.168.203.2:3128

# Install core packages
echo "Installing huggingface_hub..."
pip install huggingface_hub --proxy http://192.168.203.2:3128

echo "Installing huggingface_hub[cli]..."
pip install "huggingface_hub[cli]" --proxy http://192.168.203.2:3128

echo "Installing transformers..."
pip install transformers --proxy http://192.168.203.2:3128

echo "Installing accelerate..."
pip install accelerate --proxy http://192.168.203.2:3128

# Verify installations
echo -e "\n📋 Verification:"
python -c "import huggingface_hub; print('✅ huggingface_hub installed: v' + huggingface_hub.__version__)"
huggingface-cli --version 2>/dev/null && echo "✅ huggingface-cli installed"

echo -e "\n✨ Environment ready!"
echo "To activate: source prep_venv/bin/activate"
echo "Proxy set to: http://192.168.203.2:3128"
