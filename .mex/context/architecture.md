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
last_updated: 2026-06-07
---

# Architecture

## System Overview
Cloud orchestrator (Claude/GPT) sends a handoff + slice contract via MCP over stdio → `SliceCoordinator` runs 14-state pipeline: validates contracts against JSON Schema Draft 2020-12 → builds bounded context packet from allowed files only → invokes local LLM (llama.cpp via HTTP) to generate JSON operation batch → schema-validates + semantically validates operations → creates git snapshot, applies ops, generates preview diff → user reviews diff via CLI and writes hash-bound approval record → applies ops atomically with TOCTOU re-check → runs allowlisted validation commands (cargo fmt/check/test/clippy) with SIGTERM/SIGKILL signals → on failure, enters bounded repair loop → all artifacts written to `.forgerwrite/runs/<run_id>/` as JSON + Markdown.

## Key Components
- **SliceCoordinator** (`coordinator.py`) — owns the 14-state machine. No MCP or CLI knowledge. Delegates to context, local model, validation, and repair modules.
- **ContractRegistry** (`contracts/registry.py`) — loads and caches JSON schemas; validates using Draft 2020-12. Schemas live in `schemas/`.
- **OperationRegistry** (`operations/registry.py`) — Open/Closed dispatch: `OperationHandler` Protocol with 6 handlers. New ops are added by registering, not editing a switch.
- **Forge Safety Layer** (`forge/`) — git snapshot create/cleanup/restore; worktree cleanliness check (ADR-004); preview diff generation; TOCTOU-guarded apply.
- **Validation Runner** (`validation/runner.py`) — runs allowlisted command IDs with `shell=False`, SIGTERM→SIGKILL with configurable grace period.
- **Semantic Validator** (`validation/semantic.py`) — 5 pluggable rules: scope, size, forbidden targets, generated paths, permissions.
- **Repair Coordinator** (`repair.py`) — bounded repair budget, builds feedback prompt from validation errors. Currently stub — does not re-invoke model.
- **MCP Server** (`server.py`) — FastMCP over stdio; 10 thin tools; stdout→stderr redirect at boot; all errors through `envelope_from()`.
- **CLI** (`cli.py`) — Typer app with 12 commands; `--json` flag on all; Rich syntax highlighting; interactive approve with `typer.confirm`.
- **Approval Store** (`approval.py`) — hash-bound approval record with SHA256 of preview diff; fcntl file locking; TOCTOU re-check.
- **Config** (`config.py`) — Pydantic v2 models for 7 sections; `load_config()` from `.forgerwrite/forgerwrite.toml`.
- **Dead Letter + Audit** (`dead_letter.py`, `audit.py`) — centralized unrecoverable failure records and JSONL audit event log.
- **Summary** (`summary.py`) — reads all run artifacts, produces Markdown summary with dead letter alerts, artifact table, audit trail.

## External Dependencies
- **llama.cpp server** — local HTTP endpoint at `127.0.0.1:8080/v1`; must be launched externally (MVP). OmniCoder 9B Q8 required.
- **Git** — worktree checks, snapshot create/restore via `refs/forgerwrite/<run_id>`; `git update-ref`, `git read-tree`, `git checkout-index`, `git clean`.
- **Cargo/Rustup** — validation commands run `cargo fmt -- --check`, `cargo check`, `cargo test`, `cargo clippy`.

## What Does NOT Exist Here
- No SQLite index — JSON + Markdown artifacts are the source of truth (ADR-005); SQLite added in mature beta as queryable index only
- No remote infrastructure — Kubernetes, Redis, multi-region, Terraform explicitly out of scope (ADR-006)
- No unified diff operations — disabled by default (`allow_unified_diff_fallback: false`); enabled per-slice in mature beta (ADR-003)
- No daemon mode or HTTP control API — mature beta feature
- No Rust harness — Python MCP first; safety-critical mutation extracted to Rust in mature beta (ADR-001)
