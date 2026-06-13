---
name: architecture
description: How the major pieces of this project connect and flow. Load when working on system design, integrations, or understanding how components interact.
triggers:
  - "architecture"
  - "system design"
  - "how does X connect to Y"
  - "integration"
  - "flow"
edges:
  - target: context/stack.md
    condition: when specific technology details are needed
  - target: context/decisions.md
    condition: when understanding why the architecture is structured this way
last_updated: 2026-06-13
---

# Architecture

## System Overview
Cloud orchestrator (Claude/GPT) sends a handoff + slice contract via MCP over stdio → `SliceCoordinator` runs 14-state pipeline: validates contracts against JSON Schema Draft 2020-12 → builds bounded context packet from allowed files only → optionally enriches prompt with RAG knowledge (gte-modernbert-base semantic search over curated Rust KB) → invokes local LLM (llama.cpp via HTTP, Gemma 4 12B Q4) via json_object response format to generate JSON operation batch → schema-validates + semantically validates operations (retries on missing fields via schema repair loop) → creates git snapshot, applies ops, generates preview diff → user reviews diff via CLI and writes hash-bound approval record → applies ops atomically with TOCTOU re-check → runs allowlisted validation commands (cargo fmt/check/test/clippy) with SIGTERM/SIGKILL signals → on failure, enters bounded repair loop which re-invokes model with validation errors → all artifacts written to `.forgerwrite/runs/<run_id>/` as JSON + Markdown.

## Key Components
- **SliceCoordinator** (`coordinator.py`) — owns the 14-state machine. No MCP or CLI knowledge. Delegates to context, local model, validation, repair, and RAG modules.
- **RAG Pipeline** (`rag/`) — 5 modules: DocumentPreprocessor (splits markdown on ###/# boundaries), RagIndex (TurboQuantIndex + gte-modernbert-base 768-dim embeddings), RagRetriever (turbovec semantic search), RagPromptEnricher (injects `--- RELEVANT KNOWLEDGE ---` with token budget), factory functions (`build_rag_enricher`, `build_rag_index`). 26 curated KB documents across 7 sections; external support for rust-cookbook (285) and rust-by-example (198). Index persists as turbovec file.
- **ContractRegistry** (`contracts/registry.py`) — loads and caches JSON schemas; validates using Draft 2020-12. Schemas live in `schemas/`.
- **OperationRegistry** (`operations/registry.py`) — Open/Closed dispatch: `OperationHandler` Protocol with 6 handlers. New ops are added by registering, not editing a switch.
- **Forge Safety Layer** (`forge/`) — git snapshot create/cleanup/restore; worktree cleanliness check (ADR-004); preview diff generation; TOCTOU-guarded apply.
- **Validation Runner** (`validation/runner.py`) — runs allowlisted command IDs with `shell=False`, SIGTERM→SIGKILL with configurable grace period.
- **Semantic Validator** (`validation/semantic.py`) — 5 pluggable rules: scope, size, forbidden targets, generated paths, permissions.
- **Repair Coordinator** (`repair.py`) — bounded repair budget, builds feedback prompt from validation errors. Also handles schema-level repair (missing required fields) via `_generate_with_schema_repair` in coordinator.
- **MCP Server** (`server.py`) — FastMCP over stdio; 10 thin tools; stdout→stderr redirect at boot; all errors through `envelope_from()`. RAG enrichment in `fw_generate_operations_local`.
- **CLI** (`cli.py`) — Typer app with 13 commands; `--json` flag on all; Rich syntax highlighting; interactive approve with `typer.confirm`. Includes `build-index` command.
- **Approval Store** (`approval.py`) — hash-bound approval record with SHA256 of preview diff; fcntl file locking; TOCTOU re-check.
- **Config** (`config.py`) — Pydantic v2 models for 8 sections (rag added); `load_config()` from `.forgerwrite/forgerwrite.toml`. Config default `max_tokens` raised to 4096 for json_object output.
- **Dead Letter + Audit** (`dead_letter.py`, `audit.py`) — centralized unrecoverable failure records and JSONL audit event log.
- **Summary** (`summary.py`) — reads all run artifacts, produces Markdown summary with dead letter alerts, artifact table, audit trail.

## External Dependencies
- **llama.cpp server** — local HTTP endpoint at `127.0.0.1:8080/v1`; must be launched externally (MVP). Gemma 4 12B QAT (Q4_K_XL) on CUDA recommended. json_object response format.
- **TurboQuantIndex** (turbovec 0.7.0) — Rust vector index with Python bindings, 16x compression, for RAG document search.
- **gte-modernbert-base** (sentence-transformers) — 149M param embedding model, 768-dim vectors, 8192 token context, for RAG.
- **Git** — worktree checks, snapshot create/restore via `refs/forgerwrite/<run_id>`; `git update-ref`, `git read-tree`, `git checkout-index`, `git clean`.
- **Cargo/Rustup** — validation commands run `cargo fmt -- --check`, `cargo check`, `cargo test`, `cargo clippy`.

## What Does NOT Exist Here
- No SQLite index — JSON + Markdown artifacts are the source of truth (ADR-005); SQLite added in mature beta as queryable index only
- No remote infrastructure — Kubernetes, Redis, multi-region, Terraform explicitly out of scope (ADR-006)
- No unified diff operations — disabled by default (`allow_unified_diff_fallback: false`); enabled per-slice in mature beta (ADR-003)
- No daemon mode or HTTP control API — mature beta feature
- No Rust harness — Python MCP first; safety-critical mutation extracted to Rust in mature beta (ADR-001)
