# ForgeWrite — Handoff Plan for DeepSeek Flash Execution

**Handoff date:** 2026-06-13
**Baseline:** `main` @ `56347e0`, 246 tests passing, 0 failures
**Target model:** DeepSeek Flash (or equivalent smaller model)
**Primary contact file:** `docs/implementation-plan.md` (high-level design reference)

---

## HANDOFF PROTOCOL — READ THIS FIRST

### What You Are
You are executing a pre-written implementation plan. Your job is to follow each task exactly as written. Do not design, do not refactor, do not improve. Copy the code as shown, run the test command as shown, and verify it passes.

### Ground Rules

1. **No scope broadening.** If a task says "add one function to `server.py`", add exactly that function. Do not refactor nearby code. Do not "while I'm here" anything.

2. **No test rewriting.** The test code in this document is the test code. Copy it exactly. If it fails, the implementation is wrong — fix the implementation, not the test.

3. **TDD order strictly enforced.** For every task, step 1 is ALWAYS "write the test and verify it FAILS." If the test passes before you write the implementation, something is wrong — stop and report it.

4. **Run the gate after every task.** Each task ends with a specific `uv run pytest` command. Run it. If it fails, fix the implementation before moving on. Do not accumulate failures.

5. **Do not modify these files without explicit permission:**
   - `schemas/operation_batch.v1.json`
   - `forgerwrite_mcp/forge/forge.py`
   - `forgerwrite_mcp/paths.py`
   - `forgerwrite_mcp/approval.py`
   - `forgerwrite_mcp/contracts/registry.py`
   - `forgerwrite_mcp/validation/semantic.py` (existing rules only)

6. **If you encounter an error not described in this plan**, stop and report it. Do not guess at fixes.

7. **After every task completion**, report: files changed, test count before/after, any deviations.

### Project Commands

```bash
# Activate venv
source /home/eric/projects/forgewrite_mcp/.venv/bin/activate

# Run all tests
uv run pytest tests/ -q

# Run specific test file
uv run pytest tests/test_coordinator.py -v

# Run specific test
uv run pytest tests/validation/test_semantic.py -k "permission_rule" -v

# Lint
uv run ruff check forgerwrite_mcp/ tests/

# Type check
uv run mypy forgerwrite_mcp/

# All gates
uv run ruff check forgerwrite_mcp/ tests/ && uv run mypy forgerwrite_mcp/ && uv run pytest tests/ -q
```

### Key Project Patterns

- **Error handling:** Every MCP tool wraps body in `try/except` and returns `envelope_from(exc, "tool_name").to_dict()`
- **Path safety:** All file paths go through `forgerwrite_mcp.paths.safe_resolve_path()` — never use `Path(...)` directly for file access
- **Config:** Loaded via `load_config(Path.cwd())`, returns `ForgerWriteConfig` Pydantic model
- **Artifacts:** Written via `write_artifact(run_dir, "name.json", data)` from `forgerwrite_mcp.artifacts`
- **Tests:** Use `tmp_path` fixture, `FakeLocalModelBackend`, and `_init_repo()` helper from existing tests

---

## PHASE 0: Stabilize Core & Naming

**Goal:** Close PV1/PV2 bugs, add naming ADR, add TurboVec MCP tools, RAG health in doctor.
**Gate:** 251+ tests passing. `forgerwrite doctor` shows RAG health.

---

### Task 0.1 — Verify PV1 (PermissionRule reads config)

PV1 is listed as debt but code inspection suggests it's already fixed. Verify this.

**Command:**
```bash
uv run pytest tests/validation/test_semantic.py -k "permission_rule_reads_config" -v
```

**If both tests pass:** PV1 is resolved. Document in `.mex/ROUTER.md` under "Known issues" → strike PV1. No code changes needed.

**If tests fail:** Report the exact failure. Do not fix — this plan doesn't cover PV1 repair because inspection shows it's already done.

**Expected output:** 2 passed.

---

### Task 0.2 — Fix PV2 (async-safe coordinator)

**Problem:** `SliceCoordinator.run()` uses `asyncio.run()` which fails when called from inside an async event loop (e.g., async MCP tools).

**Step 1: Write the failing test**

Open `tests/test_coordinator.py`. Find the class `TestSliceCoordinator`. After the last test method (currently `test_preview_captures_new_files`), add this test:

```python
    def test_run_in_async_context_succeeds(
        self, coordinator: object, tmp_path: Path
    ) -> None:
        """Coordinator.run() works when called from inside an async event loop.

        PV2: asyncio.run() fails with RuntimeError when an event loop is
        already running. run() must be safe to call from async MCP tools.
        """
        import asyncio
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        handoff = {
            "schema_id": "forgerwrite.handoff.v1",
            "project": "test",
            "language": "rust",
        }
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["src/generated.rs"],
        }

        async def call_run() -> object:
            return coord.run(handoff, slice_contract)

        # This MUST NOT raise RuntimeError("asyncio.run() cannot be called from a running event loop")
        outcome = asyncio.run(call_run())
        assert outcome.run_dir is not None
```

Run to confirm it FAILS:
```bash
uv run pytest tests/test_coordinator.py::TestSliceCoordinator::test_run_in_async_context_succeeds -v
```

Expected: `RuntimeError: asyncio.run() cannot be called from a running event loop` (or similar).

**Step 2: Add `run_async()` method to coordinator**

Open `forgerwrite_mcp/coordinator.py`. Find the `run()` method (starts around line 95 with `def run(self, handoff: dict[str, Any], slice_contract: dict[str, Any]) -> RunOutcome:`).

Read the ENTIRE `run()` method body — from `def run(...)` to the final `return RunOutcome(...)`. You will replicate this logic in `run_async()`.

After the closing of `run()` (which ends with `return RunOutcome(run_id=..., status=..., run_dir=...)`), add this new method:

