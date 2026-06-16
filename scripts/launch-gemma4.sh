#!/usr/bin/env bash
# Launch Gemma 4 12B (QAT Q4_K_XL) via llama.cpp for ForgeWrite.
# Prerequisites: llama.cpp built with CUDA, model file at the expected path.
#
# Usage: bash scripts/launch-gemma4.sh
# The server starts at http://localhost:8080 by default.
#
# After launch, verify with: curl http://localhost:8080/v1/models

set -euo pipefail

MODEL="gemma-4-12b-qat-Q4_K_XL.gguf"
CTX_SIZE=8192
NGPU=35
PORT=8080

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_PATH="${HOME}/models/${MODEL}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model not found at ${MODEL_PATH}"
    echo "Download from: https://huggingface.co/bartowski/gemma-4-12b-qat-Q4_K_XL-GGUF"
    exit 1
fi

exec llama-server \
    --model "${MODEL_PATH}" \
    --ctx-size ${CTX_SIZE} \
    --ngl ${NGPU} \
    --port ${PORT} \
    --host 0.0.0.0 \
    "$@"
