# ForgeWrite MCP — Project State

**Date:** 2026-06-23
**Branch:** `main`
**Phase:** 7 complete — Integrations + RC + Hardening
**Status:** v0.1.0-rc1 tagged, rc2 hardening in progress
**Full plan:** `docs/implementation-plan.md`

---

## Architecture Overview

```
forgerwrite_mcp/
├── artifacts.py          # Run ID generation + centralized artifact I/O
├── approval.py           # Hash-bound, TOCTOU-safe terminal approval + audit
├── audit.py              # JSONL audit event log per run
├── audit_analyzer.py     # Audit log analysis for Markdown/JSON reports
├── cli.py                # Typer CLI — 16 commands, --json flag
├── config.py             # Pydantic models for 8 config sections (project, local_model,
│                         #   limits, validation, permissions, hygiene, repair, rag)
├── context.py            # Context packet builder (per-file + total limits, SHA256)
├── coordinator.py        # SliceCoordinator — 14-state machine, zero stubs
├── dead_letter.py        # Centralized dead letter writer
├── doctor.py             # Shared doctor checks (config, git, llama.cpp, RAG)
├── errors.py             # PublicError, ErrorEnvelope, 10 error code constants
├── llama_client.py       # HTTP client for llama.cpp (retry + circuit breaker)
├── local_model.py        # LocalModelBackend Protocol + FakeLocalModelBackend
├── model_state.py        # Model state persistence for dashboards
├── paths.py              # safe_resolve_path (DRY path safety)
├── repair.py             # RepairCoordinator — bounded budget, feedback prompt
├── server.py             # FastMCP server — 22 MCP tools, stdio transport
├── summary.py            # Markdown run summary generator
├── token_tracker.py      # Token usage tracker (by-model, by-purpose)
├── tui.py                # Textual TUI dashboard
├── contracts/            # JSON Schema loading + Draft 2020-12 validation
├── forge/                # Git snapshot/diff/restore utilities
├── integrations/         # Fail-soft adapters: MEX, Graphify, Headroom
├── knowledge/            # Saved Work Knowledge Base (store, indexer, promotion)
├── languages/            # LanguageAdapter protocol + Rust/Python implementations
├── operations/           # 6 file operation handlers (create, replace, delete, insert)
├── rag/                  # RAG subsystem (indexer, retriever, enricher, preprocessor)
├── scout/                # Scout evidence discovery (coordinator, safe_grep)
└── validation/           # CI validation runner + semantic rules

schemas/   (9 JSON Schema Draft 2020-12 files)
tests/     (~40 test files, 358 tests)
docs/      (project-state.md, implementation-plan.md, adr/, acceptance/, handoff/, patterns/)
.github/   (CI workflow: lint, typecheck, test, security-audit, trivy)
.vscode/   (mcp.json for VS Code MCP integration)
```

