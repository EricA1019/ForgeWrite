# ForgeWrite — Detailed Implementation Plan

**Date:** 2026-06-16 (updated)
**Baseline:** 315 tests, 0 failures, main
**Remote:** None configured
**Current phase:** 7 (final) — dogfooding via `docs/dogfood-plan.md`

---

## Phase 0: Stabilize Core & Naming ✅

**Goal:** Fix safety bugs, verify PV1 status, add async-safe entrypoint, stage public naming, add TurboVec MCP tools, move RAG enrichment to coordinator.

**Gate:** All 246+ tests pass. No regressions. `forgerwrite doctor` covers RAG health. Naming ADR committed.

### Task 0.1 — Verify PV1 (PermissionRule config behavior)

PV1 is listed as open debt ("PermissionRule ignores permissions config") but code inspection shows `PermissionRule.check()` already reads from the `permissions: PermissionsConfig` parameter. Two tests exist in `tests/validation/test_semantic.py`:
- `test_permission_rule_reads_config_for_replace_file` (line 89)
- `test_permission_rule_reads_config_for_delete_file` (line ~108)

**Action:** Run the specific tests. If they pass, PV1 is already fixed — document closure. If they fail, fix is small.

```bash
uv run pytest tests/validation/test_semantic.py -k "permission_rule_reads_config" -v
```

**Files:** No changes unless tests fail.
**Tests:** Verify existing 2 tests pass.

---

### Task 0.2 — Fix PV2 (async-safe coordinator entrypoint)

**Problem:** `SliceCoordinator.run()` calls `asyncio.run(self._generate_with_schema_repair(...))` on line ~112. If `run()` is invoked from an already-running async event loop (e.g., from an `async def` MCP tool), Python raises `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**Current usage:** MCP server tools in `server.py` do NOT call `coordinator.run()` — they call individual pipeline functions directly. But future tools (Scout, knowledge) will want to use the coordinator from async contexts.

**Fix approach:** Add `run_async()` method that works inside an event loop, keep `run()` as the sync wrapper.

**Step 1:** Write failing test.

File: `tests/test_coordinator.py`

```python
def test_run_in_async_context_does_not_raise_event_loop_error(
    self, coordinator: object, tmp_path: Path
) -> None:
    """Calling coordinator.run() from within an async context should succeed."""
    import asyncio
    from forgerwrite_mcp.coordinator import SliceCoordinator

    coord: SliceCoordinator = coordinator  # type: ignore[assignment]

    handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
    slice_contract = {
        "schema_id": "forgerwrite.slice.v1",
        "slice_id": "test-slice",
        "allowed_files": ["src/generated.rs"],
    }

    async def call_run():
        return coord.run(handoff, slice_contract)

    # Must not raise RuntimeError about running event loop
    outcome = asyncio.run(call_run())
    assert outcome.run_dir is not None
```

Expected: This test FAILS with `RuntimeError: asyncio.run() cannot be called from a running event loop` before the fix.

**Step 2:** Add `run_async()` to `SliceCoordinator`.

File: `forgerwrite_mcp/coordinator.py` (~line 95, after `run()`)

Add method:

```python
async def run_async(self, handoff: dict[str, Any], slice_contract: dict[str, Any]) -> RunOutcome:
    """Async-safe entrypoint. Use this when called from within an event loop."""
    self._run_id = generate_run_id()
    self._run_dir = init_run_dir(self._run_id, base_dir=self._repo_root)
    self._slice_id = slice_contract.get("slice_id", "unknown")
    status = _STATUS_DRAFT

    try:
        status = self._validate_contracts(handoff, slice_contract)
        status = self._build_context(handoff, slice_contract)
        status = await self._generate_with_schema_repair(handoff, slice_contract)
        # ... (same pipeline as run(), but with await instead of asyncio.run)
    except Exception as exc:
        # ... same error handling
    finally:
        self._record(status)
    return RunOutcome(...)
```

Then refactor `run()` to delegate:

```python
def run(self, handoff: dict[str, Any], slice_contract: dict[str, Any]) -> RunOutcome:
    """Sync entrypoint. Delegates to run_async via asyncio.run."""
    import asyncio
    return asyncio.run(self.run_async(handoff, slice_contract))
```

**Step 3:** Retest. `test_run_in_async_context_does_not_raise_event_loop_error` should pass.

**Files:** `forgerwrite_mcp/coordinator.py` (refactor), `tests/test_coordinator.py` (+1 test)
**Tests:** 1 new, 11 existing coordinator tests must not regress.

---

### Task 0.3 — Naming ADR + user-facing rename

**Problem:** Public name is "ForgeWrite" but all code, docs, config say "ForgerWrite". Deferring to Phase 10 creates 9 phases of drift.

**Fix:** Add a naming ADR. Update user-facing strings only. Do NOT rename the Python package.

**Step 1:** Create `docs/adr/0001-naming.md`:

```markdown
# ADR-0001: Public Name is ForgeWrite

