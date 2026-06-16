# Rust MVP Acceptance Report

**Date:** 2026-06-13
**Model:** Gemma 4 12B (Q4_K_XL) via llama.cpp
**Pipeline:** `SliceCoordinator` with auto-approve (full 14-state machine)
**Baseline:** 251 unit tests passing, 0 failures

---

## Summary

| Slice | Status | Pipeline | Operations | Time | Repair |
|-------|--------|----------|------------|------|--------|
| R1 — Create CLI | ❌ `validation_failed` | Full | 2 `create_file` | 297s | No |
| R2 — Fix bug | ✅ `validation_passed` | Full | 1 `replace_line_range` | 82s | No |
| R3 — Refactor | ❌ `context_ready` | Generation failed | 0 | 461s | N/A |

**Overall: 1/3 slices passed full acceptance criteria.** The pipeline infrastructure works. R2 demonstrates a complete end-to-end success: model generates valid operations → schema validation → preview → approval → apply → all cargo commands pass.

---

## Slice R1 — Create CLI Project

**Status:** ❌ `validation_failed` (297s)

### Pipeline Flow

| Step | Status | Detail |
|------|--------|--------|
| Contract validation | ✅ | Handoff + slice schemas valid |
| Context building | ✅ | Context packet written |
| LLM generation | ✅ | Valid JSON operation batch |
| Schema validation | ✅ | Draft 2020-12 passed |
| Semantic validation | ✅ | Scope, size, permissions passed |
| Preview diff | ✅ | `preview.diff` created |
| Auto-approval | ✅ | `approval_record.json` written |
| Apply | ✅ | Files created: `Cargo.toml`, `src/main.rs` |
| Validation (fmt) | ❌ | `cargo metadata` failed — inline TOML table with newlines |
| Repair loop | Not triggered | Validation error was TOML parse failure, not test failure |

### Failure Analysis

The generated `Cargo.toml` used an inline table with multi-line formatting:
```toml
[dependencies]
clap = {
    version = "4.0",
    features = ["derive"]
}
```

This is valid TOML syntax but Rust's `cargo metadata` + `cargo fmt` does not support newlines inside inline tables. `cargo metadata` exits with an error, which causes `cargo fmt` to fail.

**Root cause:** Model prompt needs to specify that `Cargo.toml` dependencies must use a single-line inline table format.

### Generated Operations

```json
{
  "batch_id": "r1-cli-setup",
  "operations": [
    {"op": "create_file", "path": "Cargo.toml", "content": "[package]\nname = \"minimal-cli\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nclap = {\n    version = \"4.0\",\n    features = [\"derive\"]\n}"},
    {"op": "create_file", "path": "src/main.rs", "content": "use clap::Parser;\n\n#[derive(Parser, Debug)]\n#[command(author, version, about, long_about = None)]\nstruct Args {\n    /// Name to greet\n    #[arg(short, long)]\n    name: String,\n}\n\nfn main() {\n    let args = Args::parse();\n    println!(\"Hello, {}!\", args.name);\n}"}
  ]
}
```

---

## Slice R2 — Add Failing Test + Fix Bug

**Status:** ✅ `validation_passed` (82s)

### Pipeline Flow

| Step | Status | Detail |
|------|--------|--------|
| Contract validation | ✅ | Handoff + slice schemas valid |
| Context building | ✅ | Context packet written |
| LLM generation | ✅ | Valid JSON operation batch |
| Schema validation | ✅ | Draft 2020-12 passed |
| Semantic validation | ✅ | Scope, size, permissions passed |
| Preview diff | ✅ | `preview.diff` created |
| Auto-approval | ✅ | `approval_record.json` written |
| Apply | ✅ | File modified: `src/lib.rs` line 4 |
| Validation (fmt, check, test, clippy) | ✅ **ALL PASSED** | `cargo test` passes, `cargo clippy` clean |
| Repair loop | Not needed | First attempt succeeded |

### Generated Operations

```json
{
  "batch_id": "fix-double-bug",
  "operations": [
    {"op": "replace_line_range", "path": "src/lib.rs", "start_line": 4, "end_line": 4, "content": "    n * 2"}
  ]
}
```

The model identified that line 4 contained `n * 3` and changed it to `n * 2`. **Note:** The model did NOT add a failing test first as requested — it went straight to the fix. The existing test (`test_double_positive`) then passed.

### Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| `cargo build` | ✅ PASS |
| `cargo test` | ✅ PASS |
| `cargo clippy` | ✅ PASS |

---

## Slice R3 — Refactor Without Behavior Change

**Status:** ❌ `context_ready` (461s)

### Failure Analysis

The pipeline built the context packet (read the refactor-able math module) but the LLM generation failed with "Failed to get valid JSON after 3 attempts." This means the model could not produce a valid JSON operation batch within 3 schema repair retries.

**Possible causes:**
1. The system prompt's instruction to produce a refactoring (extract helper function) resulted in complex multi-step operations that the model struggled to format as JSON.
2. The 4096 max_tokens limit may have been insufficient for a refactor with multiple `replace_line_range` operations.
3. The model's `json_object` response format may have produced valid JSON that failed schema validation (e.g., wrong field names, missing required fields).

### Pipeline Flow

| Step | Status | Detail |
|------|--------|--------|
| Contract validation | ✅ | Schemas valid |
| Context building | ✅ | Context packet with file contents |
| LLM generation (attempt 1) | ❌ | Invalid JSON or schema failure |
| Schema repair (attempt 2) | ❌ | Retry also failed |
| Schema repair (attempt 3) | ❌ | Budget exhausted |

---

## Findings

### What Works (Pipeline Infrastructure)

1. ✅ **14-state coordinator pipeline** — all states transition correctly.
2. ✅ **LLM integration** — `LlamaCppClient` calls Gemma 4 12B with `json_object` format successfully (R1: 297s, R2: 82s).
3. ✅ **Operation application** — `create_file` and `replace_line_range` handlers work correctly.
4. ✅ **Schema validation** — catches malformed responses.
5. ✅ **Full validation runner** — `cargo fmt`, `cargo check`, `cargo test`, `cargo clippy` all execute.
6. ✅ **End-to-end success demonstrated** — R2: generation → schema → semantic → preview → approve → apply → cargo build/test/clippy all pass.

### What Needs Improvement

1. ❌ **Cargo.toml formatting** — the model produces inline tables with newlines, which TOML parsers reject. Add "keep all TOML dependency entries on a single line" to the generation system prompt.
2. ❌ **Refactoring prompts** — the model struggles with complex multi-step refactors. Consider breaking the refactor into smaller slices or improving the prompt structure.
3. ❌ **`max_tokens` may be too low** — refactoring operations with full file content may exceed 4096 tokens. Consider increasing to 8192 for complex refactors.
4. ❌ **Model didn't add test first** — R2's prompt asked to "first add a failing test" but the model went straight to the fix. The evaluation prompt needs strengthening for multi-step instructions.

### Recommendations

1. **Tweak generation system prompt:**
   - Add: "For Cargo.toml files, keep all dependency entries on a single line. Do NOT use multi-line inline tables."
   - Add: "If the task requires multiple steps (e.g., add test THEN fix code), execute them in order as separate operations."
2. **Increase `max_tokens` to 8192** for complex refactoring slices.
3. **Test with higher temperature (0.3)** for creative refactoring tasks.
4. **Add a `language` field to the generation prompt** so the model knows which language it's generating code for.

---

## Appendix: Run Artifacts

### R1 Artifacts
```
_acceptance_runs/run-r1/.forgerwrite/runs/run_20260613_0001/
├── operation_batch.json      — 2 create_file operations
├── preview.diff              — 5.2 KB diff
├── approval_record.json      — auto-approved
├── validation_result.json    — fmt failed (TOML inline table error)
├── context_packet.json       — context sent to model
└── local_model_raw_attempt_1.txt — raw model response
```

### R2 Artifacts
```
_acceptance_runs/run-r2/.forgerwrite/runs/run_20260613_0002/
├── operation_batch.json      — 1 replace_line_range operation
├── preview.diff              — small diff (line 4 changed)
├── approval_record.json      — auto-approved
├── validation_result.json    — ALL PASSED (fmt, check, test, clippy)
├── context_packet.json       — context with buggy src/lib.rs
└── local_model_raw_attempt_1.txt — raw model response
```

### R3 Artifacts
```
_acceptance_runs/run-r3/.forgerwrite/runs/run_20260613_0003/
├── context_packet.json       — context built (generation never completed)
└── (no generation artifacts)
```
