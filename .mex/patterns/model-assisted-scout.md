---
name: model-assisted-scout
description: Phase 5 — adding model-assisted query planning and evidence summarization to Scout
when: adding a new model-assisted capability or maintaining Scout's planner/summarizer
---

# Model-Assisted Scout (Phase 5)

## Architecture

```
question → ScoutCoordinator.scout()
            ├─ plan_queries(question, use_model=True)
            │   ├─ _plan_with_model() ──→ health check → LlamaCppClient → JSON parse
            │   └─ _extract_queries() ──→ deterministic fallback (coordinator)
            ├─ safe_grep(repo_root, queries) ──→ GrepResult
            └─ summarize_evidence(evidence) ──→ dedup, sort, cap
```

## Files

| File | Purpose |
|------|---------|
| `forgerwrite_mcp/scout/planner.py` | `plan_queries()` — model-assisted with deterministic fallback |
| `forgerwrite_mcp/scout/summarizer.py` | `summarize_evidence()` — dedup by (path, line_start), sort, cap |
| `forgerwrite_mcp/scout/coordinator.py` | `ScoutCoordinator` — added `use_model_planner` param, wired planner + summarizer |

## Key Decisions

1. **Health check before model call**: `_plan_with_model` first checks `{endpoint}/models` with a 2s httpx GET. If the server isn't running, returns `None` immediately — no hanging.
2. **`asyncio.run()` for sync context**: The planner is called from sync code (coordinator), so the async model call is wrapped in `asyncio.run(asyncio.wait_for(..., timeout=10))`. In test environments where an event loop already exists, `asyncio.run()` raises `RuntimeError`, which is caught and triggers fallback.
3. **Deterministic fallback always works**: `_extract_queries()` (reused from Phase 4) extracts keywords from the question. Results may differ from model output but are always valid.
4. **Summarizer always applied**: After grep, evidence is always deduplicated, sorted, and capped — regardless of planner mode.

## Tests

- `tests/test_scout.py::TestScoutPlanner` (4 tests)
- `tests/test_scout.py::TestScoutSummarizer` (4 tests)
- `tests/test_scout.py::TestScoutCoordinatorModelAssisted` (1 test)

## Common Pitfalls

- `asyncio.run()` in nested context: caught by `except Exception` in `_plan_with_model`, causes fallback. This is intentional — the deterministic path is always available.
- Health check port mismatch: if the model server is running but on a different port, the health check fails and fallback is used. This is acceptable — the model-assisted path is a bonus.
- Safe grep path handling: `safe_grep` treats ALL items in `queries` as grep patterns. `allowed_files` are prepended as `["src/main.rs", "error", "handler"]` — the file path pattern won't match file contents (it matches the text "src/main.rs" in files, not the filename), so it's harmless.