**Status:** Accepted
**Date:** 2026-06-13

## Decision
The public product name is **ForgeWrite**. The internal Python package
`forgerwrite_mcp/` will be renamed to `forgewrite_mcp/` in a future
ADR when import-compatibility concerns are resolved.

## Scope of this ADR
- README, docstrings, CLI help text, MCP tool descriptions → "ForgeWrite"
- Config directory `.forgerwrite/` → stays for now (rename later)
- Python package `forgerwrite_mcp/` → stays for now (rename later)
- CLI binary `forgerwrite` → stays for now (rename later)
```

**Step 2:** Update user-facing strings:

| File | Change |
|------|--------|
| `README.md` | "ForgerWrite" → "ForgeWrite" in title/description |
| `docs/project-state.md` | Title: "ForgeWrite MCP — Project State" |
| `forgerwrite_mcp/server.py` | `FastMCP("forgerwrite")` stays; docstring "ForgerWrite MCP server" |
| `forgerwrite_mcp/cli.py` | `app = typer.Typer(name="forgerwrite", help="...")` — help text updated |
| `.github/copilot-instructions.md` | Project name updated |

**Files:** 6 files, string-only changes.
**Tests:** No new tests needed (cosmetic).

---

### Task 0.4 — Add `fw_turbovec_health` MCP tool

**What:** Thin MCP tool that returns TurboVec/RAG index health. The existing `RagIndex` has a `.load()` method; the tool checks index file presence and basic integrity.

**Step 1:** Write test.

File: `tests/rag/test_integration.py` (add test)

```python
def test_turbovec_health_returns_status(tmp_path: Path) -> None:
    """fw_turbovec_health reports index presence and document count."""
    # Build a small index, check health
    ...
```

**Step 2:** Add tool to `server.py`:

```python
@mcp.tool()
async def fw_turbovec_health() -> dict:
    """Report TurboVec retrieval system health."""
    try:
        from .config import load_config
        from pathlib import Path
        config = load_config(Path.cwd())
        index_path = Path.cwd() / config.rag.index_path
        if not index_path.exists():
            return {"ok": True, "healthy": False, "reason": "index not found"}
        from .rag.index import RagIndex
        idx = RagIndex.load(str(index_path))
        return {
            "ok": True,
            "healthy": True,
            "document_count": len(idx.documents) if idx.documents else 0,
            "index_path": str(index_path),
        }
    except Exception as exc:
        return envelope_from(exc, "turbovec_health").to_dict()
```

**Files:** `forgerwrite_mcp/server.py` (+1 tool), `tests/rag/test_integration.py` (+1 test)
**Tests:** 1 new

---

### Task 0.5 — Add `fw_turbovec_index` MCP tool

**What:** MCP tool wrapping `build_rag_index()`. Lets users rebuild the index via MCP.

**Step 1:** Write test (mock/fake — verify tool calls factory, doesn't require live model).

**Step 2:** Add tool to `server.py`:

```python
@mcp.tool()
async def fw_turbovec_index(kb_dir: str = "data/rag", index_path: str = "data/rag/index.tqi") -> dict:
    """Build (or rebuild) the TurboVec retrieval index."""
    try:
        from .rag import build_rag_index
        index = build_rag_index(kb_dir=kb_dir, index_path=index_path)
        return {"ok": True, "indexed": len(index.documents) if index.documents else 0}
    except Exception as exc:
        return envelope_from(exc, "turbovec_index").to_dict()
```

**Files:** `forgerwrite_mcp/server.py` (+1 tool), `tests/rag/test_integration.py` (+1 test)
**Tests:** 1 new

---

### Task 0.6 — Add RAG index check to `forgerwrite doctor`

**What:** `doctor.py` already checks config, worktree, etc. Add a RAG index presence and sentence-transformers availability check.

**Step 1:** Write test.

File: `tests/test_cli.py` — add a doctor test that verifies RAG section appears in output.

**Step 2:** Add check to `doctor.py`:

```python
def _check_rag_index(project_root: Path) -> list[dict]:
    """Check RAG index health."""
    results = []
    try:
        from .config import load_config
        config = load_config(project_root)
        index_path = project_root / config.rag.index_path
        if index_path.exists():
            results.append({"check": "rag_index", "status": "ok", "detail": str(index_path)})
        else:
            results.append({"check": "rag_index", "status": "warning", "detail": "Index not found. Run: forgerwrite build-index"})
        # Check sentence-transformers
        try:
            import sentence_transformers
            results.append({"check": "sentence_transformers", "status": "ok"})
        except ImportError:
            results.append({"check": "sentence_transformers", "status": "error", "detail": "Not installed"})
    except Exception as exc:
        results.append({"check": "rag", "status": "error", "detail": str(exc)})
    return results
