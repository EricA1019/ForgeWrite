# Llama.cpp Setup for ForgerWrite MCP

ForgerWrite uses a local llama.cpp server. The default model is **OmniCoder 9B** (Q8_0). A **Gemma 4 12B QAT** configuration is also available and will be tested further at MVP.

---

## 1. Install llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
mkdir build && cd build
cmake .. -DLLAMA_CUDA=ON -DLLAMA_CUDA_F16=ON  # CPU-only: -DLLAMA_CUDA=OFF
cmake --build . --config Release -j$(nproc)
```

---

## 2. OmniCoder 9B (Default)

```bash
# Download
huggingface-cli download \
    nisten/omnicoder-9b-q8_0-GGUF \
    omnicoder-9b-q8_0.gguf \
    --local-dir ./models/

# Launch (CPU or partial GPU)
./build/bin/llama-server \
    --model ./models/omnicoder-9b-q8_0.gguf \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 8192 \
    --batch-size 512 \
    --threads $(nproc) \
    --gpu-layers 0
```

For GPU offload (NVIDIA), add `--gpu-layers 35 --no-mmap`.

---

## 3. Gemma 4 12B QAT (Experimental — MVP Testing)

```bash
# Download
export MODEL_PATH=/path/to/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf

# Launch (CUDA, 32K context, flash attention)
./build/bin/llama-server \
    --model "$MODEL_PATH" \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 32768 \
    --batch-size 2048 \
    --ubatch-size 512 \
    --n-gpu-layers 49 \
    --flash-attn 1 \
    --no-mmap
```

A launch script for RTX 3060 is at `scripts/launch-gemma4.sh`.

---

## 4. Verify & Smoke Test

```bash
curl http://127.0.0.1:8080/health
# → {"status": "ok"}

# Smoke test with your model
curl http://127.0.0.1:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "<your-model-name>",
        "messages": [
            {"role": "user", "content": "{\"test\": \"hello\"}"}
        ],
        "temperature": 0.2,
        "max_tokens": 256,
        "response_format": {"type": "json_object"}
    }'
```

---

## 5. Configure ForgerWrite

Set the endpoint in `.forgerwrite/forgerwrite.toml`. Default config is for OmniCoder:

```toml
[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "omnicoder-9b"
temperature = 0.20
top_p = 0.90
top_k = 20
max_tokens = 4096
```

For Gemma 4, update to temperature=1.0, top_p=0.95, top_k=64, max_tokens=4096.

Run `uv run forgerwrite doctor` to confirm the connection.

---

## Requirements Summary

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| llama.cpp | latest `master` | latest `master` |
| OmniCoder 9B | Q8_0 quantization | Q8_0 |
| Gemma 4 12B QAT | Q4_K_XL, CUDA GPU 12GB+ | Q4_K_XL, RTX 3060+ |
| RAM | 12 GB | 16 GB |
| VRAM (GPU) | 8 GB | 12 GB |
| Context size | 4096 | 8192 |

---

## Troubleshooting

### "Connection refused"
The llama.cpp server isn't running or is on a different port. Check with `curl http://127.0.0.1:8080/health`.

### "Invalid JSON response from model"
- Ensure `temperature` is set to 0.2 or lower in `forgerwrite.toml`.
- Verify the model is OmniCoder 9B, not a different model.
- Check `response_format: {"type": "json_object"}` is set in the request.
- The Phase 0 spike found Q4 quantization produces malformed JSON ~15% of the time — use Q8 or better.

### "Out of memory"
- Reduce `ctx-size` to 4096.
- Use `--no-mmap` to avoid memory-mapping the full model file.
- If using GPU, reduce `--gpu-layers` or set to 0 for CPU-only.
