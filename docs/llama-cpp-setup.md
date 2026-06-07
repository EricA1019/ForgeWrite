# Llama.cpp Setup for ForgerWrite MCP

ForgerWrite requires a running **llama.cpp server** with the **OmniCoder 9B** model (Q8 quantization or better).

---

## 1. Install llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
mkdir build && cd build
cmake .. -DLLAMA_CUDA=OFF  # CPU-only; add -DLLAMA_CUDA=ON for NVIDIA GPU
cmake --build . --config Release -j$(nproc)
```

---

## 2. Download OmniCoder 9B

Download from Hugging Face:

```bash
# GGUF format (Q8_0 quantization recommended)
huggingface-cli download \
    nisten/omnicoder-9b-q8_0-GGUF \
    omnicoder-9b-q8_0.gguf \
    --local-dir ./models/
```

Or manually from: <https://huggingface.co/nisten/omnicoder-9b-q8_0-GGUF>

---

## 3. Launch the Server

```bash
./build/bin/llama-server \
    --model ./models/omnicoder-9b-q8_0.gguf \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 8192 \
    --batch-size 512 \
    --threads $(nproc) \
    --gpu-layers 0 \
    --no-mmap
```

For GPU offload (NVIDIA), add:
```bash
    --gpu-layers 35 \
    --no-mmap
```

---

## 4. Verify the Server

```bash
curl http://127.0.0.1:8080/health
# → {"status": "ok"}

curl http://127.0.0.1:8080/v1/models
# → {"object": "list", "data": [{"id": "omnicoder-9b", ...}]}
```

---

## 5. Test JSON Schema Compliance

ForgerWrite's Phase 0 spike validated that OmniCoder 9B with Q8 quantization reliably produces valid JSON matching Draft 2020-12 schemas. Run a quick smoke test:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "omnicoder-9b",
        "messages": [
            {"role": "system", "content": "You are a coding assistant. Output valid JSON only."},
            {"role": "user", "content": "Create a file called hello.rs with a main function that prints Hello, world!"}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }'
```

---

## 6. Configure ForgerWrite

Set the endpoint in `.forgerwrite/forgerwrite.toml`:

```toml
[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "omnicoder-9b"
temperature = 0.20
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
