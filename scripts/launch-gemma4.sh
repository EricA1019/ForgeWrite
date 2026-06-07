#!/usr/bin/env bash
# Launch Gemma 4 12B QAT on CUDA GPU (RTX 3060 12GB)
# Model: unsloth/gemma-4-12B-it-qat-UD-Q4_K_XL (~6.7 GB)

set -euo pipefail

readonly LLAMA_SERVER="/home/eric/servers/llama.cpp-cuda-b8680-sm86/bin/llama-server"
readonly LLAMA_BIN_DIR="/home/eric/servers/llama.cpp-cuda-b8680-sm86/bin"
readonly MODEL_PATH="/home/eric/models/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
readonly CUDA_LIBS="/home/eric/miniconda3/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:/home/eric/miniconda3/lib/python3.12/site-packages/nvidia/cublas/lib"

readonly HOST="127.0.0.1"
readonly PORT="8080"
readonly N_GPU_LAYERS="999"
readonly CONTEXT_SIZE="32768"
readonly BATCH_SIZE="2048"
readonly FLASH_ATTN="1"

export LD_LIBRARY_PATH="${LLAMA_BIN_DIR}:${CUDA_LIBS}:${LD_LIBRARY_PATH:-}"

echo "Launching Gemma 4 12B (CUDA) on ${HOST}:${PORT}..."
echo "Model: ${MODEL_PATH}"
echo "Context: ${CONTEXT_SIZE}"
echo ""

exec "${LLAMA_SERVER}" \
    --model "${MODEL_PATH}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --n-gpu-layers "${N_GPU_LAYERS}" \
    --ctx-size "${CONTEXT_SIZE}" \
    --batch-size "${BATCH_SIZE}" \
    --flash-attn "${FLASH_ATTN}" \
    --mlock \
    --no-mmap \
    "$@"
