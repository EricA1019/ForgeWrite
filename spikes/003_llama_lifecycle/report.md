# Spike C — llama.cpp Server Lifecycle

**Date:** 2026-06-07 (retrospective)
**Status:** GO
**ADR:** ADR-007

---

## Question

What is the exact launch command, cold-start time, memory footprint, and
failure mode of llama.cpp with OmniCoder 9B on the target machine?

## Launch Command

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

## Baseline Numbers

| Metric | Value |
|--------|-------|
| Cold-start time | ~8-15 seconds (model dependent) |
| Resident memory (Q8_0) | ~10-12 GB |
| Context size | 8192 tokens |
| Tokens/sec (CPU, 16 threads) | ~8-12 tok/s (estimated) |
| Tokens/sec (GPU, 35 layers) | ~25-40 tok/s (estimated) |

## Health Check

```bash
curl http://127.0.0.1:8080/health
# → {"status": "ok"}
```

## Failure Modes

| Mode | Symptom | Mitigation |
|------|---------|------------|
| OOM | Server crashes | Reduce `--ctx-size` or use smaller quant |
| Port conflict | `Address already in use` | Change `--port` |
| Model not found | Server exits immediately | Check `--model` path |

## Decision: GO

The launch command is documented in `docs/llama-cpp-setup.md`. The ForgerWrite
doctor command checks llama.cpp reachability via `/health` endpoint.

## Implementation Notes

- MVP assumes llama.cpp is externally launched (not managed by ForgerWrite)
- Mature beta may add supervised launch + health probes
- `LlamaCppClient` uses configurable endpoint + retry with backoff
