# ForgeWrite v0.1.0-rc1 Release Notes

**Date:** 2026-06-16
**Tag:** `v0.1.0-rc1`

---

## Overview

First release candidate of ForgeWrite — a local-first MCP coding service that delegates narrow file edit slices to a local LLM with hard safety rails.

**354 tests. 22 MCP tools. 13 CLI commands. Rust + Python support.**

## What's Included

### Core Pipeline
- 14-state `SliceCoordinator` pipeline: validate → scout → context → generate → schema → semantic → preview → approve → apply → validate → repair
- Schema repair loop (retries on missing fields, wrong types)
- Git snapshot create/restore with TOCTOU re-check
- Hash-bound terminal approval with fcntl file locking
- `LlamaCppClient` with retry + circuit breaker, JSON extraction from reasoning_content

### RAG (Retrieval-Augmented Generation)
- TurboQuantIndex with gte-modernbert-base embeddings (768-dim, 4-bit quantization)
- 1,235 indexed documents: Rust KB, Python KB, rust-by-example, rust-cookbook, Pydantic v2 docs, httpx docs
- Semantic search for model prompt enrichment

### Scout (Evidence Discovery)
- Safe grep via ripgrep with path policy enforcement
- Model-assisted query planning with deterministic fallback
- Evidence summarization (dedup, sort, cap)
- TurboVec RAG retrieval integration

### Saved Work KB
- File-backed JSON store (`.forgerwrite/knowledge/`)
- Knowledge indexer with semantic search (TurboQuantIndex)
- Run promotion: extract patterns from successful slices
- Usage tracking: record helped/did_not_help outcomes
- 5 seed entries from common ForgeWrite patterns

### Language Support
- **Rust:** cargo fmt, check, test, clippy
- **Python:** ruff, pytest, mypy
- LanguageAdapter Protocol for adding new languages

### Integrations
- MEX adapter (fail-soft `.mex/` project memory)
- Graphify adapter (fail-soft codebase graph analysis)
- Headroom adapter (fail-soft, placeholder for future orchestrator)

## Known Limitations

- **Model reliability:** Gemma 4 12B Q4 may omit JSON fields on first attempt; schema repair loop retries up to 2 times
- **Embedding speed:** The gte-modernbert-base model runs on CPU (~2-3 min per 32-document batch during index build)
- **Model-assisted Scout:** Requires the LLM server to be running; defaults to deterministic mode (`use_model_planner=False`)
- **No remote infrastructure:** Kubernetes, Redis, multi-region, Terraform out of scope
- **No daemon mode:** Server runs as a blocking stdio process only
- **MEX integration:** Read-only adapter — does not modify `.mex/` files
- **Package rename:** Python package is `forgerwrite_mcp` (pending future rename to `forgewrite_mcp`)

## Requirements

- Python 3.12+
- llama.cpp server running locally (Gemma 4 12B recommended)
- ripgrep (`rg`) for Scout grep
- Git for snapshot/restore
- 12 GB GPU VRAM recommended (Gemma 4 Q4 ~8GB)
- 32 GB RAM recommended (embedding model uses CPU)

## Upgrade Notes

If upgrading from a pre-release build:
1. Run `uv run forgerwrite build-index` to rebuild the RAG index (now includes Python KB + Pydantic/httpx docs)
2. Run `uv run forgerwrite doctor` to verify the environment
3. Knowledge entries are stored in `.forgerwrite/knowledge/` — no migration needed (new directory)
