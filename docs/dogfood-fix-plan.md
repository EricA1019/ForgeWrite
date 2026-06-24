# Dogfood Fix Plan

**Date:** 2026-06-24
**Source:** ForgeWrite dogfood session — 4-slice Rust bookmark manager project
**Baseline:** 358 tests, 0 lint errors, Gemma 4 12B QAT @ 32k context on RTX 3060

---

## Problem Summary

Ran ForgeWrite through its full pipeline on a real Rust project (`_output/bookmarks/`). 4 slices, 7 operations, 6 files created. Project compiles clean with zero warnings. The pipeline works end-to-end, but 7 issues were discovered that prevent production readiness.

---

## Issues

### #1 — `fw_validate_operations` hardcodes empty `allowed_files`

**Severity:** High — all file-targeting operations fail semantic validation.

**Root cause:** `server.py:521` calls `default_validator().validate(operation_batch, {"allowed_files": []})`. The validator's `ScopeRule` checks every operation path against an empty list, so every file operation fails.

**Fix:**
1. Add optional `slice_contract` parameter to `fw_validate_operations` tool (default `None`)
2. When provided, pass to semantic validator's `validate()` so `ScopeRule` sees real `allowed_files`
3. When absent, use empty `{"allowed_files": []}` (backwards compatible, current behavior)

**Files:**
- `forgerwrite_mcp/server.py` — add `slice_contract: dict | None = None` param (~line 521)
- `tests/test_server.py` — add test for validation with slice contract

**Acceptance:** `fw_validate_operations` returns `ok: true` when valid ops target files listed in the slice contract's `allowed_files`.

---

### #2 — Server CWD mismatch — all paths relative to ForgeWrite root

**Severity:** High — breaks multi-project workflows. Every tool uses `Path.cwd()` which is the ForgeWrite server's directory, not the target project's.

**Root cause:** The MCP server boots from the ForgeWrite repo root. All file operations resolve relative to that CWD. A project at `_output/bookmarks/` needs paths like `_output/bookmarks/src/main.rs` instead of `src/main.rs`.

**Fix:**
1. Add optional `project_root` parameter to file-operation tools (`fw_scout`, `fw_scout_grep`, `fw_preview_operations`, `fw_apply_approved_operations`, `fw_run_validation_profile`)
2. When provided, resolve all paths relative to `project_root`
3. When absent, use server's `Path.cwd()` (backwards compatible)

**Files:**
- `forgerwrite_mcp/server.py` — add `project_root` to affected tools
- `forgerwrite_mcp/forge/forge.py` — accept `repo_root` override
- `forgerwrite_mcp/validation/runner.py` — accept `working_dir` param

**Acceptance:** Operations targeting `src/main.rs` succeed when `project_root=_output/bookmarks`.

---

### #3 — Line-number shift on sequential operations

**Severity:** Medium — `insert_before_line` followed by `replace_line_range` in the same batch produces duplicate/corrupted content because line numbers shift after the first operation is applied.

**Root cause:** `forge.py:preview_operations` applies all operations in sequence against the working tree, but line numbers from the original operation batch are used for every operation — they're not recalculated after each mutation.

**Fix (option A — simpler):**
- Document constraint: line-based operations in the same batch must reference mutually exclusive line ranges
- Add validation rule: detect overlapping/sequential line ops in same batch and reject

**Fix (option B — robust):**
- After each line-modifying operation, recalculate remaining operations' line numbers by tracking delta
- Operations dispatched in order: `insert_before_line`/`insert_after_line` modifies line counts, adjust subsequent `replace_line_range`/`after_line`/`before_line` values

**Recommendation:** Option A first (document + validate), Option B deferred.

**Files:**
- `forgerwrite_mcp/validation/semantic.py` — add `LineOverlapRule`
- `docs/operations.md` — document constraint

**Acceptance:** A batch with `insert_before_line` (line 28) + `replace_line_range` (lines 29-44) is rejected with a clear error explaining the line-shift constraint.

---

### #4 — Preview diff SHA256 always empty-hash

