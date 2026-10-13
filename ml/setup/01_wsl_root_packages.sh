#!/usr/bin/env bash
# System packages needed in WSL for training and GGUF export (compilers for Triton/llama.cpp).
# Run as root:  wsl -d Ubuntu -u root -- bash ml/setup/01_wsl_root_packages.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  build-essential cmake git curl ca-certificates unzip pkg-config libcurl4-openssl-dev

echo "[01] root packages OK"
