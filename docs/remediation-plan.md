# Phase 4 Audit — Remediation Plan

**Created:** 2026-06-07
**Status:** Pending execution
**Audit ref:** Phase Readiness Audit Report (commit `3210d88`)

---

## Blocking Issues

| ID | Description | Severity |
|----|-------------|----------|
| B1 | Repair loop is non-functional stub — `_maybe_repair` never re-invokes the model | Blocker |
| B2 | Phase 0 spike reports absent — three empty spike directories | Blocker |
| B3 | Coordinator preview does not capture new files — `git diff` without staging | Blocker |

## Non-Blocking Issues

| ID | Description |
|----|-------------|
| N1 | `slice_id` hardcoded to `"unknown"` — loss of correlation |
| N2 | Stale snapshot refs never cleaned up — `_cleanup()` is dead code |
| N3 | `doctor` does not auto-run on `init`/`approve` |
| N4 | Context packet lacks `schema_id` |
| N5 | `_init_run()` dead code |

---

## Step 1 — Quick Wins (B3, N1, N4, N5) — est. 25 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 1.1 | Replace inline `git diff` with `git add -A && git diff --cached HEAD` | `coordinator.py`, `tests/test_coordinator.py` | Yes |
| 1.2 | Extract `slice_id` from `slice_contract` in `run()` and propagate | `coordinator.py`, `tests/test_coordinator.py` | Yes |
| 1.3 | Add `"schema_id": "forgerwrite.context_packet.v1"` to context return | `context.py`, `tests/context/test_build.py` | Yes |
| 1.4 | Delete unused `_init_run()` method | `coordinator.py` | No |

## Step 2 — Functional Repair Loop (B1) — est. 45 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 2.1 | Test: repair re-invokes model with canned fix response | `tests/test_coordinator.py` | Yes |
| 2.2 | Test: repair exhausts budget after repeated failures | `tests/test_coordinator.py` | Yes |
| 2.3 | Test: repair artifacts written per attempt | `tests/test_coordinator.py` | Yes |
| 2.4 | Refactor `_maybe_repair` into a loop with model re-invoke + re-validate | `coordinator.py` | — |
| 2.5 | Fix `RepairCoordinator.attempt()` to signal ready-to-proceed | `repair.py` | — |
| 2.6 | Write repair prompt + response artifacts per iteration | `coordinator.py` | — |

## Step 3 — Snapshot Cleanup (N2) — est. 15 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 3.1 | Call `cleanup_snapshot()` after successful validation | `coordinator.py` | No |
| 3.2 | Add orphan `refs/forgerwrite/*` cleanup to `gc` command | `cli.py` | No |
| 3.3 | Test: snapshot ref deleted after successful run | `tests/test_coordinator.py` | Yes |

## Step 4 — Doctor Auto-Run (N3) — est. 15 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 4.1 | Add `--no-doctor` flag to `init` and `approve` | `cli.py` | No |
| 4.2 | Call `doctor` before main action unless `--no-doctor` | `cli.py` | No |
| 4.3 | Test: `init` auto-runs doctor checks | `tests/test_cli.py` | Yes |

## Step 5 — Spike Reports (B2) — est. 30 min

| # | Action |
|---|--------|
| 5.1 | Write `spikes/001_json_schema/report.md` — OmniCoder JSON-schema reliability |
| 5.2 | Write `spikes/002_mcp_stdio/report.md` — MCP stdio behavior verification |
| 5.3 | Write `spikes/003_llama_lifecycle/report.md` — llama.cpp launch baseline |

## Step 6 — Final Verification — est. 15 min

| # | Action |
|---|--------|
| 6.1 | Re-run §16 audit checklist |
| 6.2 | `uv run pytest -q` — all pass |
| 6.3 | `uv run ruff check .` — clean |
| 6.4 | Update `docs/project-state.md` |
| 6.5 | Commit + merge |

---

**Total estimated:** ~2.5 hours
