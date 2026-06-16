# ForgeWrite Dogfood Plan — Remaining Phases

**Date:** 2026-06-16
**Baseline:** 315 tests, 0 failures, Phase 6 complete
**Goal:** Use ForgeWrite to build the remaining ForgeWrite features. Every slice is a dogfood test.

---

## Strategy

Three remaining work items, each executed as ForgeWrite slices:

| # | Slice | What | Phase |
|---|-------|------|-------|
| D1 | Wire `use_model_planner` to `fw_scout` | Add `--model-planner` flag to CLI + MCP tool | 5.6 |
| D2 | Phase 5.5 comparison report | 5 slices comparing deterministic vs model-assisted Scout | 5.5 |
| D3 | Integrations + RC | MEX/Graphify/Headroom adapters, docs, release tag | 7 |

### Dogfood Protocol Per Slice

For every slice, follow this exact workflow — **this is the dogfood**:

```
1. fw_scout question allowed_files          → evidence packet
2. fw_knowledge_search question             → relevant KB entries
3. fw_build_context_packet handoff slice    → context (with Scout evidence)
4. fw_generate_operations_local ...          → operation batch
5. fw_validate_operations batch             → schema + semantic validation
6. fw_preview_operations batch              → diff preview
7. fw_apply_approved_operations batch       → apply + snapshot
8. fw_run_validation_profile profile        → ruff + pytest
9. fw_get_run_summary run_id                → run summary
10. fw_knowledge_promote_from_run run_id    → promote to KB (if successful)
11. fw_knowledge_record_usage entry_id outcome → record if KB entry helped
```

### Build Verification After Every Slice

```bash
uv run pytest tests/ -q --tb=no     # All tests must pass
uv run ruff check forgerwrite_mcp/ tests/   # Lint must be clean
```

---

## Slice D1: Wire `use_model_planner` to fw_scout

**Goal:** Add `--use-model-planner` flag to the `fw_scout` MCP tool and `forgerwrite scout` CLI command.

**Current state:** `use_model_planner` is accepted by `ScoutCoordinator` but not exposed to users. The tool/CLI always pass `use_model_planner=False`.

**Handoff:**
```json
{
  "schema_id": "forgewrite.handoff.v1",
  "project": "ForgeWrite",
  "language": "python",
  "description": "Wire the use_model_planner parameter from ScoutCoordinator through to the fw_scout MCP tool and forgerwrite scout CLI command. Add a --use-model-planner flag that defaults to False. The scout coordinator already accepts this parameter — just need to thread it through the tool and CLI layers.",
  "context_notes": "See forgerwrite_mcp/scout/coordinator.py ScoutCoordinator.__init__ for the parameter. See forgerwrite_mcp/server.py fw_scout for the current tool signature. See forgerwrite_mcp/cli.py for the scout command."
}
```

**Slice contract:**
```json
{
  "schema_id": "forgewrite.slice.v1",
  "slice_id": "d1-model-planner-wire",
  "goal": "Thread use_model_planner parameter through MCP tool and CLI",
  "allowed_files": [
    "forgerwrite_mcp/server.py",
    "forgerwrite_mcp/cli.py"
  ],
  "validation_profile": "python_default",
  "language": "python"
}
```

**Scout query:** `"use_model_planner parameter in ScoutCoordinator fw_scout server CLI"`

**Acceptance criteria:**
- [ ] `fw_scout` tool accepts optional `use_model_planner: bool = False`
- [ ] `forgerwrite scout` CLI accepts `--use-model-planner` flag
- [ ] All 315 tests pass
- [ ] ruff clean

---

## Slice D2: Phase 5.5 Comparison Report

**Goal:** Run 5 slices through BOTH model-assisted and deterministic Scout, compare results, write report.

**Handoff:**
```json
{
  "schema_id": "forgewrite.handoff.v1",
  "project": "ForgeWrite",
  "language": "markdown",
  "description": "Write a comparison report documenting 5 ForgeWrite slices run through both model-assisted and deterministic Scout query planning. Report should include: per-slice metrics (queries generated, evidence found, precision), overall comparison, and recommendation for default mode. The report goes in docs/acceptance/scout-comparison.md.",
  "context_notes": "The 5 test slices should cover: Rust import fix, Python test fixture, Rust edition fix, Python async HTTP, Rust scaffold — matching the 5 KB seed entries from Phase 6."
}
```