```

**Files:** `forgerwrite_mcp/doctor.py` (+~25 lines), `tests/test_cli.py` (+1 test)
**Tests:** 1 new

---

### Task 0.7 — Move RAG enrichment from server tool to coordinator

**Problem:** RAG enrichment happens in TWO places:
1. `fw_generate_operations_local` in `server.py` (line ~110): calls `build_rag_enricher()` and enriches the user prompt
2. `SliceCoordinator._generate_operations()` in `coordinator.py` (line ~200): also calls `self._enricher.enrich()`

The coordinator already accepts an `enricher` parameter and uses it. The server tool does its own enrichment AND passes `None` for enricher to the coordinator. This is two code paths doing the same thing.

When Scout is added (Phase 4), it would add a THIRD enrichment path. Fix this now.

**Fix:** Remove RAG enrichment from `fw_generate_operations_local`. The coordinator's `_generate_operations()` already handles it via `self._enricher`. Update the server tool to construct the enricher and pass it to the coordinator.

Wait — looking more carefully: `fw_generate_operations_local` does NOT use the coordinator at all. It directly calls `build_context_packet()`, `LlamaCppClient.from_config()`, and `build_rag_enricher()`. This is a parallel code path to the coordinator's pipeline.

**Better fix:** Make `fw_generate_operations_local` use the coordinator instead of duplicating pipeline logic. But that's a larger refactor. For Phase 0, the minimum is to ensure the coordinator's enrichment path is the only one used when the coordinator runs. The server tool's direct path is a separate concern.

**Decision:** Defer merging server tool + coordinator paths to Phase 3 (dogfood). For Phase 0, just document the duplication in the naming ADR as known technical debt.

**Files:** None for now. Add a note to ADR-0001 about this duplication.
**Tests:** None.

---

### Task 0.8 — Regression gate

```bash
uv run ruff check forgerwrite_mcp/ tests/
uv run mypy forgerwrite_mcp/
uv run pytest tests/ -q
```

Expected: 246 + ~5 new tests = ~251 passing.

---

### Phase 0 Summary

| File | Action | Lines |
|------|--------|-------|
| `forgerwrite_mcp/coordinator.py` | Add `run_async()`, refactor `run()` | +40, ~20 changed |
| `forgerwrite_mcp/server.py` | Add `fw_turbovec_health`, `fw_turbovec_index` | +45 |
| `forgerwrite_mcp/doctor.py` | Add `_check_rag_index()` | +25 |
| `tests/test_coordinator.py` | Add async-context test | +25 |
| `tests/rag/test_integration.py` | Add 2 TurboVec tool tests | +40 |
| `tests/test_cli.py` | Add doctor RAG test | +15 |
| `docs/adr/0001-naming.md` | New | +25 |
| `README.md` | Naming fix | ~5 lines changed |
| 6 files | String-only naming updates | ~10 lines changed |

**New tests:** ~5
**Pass budget:** 3-5 agent passes

---

## Phase 1: Rust MVP Acceptance ✅

**Goal:** Prove the Rust pipeline with 3 formal end-to-end slices. Produce acceptance documentation.

**Gate:** 3/3 Rust slices pass validation with no data loss. `docs/acceptance/rust.md` committed.

### Precondition
- OmniCoder 9B or Gemma 4 running at `http://127.0.0.1:8080/v1`
- `.forgerwrite/forgerwrite.toml` has `[rag] enabled = true`

### Slice R1 — Create a small Rust CLI project

**Contract:**
```json
{
  "slice_id": "r1-create-cli",
  "goal": "Create a minimal Rust CLI project that parses one flag",
  "allowed_files": ["src/main.rs", "Cargo.toml"],
  "validation_profile": "rust_default"
}
```

**Expected operations:**
1. `create_file` → `Cargo.toml` (package config)
2. `create_file` → `src/main.rs` (clap-based CLI)

**Acceptance criteria:**
- `cargo build` passes
- `cargo test` passes (if model adds a test)
- `cargo clippy` passes with no warnings
- `cargo fmt -- --check` passes
- Run summary artifact saved

### Slice R2 — Add failing test + fix behavior

Start with a Rust project that has a function returning the wrong value. The model must:
1. Add a test that exposes the bug
2. Fix the function

