# ForgerWrite MCP — Project State

**Date:** 2026-06-06
**Branch:** `dev` (based on `main` @ `3d7f579`)
**Phase:** Phase 1 complete, Phase 2 preflight passed

---

## Architecture Overview

```
forgerwrite_mcp/
├── artifacts.py          # Run ID generation + centralized artifact I/O
├── approval.py           # Hash-bound, TOCTOU-safe terminal approval
├── config.py             # Pydantic models for all config sections
├── coordinator.py        # SliceCoordinator — 14-state machine owner
├── errors.py             # PublicError, ErrorEnvelope, 9 error codes
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
    └── __init__.py        # (package marker — semantic + runner in later phases)

schemas/
├── handoff.v1.json
├── slice.v1.json
├── operation_batch.v1.json
├── approval_record.v1.json
├── validation_result.v1.json
└── run.v1.json

tests/
├── test_artifacts.py      (7 tests)
├── test_coordinator.py    (5 tests)
├── test_errors.py         (12 tests)
├── config/                (10 tests)
├── paths/                 (10 tests)
├── contracts/             (28 tests)
├── forge/                 (14 tests)
├── operations/            (28 tests)
└── approval/              (5 tests)
```

## Module Inventory

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `artifacts.py` | 107 | Run ID generation, run directory creation, artifact read/write |
| `errors.py` | 96 | `PublicError`, `ErrorEnvelope`, `envelope_from()`, 9 error codes |
| `config.py` | 144 | `ForgerWriteConfig` + 7 Pydantic section models, `load_config()` |
| `paths.py` | 67 | `safe_resolve_path()`, `assert_inside_repo()` |
| `contracts/registry.py` | 66 | `ContractRegistry` — schema loading, caching, Draft 2020-12 validation |
| `forge/git_utils.py` | 99 | `assert_clean_worktree()`, snapshot create/cleanup/restore |
| `forge/forge.py` | 101 | `preview_operations()`, `apply_approved_operations()` |
| `operations/registry.py` | 98 | `OperationHandler` Protocol, `OperationRegistry`, 6 handlers |
| `coordinator.py` | 252 | `SliceCoordinator` — owns 14-state pipeline |
| `approval.py` | 94 | `ApprovalRecord`, hash-bound approval, TOCTOU guard |

## Test Coverage

**118 tests, 0 failures** — all passing with `uv run pytest tests/ -q`

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

## Code Quality

| Tool | Status |
|------|--------|
| `ruff check` | All checks passed |
| `ruff format` | All files formatted |
| `mypy` | Not yet run (planned Phase 4) |

## Protocol Compliance

| Rule | Status |
|------|--------|
| TDD | All tests written before implementation |
| No magic numbers | All limits from `ForgerWriteConfig`; `graceful_kill_timeout_seconds`, retry backoff in config |
| DRY | Single `safe_resolve_path`; single `artifacts.py` for file I/O |
| SRP | `SliceCoordinator` owns state machine; server/CLI not yet built |
| Open/Closed | `OperationRegistry.register()` for handlers |
| Encapsulation | `PublicError`/`ErrorEnvelope` sanitize; no class names leak |
| Private by default | `_ModelBackend`, `_RUN_DIR_BASE`, `_snapshot_ref` prefix |

## Documented Stubs (6)

These are planned and deferred to correct phases:

| Location | Deferred To | Phase |
|----------|-------------|-------|
| `coordinator._build_context()` | `context.py` | 2 |
| `coordinator._generate_operations()` | `local_model.py` / `llama_client.py` | 2 |
| `coordinator._validate_semantic()` | `validation/semantic.py` | 2 |
| `coordinator._validate_result()` | `validation/runner.py` | 3 |
| `coordinator._maybe_repair()` | `repair.py` | 3 |
| `delete_file.validate()` — `pass` | Intentional (delete has no content) | N/A |

## Git State

```
* dev  3d7f579 feat: Phase 0-1 complete — foundation with TDD
  main 3d7f579 feat: Phase 0-1 complete — foundation with TDD
```

- 75 files, 6,698 lines committed
- `main` is stable; `dev` is the active development branch
- `.gitignore` excludes `.forgerwrite/runs/`, `__pycache__/`, `.venv/`, secrets

## Phase 2 Readiness

| Check | Status |
|-------|--------|
| All 118 tests pass | ✅ |
| Ruff clean | ✅ |
| `httpx` 0.28.1 available | ✅ |
| `pytest-asyncio` configured | ✅ |
| `_ModelBackend` Protocol defined | ✅ |
| `LocalModelConfig` with retry fields | ✅ |
| Coordinator stubs documented | ✅ |
| No uncommitted changes | ✅ |

---

## Coming Next: Phase 2 — Local Model Integration

1. **Step 2.1:** `LocalModelBackend` Protocol + `FakeLocalModelBackend`
2. **Step 2.2:** Context packet builder
3. **Step 2.3:** llama.cpp HTTP client with retries + circuit breaker
4. **Step 2.4:** Semantic validator with pluggable rules

Target: ~20 additional tests, wire into `SliceCoordinator` replacing 3 stubs.
