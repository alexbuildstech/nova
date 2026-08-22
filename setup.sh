#!/bin/bash
# setup.sh - Environment setup for Nova Animatronic

echo "Setting up Nova environment..."

# Check for GCC
if ! command -v gcc &> /dev/null; then
    echo "Error: gcc not found. Please install build-essential."
    exit 1
fi

# Set CC to ensure evdev and other C extensions build correctly
export CC=gcc

# Install dependencies
echo "Installing requirements..."
pip3 install -r requirements.txt --break-system-packages --user

if [ $? -eq 0 ]; then
    echo "[OK] Setup complete!"
else
    echo "[ERROR] Setup failed."
    exit 1
fi