**Acceptance criteria:**
- Test added before fix (verify in operation batch order)
- `cargo test` passes after fix
- Repair loop exercised if first attempt fails

### Slice R3 — Refactor without behavior change

Start with a working Rust module. The model must extract a function or rename a symbol without changing behavior.

**Acceptance criteria:**
- All existing tests pass after refactor
- No new functionality added
- `cargo clippy` passes

### Tasks

1. Write acceptance test fixtures for each slice (expected outputs)
2. Run Slice R1 through full pipeline: `fw_generate_operations_local` → validate → preview → approve → apply → validate
3. Run Slice R2 through full pipeline
4. Run Slice R3 through full pipeline
5. Exercise repair loop at least once (R2 is the best candidate)
6. Write `docs/acceptance/rust.md` with run summaries, timings, and model used

**Files:** `docs/acceptance/rust.md` (new), run artifacts in `.forgerwrite/runs/`
**Tests:** Acceptance artifacts, no new unit tests
**Pass budget:** 4-8 agent passes

---

## Phase 2: Language Adapter Seam ✅

**Goal:** Extract Rust-specific defaults from core pipeline. Add Python adapter. No behavior change for Rust.

**Gate:** Rust acceptance slices still pass. Python adapter validates Python operations.

### Task 2.1 — Write failing tests for LanguageAdapter Protocol

File: `tests/test_language_adapters.py` (new)

```python
"""Tests for the LanguageAdapter protocol and built-in adapters."""

import pytest
from pathlib import Path


class TestLanguageAdapterProtocol:
    """Contract tests for LanguageAdapter."""

    def test_adapter_exposes_validation_commands(self) -> None:
        """Every adapter must return a dict of command_id → shell command."""
        from forgerwrite_mcp.languages.base import LanguageAdapter
        # Use isinstance check on concrete adapters
        ...

    def test_adapter_exposes_default_profile(self) -> None:
        """Every adapter must return a default validation profile name."""
        ...

    def test_adapter_returns_config_defaults(self) -> None:
        """Every adapter returns command dicts and profile dicts matching config schema."""
        ...


class TestRustAdapter:
    """Rust adapter produces same defaults as current hardcoded behavior."""

    def test_rust_commands_match_current_config_template(self) -> None:
        """RustAdapter commands must match what init template currently hardcodes."""
        from forgerwrite_mcp.languages.rust import RustAdapter
        adapter = RustAdapter()
        commands = adapter.get_validation_commands()
        assert commands["fmt"] == "cargo fmt -- --check"
        assert commands["check"] == "cargo check"
        assert commands["test"] == "cargo test"
        assert "clippy" in commands

    def test_rust_default_profile_is_rust_default(self) -> None:
        ...


class TestPythonAdapter:
    """Python adapter for ruff/pytest/mypy profiles."""

    def test_python_commands_include_ruff_pytest_mypy(self) -> None:
        ...

    def test_python_default_profile(self) -> None:
        ...

    def test_python_adapter_registers_in_discovery(self) -> None:
        ...
```

