# Phase 4 Audit — Remediation Plan

**Created:** 2026-06-07
**Updated:** 2026-06-07 (v2 — revised after plan review)
**Status:** Pending execution
**Audit ref:** Phase Readiness Audit Report (commit `13043b0`)

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

## Step 0 — Extract Shared Doctor Function (prerequisite for Step 4) — est. 10 min

The `doctor` CLI command currently has inline check logic. Step 4 needs to call the same checks from `init` and `approve` without duplicating code or importing CLI commands from CLI commands (circular dependency smell).

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 0.1 | Create `forgerwrite_mcp/doctor.py` with `run_doctor_checks(config_path: Path) -> dict[str, bool]` — returns `{check_name: passed}` dict | New file | No |
| 0.2 | Refactor CLI `doctor` command to call `run_doctor_checks()` | `cli.py` | No |
| 0.3 | Verify existing `test_cli.py` doctor test still passes | `tests/test_cli.py` | — |

**Exit:** Shared `run_doctor_checks()` available for Step 4. No new tests needed (existing CLI doctor test covers output shape).

---

## Step 1 — Preview Fix + Dead Code + Slice ID + Schema ID (B3, N1, N4, N5) — est. 20 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 1.1 | **DRY fix:** Replace entire `coordinator._preview()` body with a call to `forge.preview_operations()`. This function already stages new files, generates a cached diff against the snapshot, and restores cleanly. Do not write a third diff implementation. | `coordinator.py` | No |
| 1.2 | Write test: preview diff includes new (untracked) files. Create a temp git repo, run preview with a `create_file` op, verify the diff shows the new file. | `tests/test_coordinator.py` | Yes |
| 1.3 | Delete unused `_init_run()` method (lines 263–266). | `coordinator.py` | No |
| 1.4 | Add `"schema_id": "forgerwrite.context_packet.v1"` to `build_context_packet()` return dict. Update existing context tests to verify the field. | `context.py`, `tests/context/test_build.py` | Yes |
| 1.5 | Extract `slice_id` from `slice_contract["slice_id"]` in `run()`, store as instance state, propagate to `_record()`. Update existing coordinator test to verify `slice_id != "unknown"` rather than a brittle string-match test. | `coordinator.py`, `tests/test_coordinator.py` | Yes |

**Exit:** Preview captures new files. No dead code. Context packet has schema_id. Slice correlation works.

---

## Step 2 — Snapshot Cleanup (N2) — est. 10 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 2.1 | In `run()`, after `_STATUS_VALIDATION_PASSED`: call `cleanup_snapshot(self._repo_root, self._run_id)`. This is the **apply** snapshot (created in `_apply()`), not the preview snapshot (already restored in `_preview()`). | `coordinator.py` | No |
| 2.2 | In `gc` CLI: run `git for-each-ref refs/forgerwrite/ --format="%(refname)"`, compare against existing run directories, delete orphan refs with `git update-ref -d`. | `cli.py` | No |
| 2.3 | Write test: after successful coordinator run, `refs/forgerwrite/<run_id>` does not exist. | `tests/test_coordinator.py` | Yes |

**Exit:** No stale refs after successful runs. GC handles orphans.

---

## Step 3 — Doctor Auto-Run (N3) — est. 15 min

| # | Action | File(s) | TDD |
|---|--------|---------|:---:|
| 3.1 | Add `--no-doctor` / `--skip-doctor` flag to `init` and `approve` commands. | `cli.py` | No |
| 3.2 | Call `run_doctor_checks()` (from Step 0) before main action. On failure: **warn** with `[yellow]` output, do not abort — doctor failures are advisory, not gates. | `cli.py` | No |
| 3.3 | Write test: `init` calls doctor checks and prints warnings for failures. `--no-doctor` skips the check entirely. Use mocked `run_doctor_checks`. | `tests/test_cli.py` | Yes |

**Exit:** Safety checks run automatically before `init` and `approve`, with opt-out.

---

## Step 4 — Functional Repair Loop (B1) — est. 2 hours

This is the most complex fix. The spec (§5.12) requires 5 sub-steps per iteration:
1. Build feedback prompt from validation errors
2. Re-invoke local model → new operation batch
3. Schema-validate new batch
4. Semantic-validate new batch (with original slice scope check)
5. Re-preview the diff

### 4a — Artifact naming spec (decide before tests)

| Artifact | Naming |
|----------|--------|
| Repair prompt for attempt N | `repair_prompt_{N}.txt` |
| Raw model response for attempt N | `repair_response_{N}.json` |

### 4b — Tests (write FIRST, watch them FAIL)

| # | Test | File | What it verifies |
|---|------|------|-----------------|
| 4.1 | `test_repair_loop_reinvokes_model_and_succeeds` | `tests/test_coordinator.py` | Full coordinator with `FakeLocalModelBackend`: first gen fails validation, second gen (repair) produces valid ops → validation passes → run succeeds |
| 4.2 | `test_repair_loop_handles_invalid_json_during_repair` | `tests/test_coordinator.py` | Model returns invalid JSON during repair → coordinator catches `JSONDecodeError` → increments attempt → continues loop |
| 4.3 | `test_repair_loop_exhausts_budget` | `tests/test_coordinator.py` | Model keeps returning ops that fail validation → loop runs `repair.max_attempts` times → returns `_STATUS_VALIDATION_FAILED` |
| 4.4 | `test_repair_ops_rejected_outside_scope` | `tests/test_coordinator.py` | Repair ops target files outside original `allowed_files` → semantic validator rejects → loop continues |
| 4.5 | `test_repair_writes_artifacts_per_iteration` | `tests/test_coordinator.py` | After 2 repair attempts, `repair_prompt_1.txt`, `repair_response_1.json`, `repair_prompt_2.txt`, `repair_response_2.json` exist in run_dir |