**Slice contract:**
```json
{
  "schema_id": "forgewrite.slice.v1",
  "slice_id": "d2-scout-comparison",
  "goal": "Write comparison report for model-assisted vs deterministic Scout",
  "allowed_files": [
    "docs/acceptance/scout-comparison.md"
  ],
  "validation_profile": "python_default",
  "language": "markdown"
}
```

**Scout query:** `"Scout comparison report model-assisted deterministic query planning metrics"`

**Acceptance criteria:**
- [ ] Report covers 5 slices
- [ ] Per-slice metrics included
- [ ] Recommendation documented
- [ ] All tests pass (docs can't break tests)

---

## Slice D3: Phase 7 — Integrations + Release Candidate

**Goal:** Add MEX, Graphify, and Headroom adapters with fail-soft behavior. Finalize docs. Tag RC.

### D3.1: Integration adapters

**Handoff:**
```json
{
  "schema_id": "forgewrite.handoff.v1",
  "project": "ForgeWrite",
  "language": "python",
  "description": "Add integration adapters for MEX, Graphify, and Headroom. Each adapter follows the fail-soft pattern: detect if the tool is available, return a placeholder result if not, never crash. Add forgerwrite_mcp/integrations/__init__.py (fail-soft registry), forgerwrite_mcp/integrations/mex_adapter.py, forgerwrite_mcp/integrations/graphify_adapter.py, forgerwrite_mcp/integrations/headroom_adapter.py. Write tests in tests/test_integrations.py.",
  "context_notes": "MEX is the project memory system (.mex/ directory). Graphify analyzes codebase graphs. Headroom is the automation orchestrator. All three are optional — if not installed, the adapters must return {'available': False, 'reason': 'not installed'} without raising."
}
```

**Slice contract:**
```json
{
  "schema_id": "forgewrite.slice.v1",
  "slice_id": "d3-integrations",
  "goal": "Add fail-soft integration adapters for MEX, Graphify, Headroom",
  "allowed_files": [
    "forgerwrite_mcp/integrations/__init__.py",
    "forgerwrite_mcp/integrations/mex_adapter.py",
    "forgerwrite_mcp/integrations/graphify_adapter.py",
    "forgerwrite_mcp/integrations/headroom_adapter.py",
    "tests/test_integrations.py"
  ],
  "validation_profile": "python_default",
  "language": "python"
}
```

**Scout query:** `"integration adapter fail-soft pattern MEX graphify headroom optional dependency"`

**Acceptance criteria:**
- [ ] 3 adapters with `check_available()` + `get_info()`
- [ ] Fail-soft: missing tool returns `{"available": false}` not exception
- [ ] 12-15 integration tests pass
- [ ] All existing 315 tests pass
- [ ] ruff clean

### D3.2: Docs + RC tag

**Handoff:**
```json
{
  "schema_id": "forgewrite.handoff.v1",
  "project": "ForgeWrite",
  "language": "markdown",
  "description": "Finalize README with project overview, quick start, tool reference. Update docs/configuration.md with all config sections. Write docs/release-notes-v0.1.0.md with known limitations. Tag v0.1.0-rc1.",
  "context_notes": "Current README is at README.md. Config docs at docs/configuration.md. Release notes go in docs/release-notes-v0.1.0.md."
}
```

**Slice contract:**
```json
{
  "schema_id": "forgewrite.slice.v1",
  "slice_id": "d3-docs-rc",
  "goal": "Finalize docs, write release notes, tag RC",
  "allowed_files": [
    "README.md",
    "docs/configuration.md",
    "docs/release-notes-v0.1.0.md"
  ],
  "validation_profile": "python_default",
  "language": "markdown"
}
```

**Acceptance criteria:**
- [ ] README has project overview, quick start, tool reference table
- [ ] Config docs cover all 8 config sections
- [ ] Release notes document known limitations
- [ ] `git tag v0.1.0-rc1` created

---

## Dogfood Run Log

Record each slice execution here:

| Slice | Date | Status | Run ID | Notes |
|-------|------|--------|--------|-------|
| D1 | | | | |
| D2 | | | | |
| D3.1 | | | | |
| D3.2 | | | | |

---

## Gate Checklist

After all slices complete:

- [ ] All 315+ tests pass
- [ ] `ruff check` clean
- [ ] `mypy forgerwrite_mcp/` (known 63 pre-existing errors, no new ones)
- [ ] At least 3 slices used `fw_knowledge_search` and `fw_knowledge_promote_from_run`
- [ ] At least 3 slices used `fw_scout` before generation
- [ ] `forgerwrite doctor` passes
- [ ] `v0.1.0-rc1` tag exists
- [ ] Run summary artifacts saved for all slices