Expected: Tests FAIL (modules don't exist yet).

### Task 2.2 — Add `languages/base.py` with LanguageAdapter Protocol

File: `forgerwrite_mcp/languages/__init__.py` (new)
File: `forgerwrite_mcp/languages/base.py` (new)

```python
"""Language adapter protocol and discovery."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for language-specific defaults and validation profiles.

    Each adapter provides:
    - Validation commands (e.g., cargo check, pytest)
    - Default validation profile name
    - Language-specific config defaults
    """

    @property
    def language(self) -> str: ...

    def get_validation_commands(self) -> dict[str, str]: ...

    def get_default_profile_name(self) -> str: ...

    def get_profiles(self) -> dict[str, list[str]]: ...
```

### Task 2.3 — Add `languages/rust.py`

File: `forgerwrite_mcp/languages/rust.py` (new)

Extract the hardcoded Rust defaults from:
- `cli.py` `_CONFIG_TEMPLATE` (validation.commands and validation.profiles)
- `coordinator.py` `_validate_result()` (hardcoded `"rust_default"` profile name)

```python
class RustAdapter:
    """Rust language defaults — cargo fmt, check, test, clippy."""

    language = "rust"

    def get_validation_commands(self) -> dict[str, str]:
        return {
            "fmt": "cargo fmt -- --check",
            "check": "cargo check",
            "test": "cargo test",
            "clippy": "cargo clippy --all-targets --all-features -- -D warnings",
        }

    def get_default_profile_name(self) -> str:
        return "rust_default"

    def get_profiles(self) -> dict[str, list[str]]:
        return {"rust_default": ["fmt", "check", "test", "clippy"]}
```

### Task 2.4 — Add `languages/python.py`

File: `forgerwrite_mcp/languages/python.py` (new)

```python
class PythonAdapter:
    """Python language defaults — ruff, pytest, mypy."""

    language = "python"

    def get_validation_commands(self) -> dict[str, str]:
        return {
            "lint": "ruff check .",
            "format_check": "ruff format --check .",
            "test": "pytest -q",
            "typecheck": "mypy forgerwrite_mcp/",
        }

    def get_default_profile_name(self) -> str:
        return "python_default"

    def get_profiles(self) -> dict[str, list[str]]:
        return {"python_default": ["lint", "format_check", "test", "typecheck"]}
```

### Task 2.5 — Add adapter discovery

File: `forgerwrite_mcp/languages/__init__.py`

```python
from .base import LanguageAdapter
from .rust import RustAdapter
from .python import PythonAdapter

_ADAPTERS: dict[str, LanguageAdapter] = {}

def _init_adapters() -> None:
    for cls in [RustAdapter, PythonAdapter]:
        a = cls()
        _ADAPTERS[a.language] = a

def get_adapter(language: str) -> LanguageAdapter | None:
    if not _ADAPTERS:
        _init_adapters()
    return _ADAPTERS.get(language)

def list_adapters() -> list[str]:
    if not _ADAPTERS:
        _init_adapters()
    return list(_ADAPTERS.keys())
```

### Task 2.6 — Wire adapter into config template

Update `cli.py` `_CONFIG_TEMPLATE` to use adapter instead of hardcoded commands. The `forgerwrite init --language rust` or `--language python` selects the adapter and populates `[validation.commands]` and `[validation.profiles]` from it.

### Task 2.7 — Regression gate

```bash
uv run pytest tests/ -q
uv run pytest tests/test_language_adapters.py -v
```

All existing Rust tests and acceptance slices must still pass.

### Phase 2 Summary

| File | Action | Lines |
|------|--------|-------|
| `forgerwrite_mcp/languages/__init__.py` | New — adapter discovery | ~30 |
| `forgerwrite_mcp/languages/base.py` | New — LanguageAdapter Protocol | ~25 |
| `forgerwrite_mcp/languages/rust.py` | New — RustAdapter | ~35 |
| `forgerwrite_mcp/languages/python.py` | New — PythonAdapter | ~35 |
| `forgerwrite_mcp/cli.py` | Wire adapter into init template | ~20 changed |
| `tests/test_language_adapters.py` | New — 8-10 tests | ~120 |

**New tests:** 8-10
**Pass budget:** 5-8 agent passes

---

## Phase 3: Python Dogfood ✅

**Goal:** Use ForgeWrite to edit its own Python codebase. 5 successful Python slices.

**Gate:** `docs/acceptance/python_dogfood.md` committed. 5 run summaries saved.

### Precondition
- `.forgerwrite/forgerwrite.toml` set to `language = "python"`
- Python validation profile: ruff, pytest, mypy
- Clean worktree required

### Dogfood Slices

| Slice | Goal | Allowed files | Validation |
|-------|------|---------------|------------|
| P1 | Add adapter tests | `tests/test_language_adapters.py` | python_default |
| P2 | Refactor validation profile config | `forgerwrite_mcp/cli.py` | python_default |
| P3 | Update init template for Python | `forgerwrite_mcp/cli.py` | python_default |
| P4 | Add Python documentation | `docs/configuration.md` | python_default |
| P5 | Fix a real Python bug | TBD (find via ruff/mypy) | python_default |

### Dogfood Procedure Per Slice

1. **DeepSeek writes slice contract** with allowed files and constraints
2. **Scout** is NOT available yet — context builder uses file contents directly
3. **Local model** (OmniCoder 9B) generates operation batch
4. **Schema validator** catches structural errors
5. **Semantic validator** catches scope/size/permission violations
6. **Preview diff** shown
7. **Terminal approval** via `forgerwrite approve`
8. **Apply** + run `python_default` validation profile
9. **Repair loop** if validation fails (up to 2 attempts)
10. **Run summary** saved

### Tasks

1. Set `language = "python"` in `.forgerwrite/forgerwrite.toml`
2. Run Slice P1 (adapter tests)
3. Run Slice P2 (validation profile refactor)
4. Run Slice P3 (init template)
5. Run Slice P4 (Python docs)
6. Identify a real bug via `ruff check` / `mypy` — use as Slice P5
7. Write `docs/acceptance/python_dogfood.md`

**Files:** `docs/acceptance/python_dogfood.md` (new), run artifacts
**Tests:** No new unit tests (acceptance artifacts)
**Pass budget:** 8-15 agent passes

---

## Phase 4: Scout v1 (Descoped) ✅

**Goal:** Add evidence discovery phase before context building. Produce `scout_packet.json` with path:line evidence.

**Gate:** 4 dogfood slices use Scout before generation. Scout produces capped path:line evidence.

### Architecture Decision

Scout does NOT modify `context.py`. It adds a new `ScoutEnrichmentStep` to the coordinator pipeline that runs before `_build_context()`. Context builder stays unchanged. This is Open/Closed: extension via pipeline step, not modification of existing module.

### Task 4.1 — Add `scout_packet.v1` schema

File: `schemas/scout_packet.v1.json` (new)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "forgewrite.scout_packet.v1",
  "title": "Scout Evidence Packet",
  "type": "object",
  "required": ["schema_id", "question", "exact_evidence"],
  "properties": {
    "schema_id": {"const": "forgewrite.scout_packet.v1"},
    "question": {"type": "string", "minLength": 1},
    "retrieval_hits": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["doc_id", "title", "snippet"],
        "properties": {
          "doc_id": {"type": "string"},
          "title": {"type": "string"},
          "snippet": {"type": "string"}
        }
      }
    },
    "exact_evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "line_start", "finding"],
        "properties": {
          "path": {"type": "string"},
          "line_start": {"type": "integer", "minimum": 1},
          "line_end": {"type": "integer", "minimum": 1},
          "finding": {"type": "string"}
        }
      }
    },
    "recommended_allowed_files": {
      "type": "array",
      "items": {"type": "string"}
    },
    "recommended_reads": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "line_start", "line_end", "reason"],
        "properties": {
          "path": {"type": "string"},
          "line_start": {"type": "integer", "minimum": 1},
          "line_end": {"type": "integer", "minimum": 1},
          "reason": {"type": "string"}
        }
      }
    }
  }
}
```

### Task 4.2 — Write failing tests for Scout

File: `tests/test_scout.py` (new)

```python
class TestScoutPacketSchema:
    def test_valid_packet_passes_schema_validation(self) -> None: ...
    def test_missing_exact_evidence_fails(self) -> None: ...
    def test_empty_question_fails(self) -> None: ...
    def test_negative_line_start_fails(self) -> None: ...

