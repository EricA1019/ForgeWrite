#!/bin/bash
# Launch OmniCoder 9B Q8_0 on GPU (RTX 3060, CUDA 12)
# Usage: ./launch-omnicoder.sh

set -euo pipefail

BIN_DIR="/home/eric/servers/llama.cpp-cuda-b8680-sm86/bin"
MODEL="/home/eric/models/OmniCoder-9B-Claude-Opus-High-Reasoning-Distill.Q8_0.gguf"

# Collect CUDA 12 libraries from nvidia pip packages
CUDA_LIBS=$(find /home/eric/miniconda3/lib/python3.12/site-packages/nvidia \
    -name "lib" -type d 2>/dev/null | tr '\n' ':')

export LD_LIBRARY_PATH="${BIN_DIR}:${CUDA_LIBS}"

exec "${BIN_DIR}/llama-server" \
    --model "${MODEL}" \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 8192 \
    --batch-size 512 \
    --n-gpu-layers 35 \
    --threads 8 \
    --no-mmap
