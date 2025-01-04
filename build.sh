#!/bin/bash

# Install dependencies if not already installed
if ! command -v fpm &> /dev/null; then
    echo "Installing FPM..."
    sudo apt-get update
    sudo apt-get install -y ruby ruby-dev rubygems build-essential
    sudo gem install --no-document fpm
fi

# Install system dependencies
sudo apt-get install -y \
    libunwind-dev \
    libxcb-xinerama0 \
    libxcb-cursor0

# Install Python dependencies
pip install -r requirements.txt
pip install pyinstaller==5.13.2

# Build binaries
PYTHONPATH=$PWD pyinstaller -s -F --hidden-import=ctypes --collect-all scapy server/tuxcutd.py
PYTHONPATH=$PWD pyinstaller -s -F --hidden-import=ctypes --collect-all dearpygui client/tuxcut.py

# Prepare package files
rm -rf pkg/opt/tuxcut/*
mkdir -p pkg/opt/tuxcut/
mv dist/tuxcut pkg/opt/tuxcut/
mv dist/tuxcutd pkg/opt/tuxcut/

# Get version
VERSION=$(date +'%Y.%m.%d')
if [ -n "$GITHUB_REF" ] && [[ $GITHUB_REF == refs/tags/* ]]; then
    VERSION=${GITHUB_REF#refs/tags/v}
fi

# Build DEB package
fpm -s dir -t deb \
    -n tuxcut \
    -v $VERSION \
    --iteration 1 \
    -d "libpcap0.8" \
    -d "arptables" \
    -d "dnsutils" \
    -d "net-tools" \
    -d "libxcb-xinerama0" \
    -d "libxcb-cursor0" \
    -C pkg

# Build RPM package
fpm -s dir -t rpm \
    -n tuxcut \
    -v $VERSION \
    --iteration 1 \
    -d "libpcap" \
    -d "arptables" \
    -d "bind-utils" \
    -d "net-tools" \
    -d "libxcb-xinerama0" \
    -d "libxcb-cursor0" \
    -C pkg

echo "Build complete! Check the .deb and .rpm files in the current directory."