class TestSafeGrep:
    def test_rejects_path_outside_repo(self) -> None: ...
    def test_rejects_absolute_path(self) -> None: ...
    def test_skips_binary_files(self) -> None: ...
    def test_respects_max_matches_per_query(self) -> None: ...
    def test_respects_max_total_matches(self) -> None: ...

class TestScoutCoordinator:
    def test_produces_valid_packet(self) -> None: ...
    def test_respects_caps(self) -> None: ...
    def test_turbovec_fallback_when_disabled(self) -> None: ...
```

Expected: All FAIL (modules don't exist).

### Task 4.3 — Add `scout/safe_grep.py`

File: `forgerwrite_mcp/scout/__init__.py` (new)
File: `forgerwrite_mcp/scout/safe_grep.py` (new)

Safe grep wraps `ripgrep` (or Python `re` as fallback) with:
- Path policy enforcement via `paths.safe_resolve_path()`
- Binary file detection and skip
- Per-query match cap
- Total match cap
- Timeout on slow searches

```python
@dataclass
class GrepMatch:
    path: str
    line_number: int
    line_content: str

@dataclass
class GrepResult:
    matches: list[GrepMatch]
    truncated: bool
    queries: int

def safe_grep(
    repo_root: Path,
    queries: list[str],
    *,
    max_matches_per_query: int = 40,
    max_total_matches: int = 200,
    timeout_seconds: float = 10.0,
) -> GrepResult: ...
```

### Task 4.4 — Add `scout/coordinator.py`

File: `forgerwrite_mcp/scout/coordinator.py` (new)

```python
@dataclass
class ScoutPacket:
    schema_id: str = "forgewrite.scout_packet.v1"
    question: str = ""
    retrieval_hits: list[dict] = field(default_factory=list)
    exact_evidence: list[dict] = field(default_factory=list)
    recommended_allowed_files: list[str] = field(default_factory=list)
    recommended_reads: list[dict] = field(default_factory=list)

class ScoutCoordinator:
    """Runs Scout pipeline: TurboVec retrieval → grep evidence → packet."""

    def __init__(self, repo_root: Path, enricher: RagPromptEnricher | None = None): ...

    def scout(self, question: str, allowed_files: list[str]) -> ScoutPacket:
        """Run full Scout pipeline."""
        # 1. TurboVec retrieval (if enricher available)
        # 2. Safe grep on allowed files
        # 3. Normalize evidence (path:line requirement)
        # 4. Build packet
