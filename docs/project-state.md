# ForgerWrite MCP — Project State

**Date:** 2026-06-06
**Branch:** `dev` (same HEAD as `main` @ `1fdaf5e`)
**Phase:** Phase 2 complete, Phase 3 preflight

---

## Architecture Overview

```
forgerwrite_mcp/
├── artifacts.py          # Run ID generation + centralized artifact I/O
├── approval.py           # Hash-bound, TOCTOU-safe terminal approval
├── config.py             # Pydantic models for all config sections
├── context.py            # Context packet builder (per-file + total limits, SHA256)
├── coordinator.py        # SliceCoordinator — 14-state machine owner
├── errors.py             # PublicError, ErrorEnvelope, 10 error code constants
├── llama_client.py       # HTTP client for llama.cpp (retry + circuit breaker)
├── local_model.py        # LocalModelBackend Protocol + FakeLocalModelBackend
├── paths.py              # safe_resolve_path (single DRY path safety)
├── contracts/
│   └── registry.py       # JSON Schema loading + Draft 2020-12 validation
├── forge/
│   ├── git_utils.py      # Snapshot create/cleanup/restore, worktree checks
│   └── forge.py          # preview_operations, apply_approved_operations
├── operations/
│   ├── registry.py       # OperationHandler Protocol + OperationRegistry
│   ├── create_file.py
│   ├── replace_file.py
│   ├── replace_line_range.py
│   ├── insert_after_line.py
│   ├── insert_before_line.py
│   └── delete_file.py
└── validation/
    └── semantic.py       # SemanticValidator with 5 pluggable rules

schemas/
├── handoff.v1.json
├── slice.v1.json
├── operation_batch.v1.json
├── approval_record.v1.json
├── validation_result.v1.json
└── run.v1.json

tests/
├── test_artifacts.py      (7)
├── test_coordinator.py    (5)
├── test_errors.py         (12)
├── test_llama_client.py   (6)
├── test_local_model.py    (8)
├── config/                (10)
├── context/               (6)
├── contracts/             (28)
├── forge/                 (14)
├── operations/            (28)
├── paths/                 (10)
├── approval/              (5)
└── validation/            (7)
```

## Module Inventory

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `artifacts.py` | 107 | Run ID generation, run directory creation, artifact read/write |
| `errors.py` | 96 | `PublicError`, `ErrorEnvelope`, `envelope_from()`, 10 error codes |
| `config.py` | 144 | `ForgerWriteConfig` + 7 Pydantic section models, `load_config()` |
| `paths.py` | 67 | `safe_resolve_path()`, `assert_inside_repo()` |
| `contracts/registry.py` | 66 | `ContractRegistry` — schema loading, caching, Draft 2020-12 validation |
| `forge/git_utils.py` | 99 | `assert_clean_worktree()`, snapshot create/cleanup/restore |
| `forge/forge.py` | 101 | `preview_operations()`, `apply_approved_operations()` |
| `operations/registry.py` | 98 | `OperationHandler` Protocol, `OperationRegistry`, 6 handlers |
| `coordinator.py` | ~260 | `SliceCoordinator` — owns 14-state pipeline |
| `approval.py` | 94 | `ApprovalRecord`, hash-bound approval, TOCTOU guard |
| **Phase 2** | | |
| `local_model.py` | 132 | `LocalModelBackend` Protocol, `FakeLocalModelBackend` |
| `llama_client.py` | 173 | HTTP to llama.cpp, JSON retry + backoff, circuit breaker |
| `context.py` | 117 | `build_context_packet()` — per-file/total limits, SHA256, hygiene |
| `validation/semantic.py` | 207 | Pluggable `SemanticValidator` with 5 rules |

## Test Coverage

**145 tests, 0 failures** — all passing with `uv run pytest tests/ -q`

