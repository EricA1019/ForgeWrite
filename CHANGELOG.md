# Changelog

All notable changes to ForgeWrite are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-16

### Added
- FastMCP stdio server with 22 tools for file operations, scout, knowledge base, and diagnostics
- Local LLM integration via llama.cpp HTTP API with retry, circuit breaker, and JSON repair loop
- Six file operation handlers: create_file, replace_file, delete_file, insert_before_line, insert_after_line, replace_line_range
- Scout evidence system with model-assisted grep query planning and deterministic fallback
- Saved Work Knowledge Base with semantic search (gte-modernbert-base embeddings), promotion from runs, and usage tracking
- TurboQuantIndex 4-bit compressed vector search for the KB
- Schema + semantic validation pipeline with TOCTOU snapshot guard on apply
- Contract registry with JSON Schema Draft 2020-12 validation (9 schemas)
- Operation batch approval with hash-based snapshots
- Token usage tracker with by-model and by-purpose breakdowns
- Audit log system for runs, with analyzer for Markdown/JSON reports
- Textual TUI dashboard (tokens, runs, KB, model health)
- CLI with 12 commands: init, doctor, approve, approve-batch, ping, scout, generate, validate, apply, token-stats, audit-report, model-status, tui
- Model state persistence and health check (llama.cpp server detection)
- Fail-soft integration adapters for MEX, Graphify, and Headroom
- Python adapter: ruff, pytest, mypy validation profiles
- Rust adapter: cargo fmt, check, test, clippy validation profiles
- Dead letter queue for operation audit
- Context packet builder with file exclusion and SHA-256 hashing
- Repair loop for malformed LLM JSON output (configurable retries)
- Stress test script covering 6 subsystems
- 354 tests (pytest), ruff linting clean
- GitHub Actions CI: lint, typecheck, test, security-audit, trivy

### Security
- TOCTOU guard: git snapshot at preview time checked at apply time
- Validation before every write operation
- Allowed-files path boundary enforcement
- Content size cap (200KB per create_file operation)

[0.1.0]: https://github.com/EricA1019/ForgeWrite/releases/tag/v0.1.0