```

### Task 4.5 — Add MCP tools

File: `forgerwrite_mcp/server.py` (+2 tools)

```python
@mcp.tool()
async def fw_scout(question: str, allowed_files: list[str] | None = None) -> dict:
    """Run full Scout pipeline and return evidence packet."""
    ...

@mcp.tool()
async def fw_scout_grep(queries: list[str], allowed_files: list[str] | None = None) -> dict:
    """Bounded grep through ForgeWrite path policy."""
    ...
```

### Task 4.6 — Add Scout step to coordinator pipeline

File: `forgerwrite_mcp/coordinator.py`

Add `_enrich_with_scout()` method that runs before `_build_context()`. Does NOT modify `context.py`.

```python
def _enrich_with_scout(self, handoff: dict, slice_contract: dict) -> None:
    """Run Scout and attach evidence to context packet metadata."""
    if not self._config.scout.enabled:  # future config section
        return
    scout = ScoutCoordinator(self._repo_root, enricher=self._enricher)
    question = handoff.get("description", "")
    allowed = slice_contract.get("allowed_files", [])
    packet = scout.scout(question, allowed)
    write_artifact(self._run_dir, "scout_packet.json", dataclasses.asdict(packet))
    # Merge into context packet metadata
    self._context_packet["_scout"] = dataclasses.asdict(packet)
