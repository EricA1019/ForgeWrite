---
name: conventions
description: How code is written in this project — naming, structure, patterns, and style. Load when writing new code or reviewing existing code.
triggers:
  - "convention"
  - "pattern"
  - "naming"
  - "style"
  - "how should I"
  - "what's the right way"
edges:
  - target: context/architecture.md
    condition: when a convention depends on understanding the system structure
last_updated: 2026-06-07
---

# Conventions

## Naming
- Files: snake_case (`safe_resolve_path`, `git_utils.py`, `test_coordinator.py`)
- Modules: descriptive nouns (`coordinator.py`, `approval.py`) or domain prefixes (`insert_after_line.py`)
- Functions: verb-first snake_case (`write_dead_letter`, `build_context_packet`, `assert_clean_worktree`)
- Classes: PascalCase (`SliceCoordinator`, `ContractRegistry`, `RepairCoordinator`)
- Error classes: inherit from `PublicError` (not `Exception`); code constants in `errors.py` as `UPPER_SNAKE_CASE`
- Test files: `test_<module>.py` in `tests/` mirroring source structure

## Structure
- No orchestration logic in MCP tools or CLI — delegate to `SliceCoordinator` and library modules
- All file mutations go through `OperationHandler.apply()` via `OperationRegistry.dispatch()`
- All path resolution uses `safe_resolve_path()` — never bare `Path` construction
- All magic numbers live in `forgerwrite.toml` → `config.py` Pydantic models
- New operation types: create a handler file in `operations/`, register in `default_registry()`
- New validation rules: implement `SemanticRule` Protocol, register in `default_validator()`
- TDD: write failing test first, then implementation

## Patterns
Always use `envelope_from()` for error responses — never return raw exception messages:
```python
# Correct
try:
    ...
except Exception as exc:
    return envelope_from(exc, "operation_name").to_dict()

# Wrong
try:
    ...
except Exception as exc:
    return {"ok": False, "error": str(exc)}
```

Always use `safe_resolve_path()` for file operations — never direct Path construction:
```python
# Correct
path = safe_resolve_path(repo_root, op["path"])

# Wrong
path = repo_root / op["path"]
```

## Verify Checklist
Before presenting any code:
- [ ] All file paths go through `safe_resolve_path()`
- [ ] All errors use `PublicError` subclasses or `envelope_from()`
- [ ] No magic numbers — all limits/timeouts from config
- [ ] No `shell=True` in subprocess calls
- [ ] No `print()` to stdout in server code
- [ ] New public functions have docstrings
- [ ] Tests exist for the new code (TDD)
