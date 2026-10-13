#!/usr/bin/env bash
# Pre-builds the llama.cpp tools Unsloth uses for GGUF export (CPU build is enough for quantizing).
# Run as your normal WSL user after 01:  wsl -d Ubuntu -- bash ml/setup/04_build_llamacpp.sh
set -euo pipefail

ML_HOME="${ML_HOME:-$HOME/indusmind-ml}"
mkdir -p "$ML_HOME"
cd "$ML_HOME"

[ -d llama.cpp ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=OFF
cmake --build build --config Release -j 8 --target llama-quantize llama-gguf-split llama-cli
# Unsloth looks for the binaries in the llama.cpp root as well as build/bin.
cp build/bin/llama-quantize build/bin/llama-gguf-split build/bin/llama-cli .

./llama-quantize --help >/dev/null 2>&1 || true
echo "[04] llama.cpp OK -> $ML_HOME/llama.cpp (commit $(git rev-parse --short HEAD))"