```

### Task 4.7 — Run 4 dogfood slices using Scout

Use Scout before generation on slices from Phase 3 (or new ones). Verify Scout evidence appears in context packet metadata.

### Phase 4 Summary

| File | Action | Lines |
|------|--------|-------|
| `schemas/scout_packet.v1.json` | New schema | ~60 |
| `forgerwrite_mcp/scout/__init__.py` | New | ~10 |
| `forgerwrite_mcp/scout/safe_grep.py` | New | ~120 |
| `forgerwrite_mcp/scout/coordinator.py` | New | ~100 |
| `forgerwrite_mcp/server.py` | +2 MCP tools | ~50 |
| `forgerwrite_mcp/coordinator.py` | +1 pipeline step | ~25 |
| `tests/test_scout.py` | New — 12-15 tests | ~250 |

**New tests:** 12-15
**Pass budget:** 8-12 agent passes

---

## Phase 5: Model-Assisted Scout ✅

> Tasks 5.5 (comparison report → `docs/acceptance/scout-comparison.md`) and 5.6 (wire `use_model_planner` → `fw_scout` tool + CLI `scout` command) — both complete.

**Goal:** Use local model to plan grep queries and summarize results. Deterministic fallback always.

**Gate:** Model-assisted Scout improves precision vs deterministic on 5 slices. Fallback works when model fails.

### Tasks

1. Write failing tests for model planner output validation
2. Add `scout/planner.py` — calls local model with strict prompt, validates output
3. Add `scout/summarizer.py` — compresses large evidence sets
4. Add deterministic fallback (keyword extraction + broad grep) when model output invalid
5. Write comparison report: deterministic vs model-assisted on 5 slices

### Phase 5 Summary

| File | Action | Lines |
|------|--------|-------|
| `forgerwrite_mcp/scout/planner.py` | New | ~80 |
| `forgerwrite_mcp/scout/summarizer.py` | New | ~60 |
| `forgerwrite_mcp/scout/coordinator.py` | Add model-assisted path | ~30 changed |
| `tests/test_scout.py` | +6-8 model-related tests | ~150 |

**New tests:** 6-8
**Pass budget:** 6-10 agent passes

---

## Phase 6: Saved Work KB ✅

**Goal:** Store reusable patterns from successful runs. TurboVec-indexed. DeepSeek-curated.

**Gate:** 5 promoted entries. 3 recorded usage outcomes. Knowledge search works via TurboVec.

### Tasks

1. Write failing tests for `knowledge_entry.v1` and `knowledge_usage.v1` schemas
2. Add schemas to `schemas/`
3. Write failing tests for KnowledgeStore (create, read, list, deprecate)
4. Add `knowledge/store.py` — file-backed JSON, one file per entry
5. Add `knowledge/promotion.py` — DeepSeek-curated promotion from run artifacts
6. Add `knowledge/usage.py` — success/failure recording
7. Add 5 MCP tools: `fw_knowledge_search`, `fw_knowledge_save_entry`, `fw_knowledge_get_entry`, `fw_knowledge_record_usage`, `fw_knowledge_deprecate_entry`
8. Index promoted entries into TurboVec via existing `RagIndex`
9. Create first 5 entries from ForgeWrite patterns

### Phase 6 Summary

| File | Action | Lines |
|------|--------|-------|
| `schemas/knowledge_entry.v1.json` | New | ~50 |
| `schemas/knowledge_usage.v1.json` | New | ~30 |
| `forgerwrite_mcp/knowledge/__init__.py` | New | ~15 |
| `forgerwrite_mcp/knowledge/store.py` | New | ~120 |
| `forgerwrite_mcp/knowledge/promotion.py` | New | ~70 |
| `forgerwrite_mcp/knowledge/usage.py` | New | ~50 |
| `forgerwrite_mcp/server.py` | +5 MCP tools | ~120 |
| `tests/test_knowledge.py` | New — 15-20 tests | ~350 |

**New tests:** 15-20
**Pass budget:** 8-14 agent passes

---

## Phase 7: Integrations + Release Candidate ✅

**Goal:** MEX, Graphify, Headroom adapters with fail-soft behavior. Finalize docs. Tag RC.

**Gate:** All release gates pass. Fresh install test passes. Acceptance docs current.

**Dogfood approach:** This phase is executed as ForgeWrite slices (D3.1, D3.2) — see `docs/dogfood-plan.md`.

### Tasks

1. Write failing tests for MEX adapter (missing MEX → graceful degradation)
2. Add `integrations/mex_adapter.py`
3. Add `integrations/graphify_adapter.py`
4. Add `integrations/headroom_adapter.py`
5. Add `integrations/__init__.py` with fail-soft behavior for all
6. Finalize README, config docs, MCP docs, design doc
7. Run clean install test from scratch (`pip install .` or `uv sync` in fresh venv)
8. Run full suite: pytest, ruff, mypy
9. Write release notes and known limitations
10. Tag `v0.1.0-rc1`

### Phase 7 Summary

| File | Action | Lines |
|------|--------|-------|
| `forgerwrite_mcp/integrations/__init__.py` | New | ~20 |
| `forgerwrite_mcp/integrations/mex_adapter.py` | New | ~60 |
| `forgerwrite_mcp/integrations/graphify_adapter.py` | New | ~50 |
| `forgerwrite_mcp/integrations/headroom_adapter.py` | New | ~50 |
| `tests/test_integrations.py` | New — 12-15 tests | ~250 |
| Docs, README, release notes | Updated | ~200 |

**New tests:** 12-15
**Pass budget:** 6-10 agent passes

---

## Total Across All Phases

| Phase | Planned | Actual Tests | Files Added | Status |
|-------|---------|-------------|-------------|--------|
| 0 | ~5 | 5 | 1 | ✅ |
| 1 | 0 | 0 | 1 | ✅ |
| 2 | ~10 | 14 | 5 | ✅ |
| 3 | 0 | 0 | 1 | ✅ |
| 4 | ~15 | 15 | 5 | ✅ |
| 5 | ~8 | 11 | 2 | ✅ |
| 6 | ~20 | 26 | 7 | ✅ |
| 7 | ~15 | 16 | 5 | ✅ |
| **Total** | **~73** | **87** | **27** | |

---

## Kill Criteria Between Phases

After every phase, before starting the next:

- [ ] All tests pass (existing + new)
- [ ] `forgerwrite doctor` passes
- [ ] At least one dogfood slice succeeded
- [ ] No regression in Rust acceptance slices (Phase 1 must still pass after Phase 2-7)
- [ ] Phase gate decision: PROCEED / STOP / PIVOT recorded in `.mex/context/decisions.md`
- [ ] `.mex/ROUTER.md` project state updated

---

## Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| GPU VRAM | 12 GB (RTX 3060) | Gemma 4 Q4 ~8GB + embeddings ~600MB = 8.6GB; serialized with LLM |
| LLM + embedding | Serial only | Do not run LLM inference and embedding simultaneously |
| Context window | 256K (Gemma 4) | Scout packet + context must fit |
| Repair budget | 2 attempts | Per `[repair]` config, shared across schema + code repair |
| Scout grep caps | 8 queries × 40 matches = 320 max | Scalable via config |
| Scout read caps | 6 ranges × 160 lines = 960 lines max | Scalable via config |

---

## Validation Checklist (Per Phase)

- [ ] Tests written before implementation (git log order: test commit before impl commit)
- [ ] No module has >1 responsibility (one class, one noun)
- [ ] Existing modules not modified to add behavior (extension via new files/pipeline steps)
- [ ] No hardcoded values without named constant or config field
- [ ] All new MCP tools route through `paths.safe_resolve_path()`
- [ ] All new MCP tools return error envelopes on failure
- [ ] `forgerwrite doctor` covers new subsystems
- [ ] At least one dogfood slice succeeded
- [ ] `.mex/ROUTER.md` updated
- [ ] Run summary artifact saved
