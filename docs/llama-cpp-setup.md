# Llama.cpp Setup for ForgerWrite MCP

ForgerWrite is tested with **Gemma 4 12B QAT** (Q4_K_XL GGUF) on an NVIDIA RTX 3060. A `launch-gemma4.sh` script is provided in `scripts/` for the exact build + launch.

---

## 1. Quick Launch (RTX 3060)

```bash
bash scripts/launch-gemma4.sh
```

This builds llama.cpp with CUDA and launches the server with the correct flags.

---

## 2. Manual Launch

```bash
# Build llama.cpp with CUDA support
cd /path/to/llama.cpp
mkdir build && cd build
cmake .. -DLLAMA_CUDA=ON -DLLAMA_CUDA_F16=ON
cmake --build . --config Release -j$(nproc)

# Download Gemma 4 12B QAT
export MODEL=/home/eric/models/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf

# Launch server (CUDA, 32K context, flash attention)
./build/bin/llama-server \
    --model "$MODEL" \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 32768 \
    --batch-size 2048 \
    --ubatch-size 512 \
    --n-gpu-layers 49 \
    --flash-attn 1 \
    --no-mmap
```

---

## 3. Verify the Server

```bash
curl http://127.0.0.1:8080/health
# → {"status": "ok"}
```

---

## 4. Smoke Test

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "gemma-4-12B-it-qat-UD-Q4_K_XL",
        "messages": [
            {"role": "user", "content": "Fix the import in this file: use calc_lib::add;"}
        ],
        "temperature": 1.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"}
    }'
```

---

## 5. Configure ForgerWrite

Set the endpoint in `.forgerwrite/forgerwrite.toml`:

```toml
[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "gemma-4-12B-it-qat-UD-Q4_K_XL"
temperature = 1.0
top_p = 0.95
top_k = 64
max_tokens = 4096
```

Run `forgerwrite doctor` to confirm the connection:

```bash
uv run forgerwrite doctor
# → {"ok": true, "checks": {"config_exists": true, "llama_cpp_reachable": true, ...}}
```

---

## Requirements Summary

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| llama.cpp | latest `master` | latest `master` |
| OmniCoder 9B | Q8_0 quantization | Q8_0 |
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