**Severity:** Medium — `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (SHA256 of empty string) returned for every preview, making the diff hash useless for TOCTOU detection.

**Root cause:** `git add -A` in `forge.py:preview_operations` stages from CWD, but the snapshot ref may not capture untracked files. The `git diff --cached <ref>` produces empty output when comparing new untracked files that aren't yet in the git tree.

**Fix:**
1. After `git add -A`, verify that all operation `path` targets are tracked
2. For untracked paths that will be created: use `git diff HEAD -- <path>` instead of `git diff --cached <ref>`
3. Fall back to direct file-content hashing if git diff is empty

**Files:**
- `forgerwrite_mcp/forge/forge.py` — fix diff generation
- `tests/forge/test_forge.py` — test diff for new files

**Acceptance:** Creating a new file via `create_file` produces a non-empty diff with a real SHA256 hash.

---

### #5 — Model generates single operation when multiple requested

**Severity:** Medium — `fw_generate_operations_local` returned only `Cargo.toml` when 4 files were requested in the handoff description.

**Root cause:**
1. `max_tokens=4096` in config — not enough for a 4-operation JSON batch
2. System prompt emphasizes JSON schema format but doesn't remind to include ALL requested files

**Fix:**
1. Increase default `max_tokens` to `8192` in `config.py`
2. Update system prompt in `coordinator.py:_generate_operations` to explicitly say: "Generate ALL files listed in the task description. Do not stop at one."
3. Add the total requested file count to the user prompt

**Files:**
- `forgerwrite_mcp/config.py` — `max_tokens: int = Field(ge=128, le=32768) = 8192`
- `forgerwrite_mcp/coordinator.py` — update system prompt
- `forgerwrite_mcp/server.py` — update prompt in `fw_generate_operations_local`

**Acceptance:** Generating 4 scaffold files produces an operation batch with 4 operations.

---

### #6 — `fw_run_validation_profile` runs from wrong CWD

**Severity:** Low — validation profile runs from ForgeWrite root, not target project directory.

**Root cause:** Same as #2 — `Path.cwd()` in the validation runner.

**Fix:** Same approach as #2 — accept `project_root` parameter. The validation runner calls `cargo check` etc. which need to run from the project root.

**Files:**
- `forgerwrite_mcp/server.py` — add `project_root` to `fw_run_validation_profile`
- `forgerwrite_mcp/validation/runner.py` — accept `cwd` parameter for subprocess

**Acceptance:** `fw_run_validation_profile("rust_default")` with `project_root=_output/bookmarks` runs `cargo check` in the bookmarks directory.

---

### #7 — `max_tokens` config default too low

**Severity:** Low — default `max_tokens=4096` constrains the model's output, especially for multi-file batches.

**Fix:**
1. Increase `max_tokens` default from 4096 to 8192
2. Update all documentation that references the old default

**Files:**
- `forgerwrite_mcp/config.py` — change default
- `README.md` — update config example
- `docs/configuration.md` — update reference
- `docs/llama-cpp-setup.md` — update example

**Acceptance:** Config default is 8192, all docs match.

---

## Execution Order

Dependency chain:
```
#7 (max_tokens bump) ← independent, no test impact
    ↓
#5 (model multi-op) ← depends on #7 for token budget
    ↓
#1 (validate_operations) ← independent of model
#2 (CWD fix) ← independent, shared fix for #6
    ↓
#6 (validation_profile CWD) ← depends on #2
    ↓
#3 (line-number shift) ← independent
#4 (preview diff) ← independent, moderate complexity
```

Recommended: **#7 → #1 + #2 → #5 + #6 → #3 → #4**

---

## Test Impact

| Issue | New Tests | Existing Tests Affected |
|-------|-----------|------------------------|
| #1 | +2 (validate with/without slice contract) | 0 |
| #2 | +2 (operations with project_root) | Minor — existing tests use default CWD |
| #3 | +2 (reject overlapping line ops, accept safe ops) | 0 |
| #4 | +2 (diff for new file, SHA256 non-empty) | 0 |
| #5 | +1 (multi-op generation produces correct count) | 0 |
| #6 | +1 (validation profile with project_root) | Minor |
| #7 | 0 (config change) | Config default test updates |
| **Total** | **~10 new tests** | **~2 minor test updates** |

## Estimated Effort

| Issue | Complexity | Est. Time |
|-------|-----------|-----------|
| #1 | Low | 20 min |
| #2 | Medium | 45 min |
| #3 | Medium | 45 min |
| #4 | High | 60 min |
| #5 | Low | 15 min |
| #6 | Low | 15 min |
| #7 | Trivial | 10 min |
| **Total** | | **~3.5 hours** |

---

## Bonus Issues (Deferred)

These were observed during dogfood but are lower priority:

### B1 — `fw_model_health` reports config model name, not actual loaded model
`model_name` field returns `"omnicoder-9b"` (from config default) even when `loaded_models` shows `"gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"`. Confusing when the config default doesn't match the running model.

### B2 — System prompt duplicated between coordinator and server
Both `coordinator.py:_generate_operations` and `server.py:fw_generate_operations_local` define the same JSON schema prompt. Single source of truth needed — likely a shared constant in `contracts/` or a `prompts.py` module.

### B3 — `model_state.json` tracks stale state
The file at `.forgerwrite/model_state.json` is not gitignored (added in rc2 hardening) but writes timestamps on every health check — constant churn, not useful as committed data. Should be in `.forgerwrite/runs/` or use a TTL instead of write-on-every-call.