```python
    async def run_async(
        self, handoff: dict[str, Any], slice_contract: dict[str, Any]
    ) -> RunOutcome:
        """Async-safe entrypoint. Use this when called from within an event loop.

        Identical logic to run() but uses ``await`` instead of ``asyncio.run()``
        for async calls. The sync run() delegates to this method.
        """
        import asyncio as _asyncio

        self._run_id = generate_run_id()
        self._run_dir = init_run_dir(self._run_id, base_dir=self._repo_root)
        self._slice_id = slice_contract.get("slice_id", "unknown")
        status = _STATUS_DRAFT

        try:
            status = self._validate_contracts(handoff, slice_contract)
            status = self._build_context(handoff, slice_contract)
            # Generate + schema-validate with retry on schema/semantic errors
            status = await self._generate_with_schema_repair(handoff, slice_contract)
            if status != _STATUS_OPS_SEMANTIC_VALID:
                write_dead_letter(
                    self._run_dir,
                    f"Schema repair exhausted at status {status}",
                )
                return RunOutcome(
                    run_id=self._run_id,
                    status=status,
                    run_dir=self._run_dir,
                    errors=[
                        f"Schema/semantic validation failed after repair: {status}"
                    ],
                )
            status = self._preview(slice_contract)
            status = self._await_approval()
            if status == _STATUS_APPROVED:
                status = self._apply(slice_contract)
                if status == _STATUS_APPLIED:
                    from .audit import write_audit_event

                    write_audit_event(self._run_dir, "apply", {"run_id": self._run_id})
                    status = self._validate_result()
                    if status == _STATUS_VALIDATION_PASSED:
                        cleanup_snapshot(self._repo_root, self._run_id)
                    elif status == _STATUS_VALIDATION_FAILED:
                        status = await self._maybe_repair_async(slice_contract)
        except Exception as exc:
            write_dead_letter(self._run_dir, str(exc))
            return RunOutcome(
                run_id=self._run_id,
                status=status,
                run_dir=self._run_dir,
                errors=[str(exc)],
            )
        finally:
            self._record(status)

        return RunOutcome(
            run_id=self._run_id, status=status, run_dir=self._run_dir
        )
```

Now refactor `run()` to delegate to `run_async()`. Replace the ENTIRE body of `run()` (from `self._run_id = generate_run_id()` through the final `return`) with:

```python
    def run(
        self, handoff: dict[str, Any], slice_contract: dict[str, Any]
    ) -> RunOutcome:
        """Sync entrypoint. Delegates to :meth:`run_async`."""
        import asyncio
        return asyncio.run(self.run_async(handoff, slice_contract))
```

**Step 3: Add `_maybe_repair_async()`**

The existing `_maybe_repair()` method uses `asyncio.run()` internally for model calls. We need an async version. Find `_maybe_repair()` in `coordinator.py`. After it, add:

```python
    async def _maybe_repair_async(self, slice_contract: dict) -> str:
        """Async version of _maybe_repair. Uses await instead of asyncio.run."""
        repair = RepairCoordinator(config=self._config.repair)

        validation_path = self._run_dir / "validation_result.json"
        if validation_path.exists():
            validation_result = json.loads(validation_path.read_text(encoding="utf-8"))
        else:
            validation_result = {"passed": False, "commands": []}

        while True:
            result = repair.attempt(validation_result, slice_contract)
            if result is None:
                self._restore_apply_snapshot()
                return _STATUS_VALIDATION_FAILED

            prompt, _remaining = result
            attempt_n = repair.attempt_count

            if self._enricher is not None and self._operation_batch is not None:
                repair_query = json.dumps(validation_result) + " " + json.dumps(
                    self._operation_batch
                )
                prompt = self._enricher.enrich(
                    base_prompt=prompt,
                    query=repair_query,
                    k=self._config.rag.k_documents,
                )

            write_artifact(
                self._run_dir,
                f"repair_prompt_{attempt_n}.txt",
                {"prompt": prompt},
            )

            try:
                # Use await instead of asyncio.run
                system_prompt = (
                    "You are a coding assistant that produces structured JSON "
                    "operation batches.\n\n"
                    "Respond ONLY with a JSON object matching the operation_batch schema."
                )
                raw = await self._backend.generate_operation_batch(
                    system_prompt, prompt, self._operation_batch_schema
                )
                write_artifact(
                    self._run_dir,
                    f"repair_raw_{attempt_n}.txt",
                    {"raw": raw},
                )
                self._operation_batch = json.loads(raw)
                write_artifact(
                    self._run_dir,
                    f"operation_batch_repair_{attempt_n}.json",
                    self._operation_batch,
                )
            except Exception as exc:
                write_dead_letter(
                    self._run_dir,
                    f"Repair attempt {attempt_n} failed: {exc}",
                )
                continue

            try:
                self._contract_registry.validate(
                    "operation_batch.v1.json", self._operation_batch
                )
                validator = default_validator()
                validator.validate(
                    self._operation_batch,
                    slice_contract,
                    limits=self._config.limits,
                    permissions=self._config.permissions,
                )
            except Exception:
                continue

            self._preview(slice_contract)
            self._apply(slice_contract)
            status = self._validate_result()
            if status == _STATUS_VALIDATION_PASSED:
                cleanup_snapshot(self._repo_root, self._run_id)
                return _STATUS_VALIDATION_PASSED
```

**Step 4: Run the test**

```bash
uv run pytest tests/test_coordinator.py::TestSliceCoordinator::test_run_in_async_context_succeeds -v
```

Expected: PASS.

**Step 5: Run full coordinator regression**

```bash
uv run pytest tests/test_coordinator.py -v
```

Expected: ALL tests pass (12 total: 11 existing + 1 new).

**Files changed:**
- `forgerwrite_mcp/coordinator.py` — `run()` refactored, `run_async()` added, `_maybe_repair_async()` added
- `tests/test_coordinator.py` — `test_run_in_async_context_succeeds` added

**Test count:** +1

---

### Task 0.3 — Naming ADR

**Step 1: Create the ADR**

Create file `docs/adr/0001-naming.md`:

```markdown
# ADR-0001: Public Name is ForgeWrite

**Status:** Accepted
**Date:** 2026-06-13

## Decision

The public product name is **ForgeWrite**. The internal Python package
`forgerwrite_mcp/` will be renamed to `forgewrite_mcp/` in a future
ADR when import-compatibility concerns are resolved.

## Scope

- README, docstrings, CLI help text, MCP tool descriptions: "ForgeWrite"
- Config directory `.forgerwrite/`: stays for now
- Python package `forgerwrite_mcp/`: stays for now
- CLI binary `forgerwrite`: stays for now

## Rationale

"Write" is cleaner English than "Write" when spoken aloud. The extra "r"
in "ForgerWrite" was a typo that stuck. Fixing it now prevents 9 phases
of documentation drift.

## Known Technical Debt (documented, not fixed in this ADR)

- RAG enrichment is duplicated in `fw_generate_operations_local` (server.py)
  and `SliceCoordinator._generate_operations()` (coordinator.py). The
  coordinator already accepts an `enricher` parameter. The server tool's
  direct enrichment path should be merged into the coordinator in Phase 3.
```