| Test Suite | Count | Focus |
|-----------|-------|-------|
| `test_artifacts.py` | 7 | Run ID uniqueness, directory structure, JSON round-trip |
| `test_errors.py` | 12 | PublicError, ErrorEnvelope, envelope_from sanitization |
| `config/test_load_config.py` | 10 | Config loading, validation, bounds, defaults |
| `paths/test_safe_resolve.py` | 10 | Path traversal, symlink escape, null bytes |
| `contracts/test_registry.py` | 28 | 6 schemas × (1 valid + 3 invalid fixtures) + edge cases |
| `forge/test_git_utils.py` | 6 | Worktree checks, snapshot lifecycle |
| `forge/test_forge.py` | 7 | Preview diff, apply, restore, TOCTOU, scope enforcement |
| `operations/test_*.py` | 28 | 6 handlers × 4-5 tests + registry dispatch |
| `approval/test_approval.py` | 5 | Record creation, stale detection, TOCTOU, locking |
| `test_coordinator.py` | 5 | State transitions, failure modes, dead letters |
| **Phase 2** | | |
| `test_local_model.py` | 8 | FakeBackend canned responses, failure sim, attempt logging |
| `test_llama_client.py` | 6 | HTTP mock, JSON retry, circuit breaker, config backoff |
| `context/test_build.py` | 6 | Forbidden files, per-file/total limits, SHA256, hygiene |
| `validation/test_semantic.py` | 7 | Scope, size, forbidden, generated, permissions, custom rules |

## Code Quality

| Tool | Status |
|------|--------|
| `ruff check` | All checks passed |
| `ruff format` | All files formatted |
| `mypy` | Not yet run (planned Phase 4) |

## Coordinator Stubs

| Location | Status | Replaced by | Phase |
|----------|--------|-------------|:---:|
| `_build_context()` | ✅ Replaced | `context.py` | 2 |
| `_generate_operations()` | ✅ Upgraded | `local_model.py` Protocol | 2 |
| `_validate_semantic()` | ✅ Replaced | `validation/semantic.py` | 2 |
| `_validate_result()` | ⏳ Stub | `validation/runner.py` | 3 |
| `_maybe_repair()` | ⏳ Stub | `repair.py` | 3 |

## Protocol Compliance

| Rule | Status |
|------|--------|
| TDD | ✅ All tests written before implementation |
| No magic numbers | ✅ All limits from config; circuit breaker thresholds named |
| DRY | ✅ Single `safe_resolve_path`; single `artifacts.py` for I/O; single `LocalModelBackend` Protocol |
| SRP | ✅ `SliceCoordinator` owns state machine; each Phase 2 module has one job |
| Open/Closed | ✅ `OperationRegistry.register()`; `SemanticValidator.register(SemanticRule)` |
| Encapsulation | ✅ `PublicError`/`ErrorEnvelope` sanitize; `_` prefix on privates |
| Extend, don't modify | ✅ `CONTEXT_ERROR` in `context.py` (not modifying `errors.py`) |

## Git State

```
* 1fdaf5e (HEAD -> dev, main) feat: Phase 2 — local model integration
* 3d7f579 feat: Phase 0-1 complete — foundation with TDD
```

- 86 files committed
- `main` and `dev` at same HEAD (Phase 2 merged)
- Active development on `dev`

## Phase 3 Readiness

| Check | Status |
|-------|--------|
| All 145 tests pass | ✅ |
| Ruff clean | ✅ |
| `httpx` 0.28.1 available | ✅ |
| `pytest-asyncio` configured | ✅ |
| `typer` + `rich` available (for CLI) | ✅ |
| `mcp[cli]` available (for server) | ✅ |
| Coordinator has 2 stubs for Phase 3 | ✅ (documented) |
| `FakeLocalModelBackend` enables CI testing | ✅ |
| No uncommitted changes | ✅ |

---

## Coming Next: Phase 3 — Integration

1. **Step 3.1:** Validation runner (allowlisted commands, SIGTERM/SIGKILL)
2. **Step 3.2:** Repair coordinator (bounded budget, model feedback loop)
3. **Step 3.3:** MCP server (10 thin tools → SliceCoordinator, stdout redirect)
4. **Step 3.4:** CLI (init, doctor, approve, show-diff, abort, inspect, restore, gc)

Target: ~30 additional tests, replace final 2 coordinator stubs.