## Module Inventory

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `artifacts.py` | 107 | Run ID generation, run directory creation, artifact read/write |
| `errors.py` | 96 | `PublicError`, `ErrorEnvelope`, `envelope_from()`, 10 error codes |
| `config.py` | 144 | `ForgerWriteConfig` + 7 Pydantic section models, `load_config()` |
| `paths.py` | 67 | `safe_resolve_path()`, `assert_inside_repo()` |
| `dead_letter.py` | 33 | `write_dead_letter()` — centralized, shared by coordinator+CLI |
| `audit.py` | 35 | `write_audit_event()` — JSONL append, used by coordinator+approval+CLI |
| `summary.py` | 98 | `generate_summary()` — Markdown summary from artifact dir |
| `contracts/registry.py` | 66 | `ContractRegistry` — schema loading, caching, Draft 2020-12 validation |
| `forge/git_utils.py` | 99 | `assert_clean_worktree()`, snapshot create/cleanup/restore |
| `forge/forge.py` | 101 | `preview_operations()`, `apply_approved_operations()` |
| `operations/registry.py` | 98 | `OperationHandler` Protocol, `OperationRegistry`, 6 handlers |
| `coordinator.py` | ~270 | `SliceCoordinator` — 14-state pipeline, zero stubs, audit+dead_letter |
| `approval.py` | 98 | `ApprovalRecord`, hash-bound approval, TOCTOU guard, audit |
| `local_model.py` | 132 | `LocalModelBackend` Protocol, `FakeLocalModelBackend` |
| `llama_client.py` | 173 | HTTP to llama.cpp, JSON retry + backoff, circuit breaker |
| `context.py` | 117 | `build_context_packet()` — per-file/total limits, SHA256, hygiene |
| `validation/semantic.py` | 207 | Pluggable `SemanticValidator` with 5 rules |
| `validation/runner.py` | 143 | `run_validation_profile()` — allowlisted, SIGTERM/SIGKILL |
| `repair.py` | 116 | `RepairCoordinator` — bounded budget, attempt tracking |
| `server.py` | ~640 | FastMCP server — 22 MCP tools over stdio |
| `cli.py` | ~580 | Typer CLI — 16 commands, `--json` flag |
| `token_tracker.py` | ~120 | Token usage tracking with by-model, by-purpose breakdowns |
| `tui.py` | ~200 | Textual TUI dashboard (tokens, runs, KB, model health) |
| `audit_analyzer.py` | ~80 | Audit log analysis, Markdown/JSON report generation |
| `model_state.py` | ~70 | Model server state persistence |
| `integrations/` | ~150 | Fail-soft MEX, Graphify, Headroom adapters |
| `knowledge/` | ~350 | KB store, indexer, promotion, 6 MCP tools |
| `languages/` | ~200 | LanguageAdapter Protocol + RustAdapter + PythonAdapter |
| `rag/` | ~300 | RAG indexer, retriever, enricher, preprocessor |
| `scout/` | ~250 | Scout evidence coordinator + safe_grep

## Test Coverage

**251 tests, 0 failures** — `uv run pytest tests/ -q`

| Test Suite | Count | Focus |
|-----------|-------|-------|
| `test_artifacts.py` | 7 | Run ID uniqueness, directory structure, JSON round-trip |
| `test_errors.py` | 12 | PublicError, ErrorEnvelope, envelope_from sanitization |
| `config/test_load_config.py` | 14 | Config loading, validation, bounds, defaults, RAG section |
| `paths/test_safe_resolve.py` | 10 | Path traversal, symlink escape, null bytes |
| `test_dead_letter.py` | 3 | File creation, timestamp, optional payload |
| `test_audit.py` | 3 | File creation, required fields, JSONL append |
| `test_summary.py` | 5 | Markdown output, run_id, artifacts, errors, missing |
| `contracts/test_registry.py` | 28 | 6 schemas × (1 valid + 3 invalid fixtures) |
| `forge/test_git_utils.py` | 6 | Worktree checks, snapshot lifecycle |
| `forge/test_forge.py` | 7 | Preview diff, apply, restore, TOCTOU, scope enforcement |
| `operations/test_*.py` | 28 | 6 handlers × 4-5 tests + registry dispatch |
| `approval/test_approval.py` | 5 | Record creation, stale detection, TOCTOU, locking |
| `test_coordinator.py` | 12 | State transitions, failure modes, dead letters, schema repair, async-safe entrypoint |
| `test_local_model.py` | 8 | FakeBackend canned responses, failure sim, attempt logging |
| `test_llama_client.py` | 6 | HTTP mock, JSON retry, circuit breaker, config backoff, max_tokens |
| `context/test_build.py` | 6 | Forbidden files, per-file/total limits, SHA256, hygiene |
| `validation/test_semantic.py` | 7 | Scope, size, forbidden, generated, permissions, custom rules |
| `validation/test_runner.py` | 8 | Profile dispatch, command failure, timeout, truncation, shell |
| `test_repair.py` | 7 | Budget enforcement, attempt tracking, feedback prompt |
| `rag/test_retriever.py` | 12 | Retrieval quality, recall@3, recall@1, relevance ordering |
| `rag/test_preprocessor.py` | 15 | Curated KB splitting, external doc parsing, HTML comment stripping |
| `rag/test_index.py` | 9 | Index build, save/load, search round-trip, full pipeline |
| `rag/test_enricher.py` | 7 | Header injection, doc retrieval, token budget, ordering |
| `rag/test_integration.py` | 11 | build_rag_enricher factory, coordinator integration, build_rag_index, turbovec_health, turbovec_index |
| `test_server.py` | 4 | Boot function, stdout redirect, module import |
| `test_cli.py` | 6 | Command registration, --json flag, gitignore template, doctor RAG checks |

