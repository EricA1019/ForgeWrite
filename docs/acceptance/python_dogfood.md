# Python Dogfood Acceptance Report

**Date:** 2026-06-16
**Model:** Gemma 4 12B (Q4_K_XL) via llama.cpp
**Pipeline:** `SliceCoordinator` with auto-approve
**Baseline:** 265 unit tests passing, 0 failures

---

## Summary

| Slice | Goal | Status | Notes |
|-------|------|--------|-------|
| P1 | Add adapter tests | ✅ **Complete (Phase 2)** | 14 tests written in Phase 2 cover Protocol, RustAdapter, PythonAdapter, discovery |
| P2 | Refactor validation profile config | ✅ **Complete (Phase 2)** | `coordinator.py:_validate_result()` resolves profile from `config.project.language` via adapter |
| P3 | Update init template for Python | ✅ **Complete (Phase 2)** | `init --language python` generates config with ruff/pytest/mypy commands |
| P4 | Add Python documentation | ⚠️ Attempted | Pipeline ran but LLM JSON generation failed (see below) |
| P5 | Fix real Python bug | ✅ **Complete** | `F841` in `cli.py:55` and `F821` in `rag/__init__.py:37` both fixed |

---

## Slices Accomplished in Phase 2

These deliverables were completed as part of the LanguageAdapter Seam (Phase 2) and directly support Python dogfooding:

### P1 — Adapter Tests

`tests/test_language_adapters.py` contains 14 tests across 4 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestLanguageAdapterProtocol` | 5 | Protocol contract (isinstance, language, commands, profile name, profiles) |
| `TestRustAdapter` | 3 | Rust defaults match old hardcoded values |
| `TestPythonAdapter` | 3 | Python commands (ruff, pytest, mypy), profile completeness, discovery registration |
| `TestAdapterDiscovery` | 3 | Unknown language returns None, Rust via get_adapter, list includes both |

### P2 — Validation Profile Refactor

`coordinator.py:_validate_result()` before Phase 2:
```python
# Hardcoded
result = run_validation_profile(self._repo_root, "rust_default", ...)
```

After Phase 2:
```python
# Resolved from language adapter
adapter = get_adapter(self._config.project.language)
profile_id = adapter.get_default_profile_name() if adapter else "rust_default"
result = run_validation_profile(self._repo_root, profile_id, ...)
```

### P3 — Init Template for Python

Verified working:
```bash
$ forgerwrite init --language python
# Generates:
# [project]
# language = "python"
#
# [validation.commands]
# lint = "ruff check ."
# format_check = "ruff format --check ."
# test = "pytest -q"
# typecheck = "mypy --strict forgerwrite_mcp/"
#
# [validation.profiles]
# python_default = ['lint', 'format_check', 'test', 'typecheck']
```

Switching a project to Python mode requires changing `language = "python"` in `.forgerwrite/forgerwrite.toml`.

### P5 — Real Python Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| `F841` unused variable | `cli.py:55` | Removed `default_profile = adapter.get_default_profile_name()` (leftover from Phase 2 implementation) |
| `F821` undefined name | `rag/__init__.py:37` | Added `from pathlib import Path` under `TYPE_CHECKING` guard |

Both were identified by `ruff check forgerwrite_mcp/` and fixed.

---

## Slice P4 — Python Documentation (Attempted)

### Goal
Add a "Python Projects" section to `docs/configuration.md` documenting how to use ForgeWrite with Python projects.

### Pipeline Attempt

```
Status: context_ready (199s)
Error: Failed to get valid JSON after 3 attempts
```

The pipeline built context and called the model 3 times, but JSON extraction failed each time.

### Root Cause

The Gemma 4 12B model with the current llama.cpp version (`b8680`) exhibits a behavior where the `json_object` response format places the model's output in `reasoning_content` instead of `content`. The model is a reasoning model that first outputs chain-of-thought text (reasoning), then produces the actual JSON. With `json_object` format, the chain-of-thought goes to `reasoning_content` and the JSON also goes to `reasoning_content`, while `content` remains empty.

### Fix Applied

The `LlamaCppClient.generate_operation_batch()` method was updated to:

1. **Remove `json_object` response format** — the format is unreliable with reasoning models
2. **Check both `content` and `reasoning_content`** — fall back to `reasoning_content` when `content` is empty
3. **Extract JSON from arbitrary text** — `_extract_json()` function tries full text parsing, then `{...}` substring extraction, then regex matching for nested JSON objects
4. **Strengthen prompt on retry** — if JSON extraction fails, append a stricter "ONLY output JSON" instruction to the system prompt

### Verification

The `_extract_json()` function passes unit tests for:
- Full JSON strings
- JSON embedded in prose text
- Nested JSON objects with arrays
- Empty strings

However, the model's generation with the full pipeline system prompt (which includes the operation batch schema as context) still failed to produce parseable JSON within 3 retry attempts.

### Recommendation

For Phase 3 slices to succeed, the model needs either:
1. A different llama.cpp version that handles `json_object` correctly
2. A different model that doesn't use reasoning tokens
3. Manual operation batch construction (bypassing the LLM for documentation tasks)

---

## Configuration

To use ForgeWrite with Python projects:

```bash
# Initialize a new project with Python defaults
forgerwrite init --language python

# Or switch an existing project to Python
# Edit .forgerwrite/forgerwrite.toml:
#   [project]
#   language = "python"
```

The `python_default` validation profile runs:
| Command | Tool |
|---------|------|
| `lint` | `ruff check .` |
| `format_check` | `ruff format --check .` |
| `test` | `pytest -q` |
| `typecheck` | `mypy --strict forgerwrite_mcp/` |

---

## Appendix: Test Suite

**265 tests, 0 failures** — all existing Rust and Python tests pass.
