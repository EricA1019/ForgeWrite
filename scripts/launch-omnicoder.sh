#!/usr/bin/env bash
# Launch OmniCoder 9B (Q8) via llama.cpp for ForgeWrite.
# Alternative to Gemma 4 for systems with less VRAM.
#
# Usage: bash scripts/launch-omnicoder.sh
# The server starts at http://localhost:8080 by default.

set -euo pipefail

MODEL="omnicoder-9b-q8.gguf"
CTX_SIZE=4096
NGPU=28
PORT=8080

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_PATH="${HOME}/models/${MODEL}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model not found at ${MODEL_PATH}"
    echo "Available models: omnicoder-9b, gemma-4-12b"
    exit 1
fi

exec llama-server \
    --model "${MODEL_PATH}" \
    --ctx-size ${CTX_SIZE} \
    --ngl ${NGPU} \
    --port ${PORT} \
    --host 0.0.0.0 \
    "$@"