**Step 2: Update user-facing strings**

These are string-only changes. Do not change any logic, imports, or function signatures.

In `README.md`:
- Find: `# ForgerWrite MCP`
- Replace with: `# ForgeWrite MCP`
- Find any other "ForgerWrite" in prose, replace with "ForgeWrite"
- Do NOT change `forgerwrite` in code blocks (that's the CLI command name)

In `docs/project-state.md`:
- Line 1: `# ForgerWrite MCP — Project State` → `# ForgeWrite MCP — Project State`
- Any other "ForgerWrite" in prose → "ForgeWrite"

In `forgerwrite_mcp/server.py`:
- Line ~5: docstring `"""MCP server — FastMCP stdio server with 10 thin tools.` → `"""ForgeWrite MCP server — FastMCP stdio server with 10 thin tools.`
- Do NOT change `FastMCP("forgerwrite")` (that's the MCP service name)

In `forgerwrite_mcp/cli.py`:
- Line ~20: `help="Local-first MCP coding service CLI."` → `help="ForgeWrite — local-first MCP coding service CLI."`

In `.github/copilot-instructions.md`:
- `# [Project Name]` → `# ForgeWrite`
- Update the "What This Is" description

**Files changed:**
- `docs/adr/0001-naming.md` (new)
- `README.md`, `docs/project-state.md`, `forgerwrite_mcp/server.py`, `forgerwrite_mcp/cli.py`, `.github/copilot-instructions.md` (string-only)

**Tests:** No new tests needed.

---

### Task 0.4 — Add `fw_turbovec_health` MCP tool

**Step 1: Write the test**

Open `tests/rag/test_integration.py`. At the end of the file, add:

```python
class TestTurbovecHealthTool:
    """Tests for fw_turbovec_health MCP tool."""

    def test_health_reports_index_not_found_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When RAG index doesn't exist, health reports healthy=False."""
        import json
        from pathlib import Path as _Path

        # Point CWD to tmp_path so .forgerwrite/forgerwrite.toml doesn't interfere
        monkeypatch.chdir(tmp_path)

        # Create minimal config with rag enabled but index pointing nowhere
        config_dir = tmp_path / ".forgerwrite"
        config_dir.mkdir()
        config_file = config_dir / "forgerwrite.toml"
        config_file.write_text("""\
[project]
name = "test"
language = "rust"
repo_root = "."

[local_model]
endpoint = "http://127.0.0.1:8080/v1"
model = "test"

[validation]
commands = {}
profiles = {}

[permissions]

[hygiene]

[repair]

[rag]
enabled = true
index_path = "nonexistent.tqi"
""")

        # Import the tool function
        from forgerwrite_mcp.server import fw_turbovec_health

        # We need to run the async tool. Use asyncio.run.
        import asyncio

        result = asyncio.run(fw_turbovec_health())
        assert result["ok"] is True
        assert result["healthy"] is False
        assert "not found" in result["reason"].lower()

    def test_health_reports_healthy_when_index_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When RAG index exists, health reports healthy=True with doc count."""
        import asyncio
        from pathlib import Path as _Path

        # Build a small index in tmp_path
        from forgerwrite_mcp.rag.preprocessor import DocumentPreprocessor
        from forgerwrite_mcp.rag.index import RagIndex
        from forgerwrite_mcp.rag.retriever import RagDocument

        # Create a tiny KB file
        kb_dir = tmp_path / "data" / "rag"
        kb_dir.mkdir(parents=True)
        kb_file = kb_dir / "test_kb.md"
        kb_file.write_text("""### Test Doc

Some knowledge content.
""")

        processor = DocumentPreprocessor(source="test")
        docs = processor.process_file(str(kb_file))

        index_path = tmp_path / "test_index.tqi"
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)
        index.save(str(index_path))

        # Create config pointing to this index
        config_dir = tmp_path / ".forgerwrite"
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "forgerwrite.toml"
        config_file.write_text(f"""\
[project]
name = "test"
language = "rust"
repo_root = "."

[local_model]
endpoint = "http://127.0.0.1:8080/v1"
model = "test"

[validation]
commands = {{}}
profiles = {{}}

[permissions]

[hygiene]

[repair]

[rag]
enabled = true
index_path = "{index_path.relative_to(tmp_path)}"
""")

        monkeypatch.chdir(tmp_path)

        from forgerwrite_mcp.server import fw_turbovec_health

        result = asyncio.run(fw_turbovec_health())
        assert result["ok"] is True
        assert result["healthy"] is True
        assert result["document_count"] >= 1
```

Run to confirm it FAILS:
```bash
uv run pytest tests/rag/test_integration.py::TestTurbovecHealthTool -v
```

Expected: `AttributeError` or `ImportError` — `fw_turbovec_health` doesn't exist yet.

**Step 2: Add the MCP tool**

Open `forgerwrite_mcp/server.py`. Find the `fw_get_run_summary` tool registration (it's the last tool, around line 220-230). After its closing, and before the `# ── Start server ──` comment (around line 235), add:

```python
    @mcp.tool()
    async def fw_turbovec_health() -> dict:
        """Report TurboVec / RAG retrieval system health.

        Checks index file presence, document count, and basic integrity.
        Returns healthy=False with reason when index is missing.
        """
        try:
            from .config import load_config

            config = load_config(Path.cwd())
            index_path = Path.cwd() / config.rag.index_path

            if not config.rag.enabled:
                return {
                    "ok": True,
                    "healthy": False,
                    "reason": "RAG is disabled in config",
                }

            if not index_path.exists():
                return {
                    "ok": True,
                    "healthy": False,
                    "reason": f"Index not found at {config.rag.index_path}. "
                              f"Run: forgerwrite build-index",
                }

            from .rag.index import RagIndex

            idx = RagIndex.load(str(index_path))
            doc_count = len(idx.documents) if idx.documents else 0

            return {
                "ok": True,
                "healthy": True,
                "document_count": doc_count,
                "index_path": str(index_path),
            }
        except Exception as exc:
            return envelope_from(exc, "turbovec_health").to_dict()
```

**Step 3: Run the test**

```bash
uv run pytest tests/rag/test_integration.py::TestTurbovecHealthTool -v
```

Expected: 2 passed.

If the first test (`test_health_reports_index_not_found`) fails because the test's TOML config is missing required fields (`[limits]`), add the missing sections to the test TOML string. The `ForgerWriteConfig` model has defaults for `[limits]`, `[repair]`, and `[rag]`, so they should be optional — if Pydantic rejects them, add:

```toml
[limits]
[repair]
```

to the test config strings.

**Files changed:**
- `forgerwrite_mcp/server.py` — `fw_turbovec_health` tool added
- `tests/rag/test_integration.py` — `TestTurbovecHealthTool` class added

**Test count:** +2

---

### Task 0.5 — Add `fw_turbovec_index` MCP tool

**Step 1: Write the test**

Open `tests/rag/test_integration.py`. After the `TestTurbovecHealthTool` class, add:

```python
class TestTurbovecIndexTool:
    """Tests for fw_turbovec_index MCP tool."""

    def test_index_builds_from_kb_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """fw_turbovec_index builds an index from KB markdown files."""
        import asyncio
        from pathlib import Path as _Path

        # Create a KB file
        kb_dir = tmp_path / "data" / "rag"
        kb_dir.mkdir(parents=True)
        kb_file = kb_dir / "test_kb.md"
        kb_file.write_text("""### Test Knowledge Entry

Some reusable pattern for testing.
""")

        index_path = tmp_path / "output.tqi"

        # Create minimal config
        config_dir = tmp_path / ".forgerwrite"
        config_dir.mkdir()
        config_file = config_dir / "forgerwrite.toml"
        config_file.write_text(f"""\
[project]
name = "test"
language = "rust"
repo_root = "."

[local_model]
endpoint = "http://127.0.0.1:8080/v1"
model = "test"

[validation]
commands = {{}}
profiles = {{}}

[permissions]

[hygiene]

[repair]

[rag]
enabled = true
index_path = "{index_path.relative_to(tmp_path)}"
""")

        monkeypatch.chdir(tmp_path)

        from forgerwrite_mcp.server import fw_turbovec_index

        result = asyncio.run(fw_turbovec_index(
            kb_dir=str(kb_dir.relative_to(tmp_path)),
            index_path=str(index_path.relative_to(tmp_path)),
        ))
        assert result["ok"] is True
        assert result["indexed"] >= 1
        assert index_path.exists()
```

Run to confirm it FAILS:
```bash
uv run pytest tests/rag/test_integration.py::TestTurbovecIndexTool -v
```

**Step 2: Add the MCP tool**

Open `forgerwrite_mcp/server.py`. After the `fw_turbovec_health` tool you just added, add:

```python
    @mcp.tool()
    async def fw_turbovec_index(
        kb_dir: str = "data/rag",
        index_path: str = "data/rag/index.tqi",
    ) -> dict:
        """Build (or rebuild) the TurboVec retrieval index.

        Processes all markdown knowledge base files in kb_dir, embeds them
        with gte-modernbert-base, and writes a TurboQuantIndex to index_path.
        """
        try:
            from .rag import build_rag_index

            index = build_rag_index(kb_dir=kb_dir, index_path=index_path)
            doc_count = len(index.documents) if index.documents else 0
            return {
                "ok": True,
                "indexed": doc_count,
                "index_path": index_path,
            }
        except Exception as exc:
            return envelope_from(exc, "turbovec_index").to_dict()
```

**Step 3: Run the test**

```bash
uv run pytest tests/rag/test_integration.py::TestTurbovecIndexTool -v
```

Expected: 1 passed.

**Files changed:**
- `forgerwrite_mcp/server.py` — `fw_turbovec_index` tool added
- `tests/rag/test_integration.py` — `TestTurbovecIndexTool` class added

**Test count:** +1

---

### Task 0.6 — Add RAG index check to `forgerwrite doctor`

**Step 1: Understand the existing doctor**

Read `forgerwrite_mcp/doctor.py`. Find the function `run_doctor_checks()`. It returns a dict with a `"checks"` list, where each check is `{"check": "...", "status": "ok|warning|error", "detail": "..."}`. You will add one more check to this list.

**Step 2: Add the check function**

Open `forgerwrite_mcp/doctor.py`. After the last existing check function, add:

```python
def _check_rag(project_root: Path) -> dict[str, object]:
    """Check RAG index presence and sentence-transformers availability."""
    try:
        from .config import load_config

        config = load_config(project_root)

        if not config.rag.enabled:
            return {
                "check": "rag",
                "status": "ok",
                "detail": "RAG is disabled (set [rag] enabled = true to enable)",
            }

        index_path = project_root / config.rag.index_path
        index_ok = index_path.exists()

        try:
            import sentence_transformers  # noqa: F401
            st_ok = True
        except ImportError:
            st_ok = False

        if index_ok and st_ok:
            return {
                "check": "rag",
                "status": "ok",
                "detail": f"Index: {config.rag.index_path}, "
                          f"model: {config.rag.embedding_model_name}",
            }

        problems = []
        if not index_ok:
            problems.append(
                f"Index not found at {config.rag.index_path}. "
                f"Run: forgerwrite build-index"
            )
        if not st_ok:
            problems.append("sentence-transformers not installed")

        return {
            "check": "rag",
            "status": "warning",
            "detail": "; ".join(problems),
        }
    except Exception as exc:
        return {
            "check": "rag",
            "status": "error",
            "detail": str(exc),
        }
```

Now find `run_doctor_checks()`. It builds a list of checks. Find where the list is assembled (look for something like `checks = [...]` or `checks.append(...)`). Add your new check:

```python
    checks.append(_check_rag(project_root))
```

**Step 3: Write the test**

Open `tests/test_cli.py`. Find the doctor-related tests. Add:

```python
def test_doctor_includes_rag_check(self) -> None:
    """Doctor output includes RAG index health check."""
    import json
    from pathlib import Path as _Path
    from forgerwrite_mcp.doctor import run_doctor_checks

    # Run doctor against the real project root
    result = run_doctor_checks(_Path.cwd())
    checks = result.get("checks", [])

    rag_checks = [c for c in checks if c["check"] == "rag"]
    assert len(rag_checks) == 1, f"Expected 1 rag check, got {len(rag_checks)}"
    assert rag_checks[0]["status"] in ("ok", "warning", "error")
```

Run to verify:
```bash
uv run pytest tests/test_cli.py::test_doctor_includes_rag_check -v
```

**Files changed:**
- `forgerwrite_mcp/doctor.py` — `_check_rag()` added, wired into `run_doctor_checks()`
- `tests/test_cli.py` — `test_doctor_includes_rag_check` added

**Test count:** +1

---

### Task 0.7 — Phase 0 Regression Gate

Run all gates:

```bash
uv run ruff check forgerwrite_mcp/ tests/
uv run mypy forgerwrite_mcp/
uv run pytest tests/ -q
```

Expected: All clean. ~251 tests passing (246 + 5 new from Phase 0).

**Phase 0 complete when:**
- [ ] PV1 verified (2 tests pass)
- [ ] PV2 fixed (`test_run_in_async_context_succeeds` passes)
- [ ] Naming ADR committed
- [ ] `fw_turbovec_health` tool + 2 tests pass
- [ ] `fw_turbovec_index` tool + 1 test passes
- [ ] Doctor RAG check + 1 test passes
- [ ] Full regression: ruff, mypy, pytest all green

---

## PHASE 1: Rust MVP Acceptance

**Precondition:** Phase 0 complete. OmniCoder 9B running at `http://127.0.0.1:8080/v1`.

**Goal:** 3 formal Rust end-to-end slices through the full pipeline.

**Warning:** This phase requires a live local model. Tests will fail if the llama.cpp server is not running.

### Slice R1 — Create Rust CLI Project

**Step 1: Create test project directory**

```bash
mkdir -p /tmp/forgewrite-r1
cd /tmp/forgewrite-r1
git init
git config user.email "test@test.com"
git config user.name "Test"
forgerwrite init
```

Edit `/tmp/forgewrite-r1/.forgerwrite/forgerwrite.toml`:
- Set `[rag] enabled = false` (no RAG needed for basic Rust)
- Set `[permissions] require_clean_worktree = false` (we're in a temp dir)

Commit the initial state:
```bash
git add -A && git commit -m "init"
```

**Step 2: Run the slice**

Use the MCP server or coordinator directly:

```python
# Save as /tmp/run_r1.py
import asyncio, json
from pathlib import Path
from forgerwrite_mcp.config import load_config
from forgerwrite_mcp.coordinator import SliceCoordinator
from forgerwrite_mcp.operations.registry import default_registry
from forgerwrite_mcp.llama_client import LlamaCppClient

async def main():
    config = load_config(Path("/tmp/forgewrite-r1"))
    client = LlamaCppClient.from_config(config.local_model)
    coord = SliceCoordinator(
        repo_root=Path("/tmp/forgewrite-r1"),
        config=config,
        registry=default_registry(),
        backend=client,
        auto_approve=True,
    )
    handoff = {
        "schema_id": "forgerwrite.handoff.v1",
        "project": "forgewrite-r1",
        "language": "rust",
        "description": "Create a minimal Rust CLI project that parses one flag using clap",
    }
    slice_contract = {
        "schema_id": "forgerwrite.slice.v1",
        "slice_id": "r1-create-cli",
        "allowed_files": ["src/main.rs", "Cargo.toml"],
        "validation_profile": "rust_default",
    }
    outcome = await coord.run_async(handoff, slice_contract)
    print(f"Status: {outcome.status}")
    print(f"Run dir: {outcome.run_dir}")

asyncio.run(main())
```

```bash
cd /tmp/forgewrite-r1
uv run python /tmp/run_r1.py
```

**Step 3: Verify**

```bash
cd /tmp/forgewrite-r1
cargo build
cargo test
cargo clippy --all-targets --all-features -- -D warnings
cargo fmt -- --check
```

All must pass.

### Slice R2 — Add Failing Test + Fix

**Step 1: Create buggy project**

```bash
mkdir -p /tmp/forgewrite-r2
cd /tmp/forgewrite-r2
cargo init
```

Create `src/lib.rs` with:
```rust
/// Returns the sum of two numbers plus one (BUG: should just return sum)
pub fn add(a: i32, b: i32) -> i32 {
    a + b + 1
}

#[cfg(test)]
mod tests {
    // BUG: no test for add() — the model must add one
}
```

```bash
git init && git add -A && git commit -m "init with bug"
forgerwrite init
```

**Step 2: Run the slice**

Slice contract:
```json
{
  "slice_id": "r2-fix-bug",
  "allowed_files": ["src/lib.rs"],
  "validation_profile": "rust_default"
}
```

Handoff description: "The add() function in src/lib.rs returns a + b + 1 but should return a + b. Add a test that exposes this bug, then fix the function."

**Step 3: Verify**

- `cargo test` passes (the new test must fail before the fix and pass after)
- Verify operation batch order: test added BEFORE function fix

### Slice R3 — Refactor Without Behavior Change

**Step 1: Create project**

```bash
mkdir -p /tmp/forgewrite-r3
cd /tmp/forgewrite-r3
cargo init
```

Create `src/lib.rs` with a module that has a long function (50+ lines). The model should extract a helper function.

**Step 2: Run the slice**

Slice contract:
```json
{
  "slice_id": "r3-refactor",
  "allowed_files": ["src/lib.rs"],
  "validation_profile": "rust_default"
}
```

**Step 3: Verify**

- All existing tests pass
- `cargo clippy` passes
- No new public API surface (or minimal)

### Tasks

1. Run R1, R2, R3
2. Exercise repair loop at least once (R2 is best — the model might fix without adding test first)
3. Write `docs/acceptance/rust.md`:

```markdown
# Rust MVP Acceptance Report

**Date:** 2026-06-13
**Model:** OmniCoder 9B Q8_0
**Baseline:** main @ 56347e0

## Slice R1: Create CLI Project
- Status: PASS/FAIL
- Run ID: ...
- Notes: ...

## Slice R2: Bug Fix
- Status: PASS/FAIL
- Run ID: ...
- Repair exercised: YES/NO
- Notes: ...

## Slice R3: Refactor
- Status: PASS/FAIL
- Run ID: ...
- Notes: ...

## Summary
- 3/3 slices passed (or X/3)
- Repair loop: exercised Y times
- Model quality: ...
```

**Files:** `docs/acceptance/rust.md` (new), run artifacts
**Tests:** Acceptance artifacts only

---

## PHASE 2: Language Adapter Seam

**Goal:** Extract Rust defaults into `RustAdapter`, add `PythonAdapter`. No behavior change for Rust.

**Gate:** All existing tests pass. `tests/test_language_adapters.py` passes (8-10 tests).

### Task 2.1 — Write all tests FIRST

Create `tests/test_language_adapters.py`:

```python
"""Tests for the LanguageAdapter protocol and built-in adapters."""

from __future__ import annotations

import pytest


# ── Protocol contract tests ─────────────────────────────────────────────────

class TestLanguageAdapterProtocol:
    """Every LanguageAdapter must satisfy this contract."""

    def test_rust_adapter_satisfies_protocol(self) -> None:
        """RustAdapter implements the LanguageAdapter protocol."""
        from forgerwrite_mcp.languages.base import LanguageAdapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        assert isinstance(adapter, LanguageAdapter)

    def test_python_adapter_satisfies_protocol(self) -> None:
        """PythonAdapter implements the LanguageAdapter protocol."""
        from forgerwrite_mcp.languages.base import LanguageAdapter
        from forgerwrite_mcp.languages.python import PythonAdapter

        adapter = PythonAdapter()
        assert isinstance(adapter, LanguageAdapter)

    def test_adapter_exposes_language_property(self) -> None:
        """Every adapter has a language string property."""
        from forgerwrite_mcp.languages.rust import RustAdapter
        from forgerwrite_mcp.languages.python import PythonAdapter

        assert RustAdapter().language == "rust"
        assert PythonAdapter().language == "python"

    def test_adapter_exposes_validation_commands(self) -> None:
        """Every adapter returns a non-empty dict of command_id -> shell command."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        commands = adapter.get_validation_commands()
        assert isinstance(commands, dict)
        assert len(commands) > 0
        for cmd_id, cmd_str in commands.items():
            assert isinstance(cmd_id, str)
            assert isinstance(cmd_str, str)
            assert len(cmd_str) > 0

    def test_adapter_exposes_default_profile(self) -> None:
        """Every adapter returns a default validation profile name string."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        name = adapter.get_default_profile_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_adapter_profiles_reference_valid_commands(self) -> None:
        """Every profile must only reference command IDs that exist in commands."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        commands = adapter.get_validation_commands()
        profiles = adapter.get_profiles()

        for profile_name, cmd_ids in profiles.items():
            for cid in cmd_ids:
                assert cid in commands, (
                    f"Profile '{profile_name}' references unknown command '{cid}'"
                )


# ── RustAdapter tests ───────────────────────────────────────────────────────

class TestRustAdapter:
    """RustAdapter produces same defaults as current hardcoded behavior."""

    def test_rust_commands_match_current_config_template(self) -> None:
        """RustAdapter commands match what init template hardcodes."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        commands = adapter.get_validation_commands()

        assert commands["fmt"] == "cargo fmt -- --check"
        assert commands["check"] == "cargo check"
        assert commands["test"] == "cargo test"
        assert "clippy" in commands
        assert "cargo clippy" in commands["clippy"]

    def test_rust_default_profile_name(self) -> None:
        """Rust default profile is named 'rust_default'."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        assert adapter.get_default_profile_name() == "rust_default"

    def test_rust_profiles_include_rust_default(self) -> None:
        """Rust profiles dict contains rust_default with all commands."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        profiles = adapter.get_profiles()
        assert "rust_default" in profiles
        assert set(profiles["rust_default"]) == {"fmt", "check", "test", "clippy"}


# ── PythonAdapter tests ─────────────────────────────────────────────────────

class TestPythonAdapter:
    """PythonAdapter for ruff/pytest/mypy profiles."""

    def test_python_commands_include_ruff_pytest_mypy(self) -> None:
        """PythonAdapter has lint, format_check, test, typecheck commands."""
        from forgerwrite_mcp.languages.python import PythonAdapter

        adapter = PythonAdapter()
        commands = adapter.get_validation_commands()

        assert "lint" in commands
        assert "ruff" in commands["lint"]
        assert "format_check" in commands
        assert "ruff format" in commands["format_check"]
        assert "test" in commands
        assert "pytest" in commands["test"]
        assert "typecheck" in commands
        assert "mypy" in commands["typecheck"]

    def test_python_default_profile_name(self) -> None:
        """Python default profile is named 'python_default'."""
        from forgerwrite_mcp.languages.python import PythonAdapter

        adapter = PythonAdapter()
        assert adapter.get_default_profile_name() == "python_default"

    def test_python_adapter_registers_in_discovery(self) -> None:
        """PythonAdapter appears in list_adapters()."""
        from forgerwrite_mcp.languages import list_adapters

        adapters = list_adapters()
        assert "python" in adapters
```

Run to confirm all FAIL:
```bash
uv run pytest tests/test_language_adapters.py -v
```

Expected: 11 failures (ImportError — modules don't exist).

### Task 2.2 — Create `languages/base.py`

Create `forgerwrite_mcp/languages/__init__.py`:

```python
"""Language adapter discovery and registration."""

from __future__ import annotations

from .base import LanguageAdapter
from .rust import RustAdapter
from .python import PythonAdapter

__all__ = ["LanguageAdapter", "RustAdapter", "PythonAdapter", "get_adapter", "list_adapters"]

_ADAPTERS: dict[str, LanguageAdapter] = {}
_INITIALIZED: bool = False


def _init_adapters() -> None:
    """Lazy-init the adapter registry."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    for cls in [RustAdapter, PythonAdapter]:
        a = cls()
        _ADAPTERS[a.language] = a
    _INITIALIZED = True


def get_adapter(language: str) -> LanguageAdapter | None:
    """Get the adapter for a language, or None if not supported."""
    if not _INITIALIZED:
        _init_adapters()
    return _ADAPTERS.get(language)


def list_adapters() -> list[str]:
    """List all supported language IDs."""
    if not _INITIALIZED:
        _init_adapters()
    return list(_ADAPTERS.keys())
```

Create `forgerwrite_mcp/languages/base.py`:

```python
"""LanguageAdapter Protocol — contract for language-specific defaults."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for language-specific validation and defaults.

    Each adapter provides validation commands, a default profile name,
    and profile definitions that map to those commands.
    """

    @property
    def language(self) -> str:
        """The language identifier (e.g., 'rust', 'python')."""
        ...

    def get_validation_commands(self) -> dict[str, str]:
        """Return {command_id: shell_command} for validation profiles."""
        ...

    def get_default_profile_name(self) -> str:
        """Return the default validation profile name."""
        ...

    def get_profiles(self) -> dict[str, list[str]]:
        """Return {profile_name: [command_id, ...]} mapping."""
        ...
```

### Task 2.3 — Create `languages/rust.py`

Create `forgerwrite_mcp/languages/rust.py`:

```python
"""Rust language adapter — cargo fmt, check, test, clippy."""

from __future__ import annotations


class RustAdapter:
    """Rust language defaults.

    These values were previously hardcoded in cli.py _CONFIG_TEMPLATE
    and coordinator.py _validate_result(). Extracted here as the single
    source of truth for Rust validation configuration.
    """

    language: str = "rust"

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
        return {
            "rust_default": ["fmt", "check", "test", "clippy"],
        }
```

### Task 2.4 — Create `languages/python.py`

Create `forgerwrite_mcp/languages/python.py`:

```python
"""Python language adapter — ruff, pytest, mypy."""

from __future__ import annotations


class PythonAdapter:
    """Python language defaults.

    Uses ruff for linting and formatting, pytest for tests,
    and mypy for static type checking.
    """

    language: str = "python"

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
        return {
            "python_default": ["lint", "format_check", "test", "typecheck"],
        }
```

### Task 2.5 — Wire adapter into `forgerwrite init`

Open `forgerwrite_mcp/cli.py`. Find the `init` command function. The config template `_CONFIG_TEMPLATE` is defined at the top of the file. You need to make the `init` command populate `[validation.commands]` and `[validation.profiles]` from the language adapter.

Find the `init` command function (search for `def init(`). After the config is written but before the success message, add logic to populate validation from the adapter. The exact change depends on how `init` is implemented — read the function and adapt accordingly.

The key logic is:
```python
from .languages import get_adapter

adapter = get_adapter(language)  # language comes from --language flag
if adapter is not None:
    # Use adapter defaults for validation section
    ...
```

### Task 2.6 — Regression gate

```bash
uv run pytest tests/ -q
```

All existing 251+ tests must pass. Then:

```bash
uv run pytest tests/test_language_adapters.py -v
```

All 11 new tests must pass.

**Files changed:**
- `forgerwrite_mcp/languages/__init__.py` (new)
- `forgerwrite_mcp/languages/base.py` (new)
- `forgerwrite_mcp/languages/rust.py` (new)
- `forgerwrite_mcp/languages/python.py` (new)
- `forgerwrite_mcp/cli.py` (wire adapter)
- `tests/test_language_adapters.py` (new)

**Test count:** +11

---

## PHASE 3: Python Dogfood

**Goal:** Use ForgeWrite to edit its own codebase through 5 Python slices.

**Precondition:** Phases 0-2 complete. `.forgerwrite/forgerwrite.toml` has `language = "python"` and valid Python validation profile.

**Caution:** This phase modifies the ForgeWrite codebase itself. Every slice must be on a clean worktree with a git snapshot. If a slice corrupts files, restore and report.

### Slice P1 — Add adapter tests

- **Allowed files:** `tests/test_language_adapters.py`
- **Goal:** Add a test that verifies `list_adapters()` returns at least ["rust", "python"]

### Slice P2 — Refactor validation profile config

- **Allowed files:** `forgerwrite_mcp/cli.py`
- **Goal:** Replace hardcoded validation commands in `_CONFIG_TEMPLATE` with adapter-derived values

### Slice P3 — Update init template for Python

- **Allowed files:** `forgerwrite_mcp/cli.py`
- **Goal:** Add `--language python` support to `forgerwrite init` with Python adapter defaults

### Slice P4 — Add Python documentation

- **Allowed files:** `docs/configuration.md`
- **Goal:** Document the `[validation]` section for Python projects (ruff, pytest, mypy commands)

### Slice P5 — Fix a real bug

- **Allowed files:** TBD by ruff/mypy output
- **Goal:** Fix a real lint or type error found by `ruff check` or `mypy`

For each slice:
1. Write the slice contract as a JSON file
2. Run `fw_generate_operations_local` via MCP or coordinator
3. Validate, preview, approve, apply
4. Run validation profile: `ruff check . && ruff format --check . && pytest -q && mypy forgerwrite_mcp/`
5. If validation fails, let repair loop try up to 2 times
6. Save run summary

Write `docs/acceptance/python_dogfood.md` with results.

**Files:** `docs/acceptance/python_dogfood.md` (new), run artifacts, potentially modified source files
**Tests:** Acceptance artifacts only

---

## PHASE 4: Scout v1

**Goal:** Evidence discovery pipeline before context building.

**Gate:** 4 dogfood slices use Scout. `scout_packet.json` produced per run.

### Task 4.1 — Scout packet schema

Create `schemas/scout_packet.v1.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "forgewrite.scout_packet.v1",
  "title": "Scout Evidence Packet",
  "description": "Context evidence gathered before operation generation.",
  "type": "object",
  "required": ["schema_id", "question", "exact_evidence"],
  "properties": {
    "schema_id": { "const": "forgewrite.scout_packet.v1" },
    "question": {
      "type": "string",
      "minLength": 1,
      "description": "The question or task description that drove the scout"
    },
    "retrieval_hits": {
      "type": "array",
      "description": "TurboVec / RAG retrieval results",
      "items": {
        "type": "object",
        "required": ["doc_id", "title", "snippet"],
        "properties": {
          "doc_id": { "type": "string" },
          "title": { "type": "string" },
          "snippet": { "type": "string" }
        }
      }
    },
    "exact_evidence": {
      "type": "array",
      "minItems": 0,
      "description": "Path:line evidence from grep and file reads",
      "items": {
        "type": "object",
        "required": ["path", "line_start", "finding"],
        "properties": {
          "path": { "type": "string" },
          "line_start": { "type": "integer", "minimum": 1 },
          "line_end": { "type": "integer", "minimum": 1 },
          "finding": { "type": "string", "minLength": 1 }
        }
      }
    },
    "recommended_allowed_files": {
      "type": "array",
      "items": { "type": "string" }
    },
    "recommended_reads": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "line_start", "line_end", "reason"],
        "properties": {
          "path": { "type": "string" },
          "line_start": { "type": "integer", "minimum": 1 },
          "line_end": { "type": "integer", "minimum": 1 },
          "reason": { "type": "string" }
        }
      }
    }
  }
}
```

### Task 4.2 — Scout tests

Create `tests/test_scout.py` with full test bodies (not `...`). Test classes:

- `TestScoutPacketSchema` — 4 tests: valid packet passes, missing evidence fails, empty question fails, negative line_start fails (use `ContractRegistry` like existing tests)
- `TestSafeGrep` — 5 tests: rejects path outside repo, rejects absolute path, skips binary files, respects max matches per query, respects max total matches
- `TestScoutCoordinator` — 3 tests: produces valid packet, respects caps, handles TurboVec disabled

### Task 4.3 — `scout/safe_grep.py`

Implement `safe_grep()` using `subprocess.run(["rg", ...])` with fallback to Python `re`. Route all paths through `paths.safe_resolve_path()`. Apply caps strictly.

### Task 4.4 — `scout/coordinator.py`

Implement `ScoutCoordinator.scout()`: query TurboVec → grep allowed files → normalize evidence → build packet.

### Task 4.5 — MCP tools

Add `fw_scout` and `fw_scout_grep` to `server.py`. Follow the exact same pattern as existing tools (try/except → `envelope_from().to_dict()`).

### Task 4.6 — Pipeline integration

Add `_enrich_with_scout()` to `SliceCoordinator`. Call it before `_build_context()`. Do NOT modify `context.py`.

### Task 4.7 — Dogfood

Run 4 Python slices using Scout before generation. Verify `scout_packet.json` in run artifacts.

---

## PHASE 5: Model-Assisted Scout

**Goal:** Local model plans grep queries and summarizes results.

### Tasks

1. Write failing tests for planner output validation (invalid JSON → fallback, missing queries → fallback)
2. Add `scout/planner.py` — calls `LlamaCppClient`, validates output strictly, returns query list or None
3. Add `scout/summarizer.py` — compresses evidence over char limit
4. Add deterministic fallback: keyword extraction + broad grep when planner returns None
5. Run 5 comparison slices: deterministic vs model-assisted, write report

---

## PHASE 6: Saved Work KB

**Goal:** Store reusable patterns. TurboVec-indexed.

### Tasks

1. Write failing tests for `knowledge_entry.v1` and `knowledge_usage.v1` schemas
2. Add schemas
3. Write failing tests for `KnowledgeStore` (CRUD, deprecation)
4. Add `knowledge/store.py` — file-backed JSON (one file per entry, `~/.forgewrite/knowledge/` and `.forgewrite/knowledge/`)
5. Add `knowledge/promotion.py` — `promote_from_run(run_dir) -> KnowledgeEntry | None`
6. Add `knowledge/usage.py` — `record_usage(entry_id, success: bool)`
7. Add 5 MCP tools: `fw_knowledge_search`, `fw_knowledge_save_entry`, `fw_knowledge_get_entry`, `fw_knowledge_record_usage`, `fw_knowledge_deprecate_entry`
8. Index promoted entries into TurboVec via existing `RagIndex`
9. Create first 5 entries from ForgeWrite patterns:
   - Safe Path Resolver Pattern
   - Hash-Bound Terminal Approval Pattern
   - MCP stdout-to-stderr Guard Pattern
   - Structured JSON Operation Batch Pattern
   - Bounded Repair Loop Pattern

---

## PHASE 7: Integrations + Release Candidate

**Goal:** MEX, Graphify, Headroom adapters with fail-soft. Tag RC.

### Tasks

1. Write failing tests for adapters (missing tool → graceful degradation, no path bypass)
2. Add `integrations/mex_adapter.py` — reads `.mex/ROUTER.md`, `.mex/context/` files
3. Add `integrations/graphify_adapter.py` — architecture graph leads
4. Add `integrations/headroom_adapter.py` — compresses bulky outputs
5. All adapters: fail-soft when optional dependency missing, never bypass path policy
6. Finalize README, config docs, MCP docs, design doc
7. Run clean install test from scratch (`uv sync` in fresh venv)
8. Run full suite: pytest, ruff, mypy, pip-audit, semgrep, trivy
9. Write release notes and known limitations
10. Tag `v0.1.0-rc1`

---

## KILL CRITERIA — After Every Phase

Before starting the next phase, confirm ALL of these:

- [ ] `uv run pytest tests/ -q` — all tests pass
- [ ] `uv run ruff check forgerwrite_mcp/ tests/` — clean
- [ ] `uv run mypy forgerwrite_mcp/` — clean
- [ ] `forgerwrite doctor` — no errors
- [ ] At least one dogfood slice succeeded this phase
- [ ] Rust acceptance slices (Phase 1) still pass (re-run after Phases 2-7)
- [ ] `.mex/ROUTER.md` updated with new project state
- [ ] Phase gate decision recorded in `.mex/context/decisions.md`: PROCEED / STOP / PIVOT

## ANTI-PATTERNS — DO NOT DO THESE

1. **Do not add new dependencies** to `pyproject.toml` unless explicitly listed in a task.
2. **Do not modify `paths.py`** — it is the security chokepoint.
3. **Do not modify `forge/forge.py`** — it is the mutation chokepoint.
4. **Do not modify `approval.py`** — it is the authorization chokepoint.
5. **Do not remove or rename existing MCP tools** — only add new ones.
6. **Do not change existing test assertions** — if a test fails, fix the implementation.
7. **Do not refactor "while you're in the file"** — stay on task scope.
8. **Do not use `shell=True`** in subprocess calls.
9. **Do not call `print()`** in MCP server code — use `write_artifact()` or logging.
10. **Do not hardcode paths** — use `config.rag.index_path`, not `"data/rag/index.tqi"`.