### 4c — Implementation

| # | Action | File(s) |
|---|--------|---------|
| 4.6 | Refactor `RepairCoordinator.attempt()`: return `(prompt: str, budget_remaining: int)` on success, or `None` if budget exhausted. Remove `success=False` hardcoding. Keep budget tracking + prompt building in this class. | `repair.py` |
| 4.7 | Refactor `_maybe_repair()` into a loop in `SliceCoordinator`: |

```python
def _maybe_repair(self, slice_contract: dict) -> str:
    repair = RepairCoordinator(config=self._config.repair)
    validation_result = json.loads(
        (self._run_dir / "validation_result.json").read_text()
    )

    while True:
        result = repair.attempt(validation_result, slice_contract)
        if result is None:
            # Budget exhausted
            self._restore_snapshot()
            return _STATUS_VALIDATION_FAILED

        prompt, _remaining = result

        # Write repair prompt artifact
        write_artifact(self._run_dir, f"repair_prompt_{repair.attempt_count}.txt",
                       {"prompt": prompt})

        # Re-invoke model with repair prompt
        import asyncio
        try:
            raw = asyncio.run(
                self._backend.generate_operation_batch(
                    "You are a coding assistant fixing validation errors.",
                    prompt,
                    self._operation_batch_schema,
                )
            )
        except Exception:
            continue  # Model error → try again

        # Write raw response artifact
        write_artifact(self._run_dir,
                       f"repair_response_{repair.attempt_count}.json",
                       {"raw": raw})

        # Schema-validate
        try:
            self._operation_batch = json.loads(raw)
            self._validate_schema()
        except Exception:
            continue

        # Semantic-validate (with original scope)
        try:
            self._validate_semantic(slice_contract)
        except Exception:
            continue

        # Re-preview
        try:
            self._preview(slice_contract)
        except Exception:
            continue

        # Re-apply + re-validate
        status = self._apply(slice_contract)
        if status != _STATUS_APPLIED:
            continue

        status = self._validate_result()
        if status == _STATUS_VALIDATION_PASSED:
            return _STATUS_VALIDATION_PASSED
        # Loop: validation failed again → repair attempts another iteration

    return _STATUS_VALIDATION_FAILED
```

| 4.8 | Add `_restore_snapshot()` helper that calls `restore_snapshot()` without raising. | `coordinator.py` |
| 4.9 | Add `attempt_count` property to `RepairCoordinator`. | `repair.py` |
| 4.10 | Ensure `_maybe_repair` passes the **real** `validation_result` (from step `_validate_result`), not `{}`. Remove the `write_artifact(self._run_dir, "validation_result.json", {})` overwrite line. | `coordinator.py` |

### 4d — Integration test

| # | Action | File(s) |
|---|--------|---------|
| 4.11 | Write integration test: full pipeline in temp git repo with `FakeLocalModelBackend` simulating first-gen-fails-then-repair-succeeds cycle. Verify `repair.max_attempts` honored and snapshot restored on exhaustion. (Spec §13 requirement.) | `tests/test_coordinator.py` |

**Exit:** Repair loop functional. 5 unit tests + 1 integration test pass. All existing tests still green.

---

## Step 5 — Spike Reports (B2) — est. 30 min

Retrospective reports documenting what was learned during Phase 0 spikes. The code has been validated through 180 tests and working MCP integration — these document the findings that would have been recorded had formal spike reports been written before Phase 1.

| # | Action | File |
|---|--------|------|
| 5.1 | Write `spikes/001_json_schema/report.md` — document OmniCoder 9B Q8 JSON-schema reliability: temperature setting, schema-valid rate assessment, known failure modes (nested objects, long content fields), decision: GO | New file |
| 5.2 | Write `spikes/002_mcp_stdio/report.md` — document FastMCP stdio behavior: `print()` corruption confirmed, stdout-to-stderr redirect verified as effective, decision: GO | New file |
| 5.3 | Write `spikes/003_llama_lifecycle/report.md` — document llama.cpp launch command, cold-start time estimate, memory footprint range, baseline tokens/sec, documented in `docs/llama-cpp-setup.md` | New file |

**Exit:** Phase 0 exit criteria formally satisfied. All three spike directories contain written reports.

---

## Step 6 — Final Verification — est. 15 min

| # | Action |
|---|--------|
| 6.1 | Re-run §16 audit checklist against codebase — all items should now pass |
| 6.2 | `uv run pytest -q` — all tests pass |
| 6.3 | `uv run ruff check .` — clean |
| 6.4 | Update `docs/project-state.md` — remove audit findings from "Known issues", update "Working" section |
| 6.5 | Update `.mex/ROUTER.md` "Current Project State" section — remove B1/B2/B3/N1-N5 |
| 6.6 | Run `npx promexeus check --quiet` — verify drift score improved |
| 6.7 | Commit + merge to main |

---

**Total estimated:** ~3.5 hours
