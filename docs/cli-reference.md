# CLI Reference

All ForgeWrite CLI commands. Run `forgerwrite --help` for the latest list.

## Core Commands

### `init`

Scaffold `.forgerwrite/` directory and default config.

```bash
forgerwrite init
```

Creates `.forgerwrite/forgerwrite.toml` with all 8 config sections (project, local_model, limits, validation, permissions, hygiene, repair, rag).

---

### `doctor`

Check environment health: config validity, git availability, llama.cpp reachability, Rust toolchain.

```bash
forgerwrite doctor
```

Returns warnings for any missing or misconfigured components. Use before debugging issues.

---

### `approve` <run_id>

Approve a run after reviewing the preview diff. Required before `apply`.

```bash
forgerwrite approve preview        # approve most recent preview
forgerwrite approve --dry-run abc  # show diff without approving
forgerwrite approve --json abc     # output approval record as JSON
```

Options: `--dry-run`, `--json`, `--skip-doctor`

---

### `show-diff` <run_id>

Pretty-print the preview diff for a run.

```bash
forgerwrite show-diff preview
```

---

### `inspect` <run_id>

Print full Markdown summary of a run (artifacts, diff, validation results).

```bash
forgerwrite inspect abc123
```

---

## Run Management

### `restore` <run_id>

Restore the git snapshot taken before a run. Use to roll back a bad apply.

```bash
forgerwrite restore abc123
```

---

### `abort` <run_id>

Abort a run: restore the git snapshot and write a dead letter for audit.

```bash
forgerwrite abort abc123
```

---

### `gc`

Clean expired run directories and orphan snapshot refs.

```bash
forgerwrite gc
```

---

### `runs-list`

List all runs from JSON artifacts with status and timestamps.

```bash
forgerwrite runs-list
```

---

### `runs`

Subcommand group for run management. See `forgerwrite runs --help`.

---

## Discovery & Diagnostics

### `scout` <question>

Run Scout evidence discovery. Searches for relevant code patterns via ripgrep and RAG retrieval.

```bash
forgerwrite scout "error handling in create_file"
forgerwrite scout -f src/server.py -f src/coordinator.py "validation flow"
forgerwrite scout --use-model-planner --json "how does approve work?"
```

Options: `-f`/`--allowed-file` (repeatable), `--use-model-planner`, `--json`

---

### `token-stats`

Show accumulated token usage and cloud cost savings, with `by_model` and `by_purpose` breakdowns.

```bash
forgerwrite token-stats
```

---

### `tui`

Launch the ForgeWrite terminal dashboard (Textual TUI). Shows tokens, runs, KB status, and model health in real time.

```bash
forgerwrite tui
```

---

### `audit-report`

Analyze ForgeWrite audit logs from `.forgerwrite/runs/` and produce a report.

```bash
forgerwrite audit-report
forgerwrite audit-report --json
```

Options: `--json`, `--since` (ISO date), `--output` (file path)

---

### `model-status`

Check llama.cpp model server health and list loaded models.

```bash
forgerwrite model-status
```

Returns: `{healthy, endpoint, model_name, loaded_models, error}`

---

## Index Management

### `build-index`

Build or rebuild the RAG search index from knowledge base files.

```bash
forgerwrite build-index
```

---

## Project Management

### `project-status`

Show project config summary (language, validation profiles, paths).

```bash
forgerwrite project-status
```

### `project`

Subcommand group for project management. See `forgerwrite project --help`.

---

## MCP Tools vs CLI Commands

Some operations are only available via MCP tools, not CLI:

| MCP Tool | CLI Equivalent |
|----------|---------------|
| `fw_ping` | (none — MCP only) |
| `fw_model_health` | `model-status` |
| `fw_scout` | `scout` |
| `fw_token_stats` | `token-stats` |
| `fw_turbovec_health` | (none — MCP only) |
| `fw_turbovec_index` | `build-index` |
| `fw_validate_operations` | (none — MCP only) |
| `fw_preview_operations` | (none — MCP only) |
| `fw_apply_approved_operations` | (none — MCP only) |
| `fw_generate_operations_local` | (none — MCP only) |
| `fw_get_run_summary` | `inspect` |
| `fw_knowledge_*` | (none — MCP only) |
| `fw_run_validation_profile` | (none — MCP only) |