## Coordinator Stubs — All Replaced

| Location | Status | Replaced by | Phase |
|----------|--------|-------------|:---:|
| `_build_context()` | ✅ | `context.py` | 2 |
| `_generate_operations()` | ✅ | `local_model.py` Protocol | 2 |
| `_validate_semantic()` | ✅ | `validation/semantic.py` | 2 |
| `_validate_result()` | ✅ | `validation/runner.py` | 3 |
| `_maybe_repair()` | ✅ | `repair.py` + coordinator loop | 4 |
| `_write_dead_letter()` | ✅ | `dead_letter.py` (centralized) | 4 |
| `_preview()` | ✅ | `forge.preview_operations()` (DRY) | 4 |
| `_init_run()` | ✅ | Removed (dead code) | 4 |
| `inspect` command | ✅ | `summary.py` (Markdown) | 4 |

## Audit Remediation — All 8 Findings Resolved

| ID | Finding | Resolution |
|----|---------|------------|
| B1 | Repair loop stub | Full loop: model re-invoke, dual validation, re-preview, budget tracking |
| B2 | Spike reports absent | Three retrospective reports in `spikes/` |
| B3 | Preview missing new files | DRY fix: `forge.preview_operations()` |
| N1 | slice_id hardcoded | Extracted from slice contract, propagated to run.json |
| N2 | Stale snapshot refs | `cleanup_snapshot()` on pass, orphan ref GC |
| N3 | No doctor auto-run | `--skip-doctor` flag, auto-run on init/approve |
| N4 | Context no schema_id | Added `"schema_id": "forgerwrite.context_packet.v1"` |
| N5 | _init_run() dead code | Removed |

## Phase 5 Readiness

Phase 5 (Acceptance) requires:
- 3 real Rust slices end-to-end with a running llama.cpp + OmniCoder
- No data loss, no corruption, inspectable artifacts
- Written acceptance report

**Zero stubs remaining in the entire codebase.**

## Code Quality

| Tool | Status |
|------|--------|
| `ruff check` | All checks passed |
| `ruff format` | All files formatted |
| `mypy` | Not yet run (planned Phase 4) |

## Protocol Compliance

| Rule | Status |
|------|--------|
| TDD | ✅ All tests written before implementation |
| No magic numbers | ✅ All limits from config; named constants for thresholds |
| DRY | ✅ Single `safe_resolve_path`; single `envelope_from()` for errors |
| SRP | ✅ Server: thin tools; CLI: one command per function; each module one job |
| Open/Closed | ✅ `OperationRegistry.register()`; `SemanticValidator.register()`; CLI via Typer |
| Encapsulation | ✅ `PublicError`/`ErrorEnvelope` sanitize; `_` prefix on privates |
| Extend, don't modify | ✅ New error codes in own modules; new commands via decorators |

## Git State

```
* 622c5c8 (HEAD -> dev) chore: update project state docs, fix stale comment
* 1fdaf5e (main) feat: Phase 2 — local model integration
* 3d7f579 feat: Phase 0-1 complete — foundation with TDD
```

- Active development on `dev`
- Phase 3 changes uncommitted: coordinator wire-up + 4 new modules + 4 test files

## Phase 4 Readiness

| Check | Status |
|-------|--------|
| All 169 tests pass | ✅ |
| Ruff clean | ✅ |
| 0 stubs remaining | ✅ |
| MCP server boots | ✅ |
| CLI has all 13 commands | ✅ |
| `--json` flag on all commands | ✅ |
| `abort` command exists | ✅ |
| `build-index` command exists | ✅
| `approve` is interactive | ✅ |

---

## Coming Next: Phase 1 — Rust MVP Acceptance

1. Prove the Rust pipeline with 3 formal end-to-end slices
2. Exercise repair loop at least once
3. Write acceptance documentation
4. All Phase 0 PV1/PV2 bugs closed

See `docs/implementation-plan.md` for full Phase 1 plan.
