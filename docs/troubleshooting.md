# Troubleshooting Guide

Common issues when using ForgeWrite, with symptoms, causes, and fixes.

## Model Server

### `fw_generate_operations_local` fails with "All connection attempts failed"

**Symptom:** Operation generation returns `LOCAL_MODEL_ERROR` with connection errors.

**Likely cause:** The llama.cpp model server is not running.

**Fix:**
1. Check with `forgerwrite model-status` or `fw_model_health`.
2. If unhealthy, restart the model server:
   ```bash
   bash scripts/launch-gemma4.sh
   ```
3. Verify with `forgerwrite model-status` — should show `healthy: true` and a loaded model.

---

### Model server returns unhealthy but process is running

**Symptom:** `fw_model_health` says unhealthy, but `ps aux | grep llama` shows the server.

**Likely cause:** Wrong endpoint URL in config, or server started on a different port.

**Fix:**
1. Check `.forgerwrite/config.toml` → `[model]` section → `endpoint`.
2. Default is `http://localhost:8080`. Verify with `curl http://localhost:8080/v1/models`.
3. Update config if port differs.

---

## MCP Connection

### ForgeWrite MCP server won't start or hangs

**Symptom:** VS Code reports the MCP server is not responding, or `fw_ping` times out.

**Likely cause:** stdout pollution — anything printed to stdout breaks the JSON-RPC pipe.

**Fix:**
1. Ensure nothing prints to stdout in the server startup path.
2. Check that `forgerwrite_mcp/server.py` does not call `_redirect_stdout_to_stderr()` in `boot()`.
3. Restart the MCP server from VS Code settings.

---


### Index build hangs or times out

**Symptom:** `fw_turbovec_index` appears to do nothing and eventually times out.

**Cause:** Building the TurboVec index loads the SentenceTransformer model and computes embeddings for all KB documents. This is a CPU-bound operation that takes 5-30 seconds on first run and blocks the MCP response.

**Fix:** Run index building from the CLI instead, where blocking is acceptable:

```bash
forgerwrite build-index
```

**Note:** After the first call, the SentenceTransformer model is cached in memory. Subsequent `fw_turbovec_index` calls (or CLI calls) within the same process lifetime will be faster (only the embedding computation, not the model load).

### Some MCP tools are missing from the list

**Symptom:** `fw_model_health` or `fw_turbovec_index` not available.

**Likely cause:** Tool registration changed in a recent update; the MCP server needs restart.

**Fix:**
1. Restart the MCP server from VS Code.
2. Verify with `fw_ping` — if it works, the server is running.
3. Check the agent config (`.github/agents/forgewrite.agent.md`) matches current server tools.

---

## Validation Failures

### `fw_validate_operations` fails with CONTRACT_VALIDATION_ERROR

**Symptom:** Validation reports missing required properties or unexpected additional properties.

**Likely cause:** The operation batch doesn't match the JSON Schema.

**Fix:**
1. Read the error message — it tells you which field is missing or wrong.
2. Required fields: `schema_id` (must be `forgerwrite.operation_batch.v1`), `batch_id`, `slice_id`, `operations`.
3. Each operation needs `op` (one of: `create_file`, `replace_file`, `delete_file`, `insert_before_line`, `insert_after_line`, `replace_line_range`), `path`, and operation-specific fields.
4. Do NOT include `run_id` — that's set by the system.

---

### `fw_validate_operations` fails with SEMANTIC_VALIDATION_ERROR

**Symptom:** "Operation targets 'X' outside allowed_files".

**Likely cause:** The file path doesn't match the slice contract's `allowed_files` list.

**Fix:**
1. Check the slice contract's `allowed_files` — it must include every file your operations touch.
2. File paths are relative to the repo root.

---

## Operation Failures

### `fw_apply_approved_operations` fails with "Run not approved"

**Symptom:** Apply returns `APPROVAL_ERROR: Run not approved`.

**Likely cause:** The run was previewed but not approved via `forgerwrite approve`.

**Fix:**
1. Run `forgerwrite approve <run_id>` (e.g., `forgerwrite approve preview`).
2. Review the diff, then confirm with `y`.
3. Re-run `fw_apply_approved_operations`.

---

### `fw_apply_approved_operations` fails after a successful preview

**Symptom:** Apply returns `APPROVAL_ERROR` about TOCTOU or snapshot mismatch.

**Likely cause:** The file was modified between preview and apply (Time-of-Check to Time-of-Use).

**Fix:**
1. Re-run `fw_preview_operations` to get a fresh snapshot.
2. Approve the new preview with `forgerwrite approve`.
3. Apply immediately after approval — don't let the worktree change in between.

---

### `create_file` operation rejected for large content

**Symptom:** Validation fails with content size error.

**Likely cause:** Content exceeds the 200KB hard cap.

**Fix:**
1. Split large files into multiple `create_file` operations (each under 200KB).
2. Or use `insert_after_line` / `insert_before_line` to add content to an existing file piecemeal.

---

## Knowledge Base

### `fw_knowledge_search` returns empty results

**Symptom:** Search returns `total: 0` for a reasonable query.

**Likely cause:** No matching patterns exist in the KB yet, or the index is stale.

**Fix:**
1. After a successful run, promote it with `fw_knowledge_promote_from_run`.
2. Rebuild the RAG index with `forgerwrite build-index` or `fw_turbovec_index`.
3. The KB currently has 5 seed entries — coverage grows as you promote runs.

---

### `fw_generate_operations_local` returns invalid JSON

**Symptom:** The local model produces JSON that fails schema validation.

**Likely cause:** The model occasionally produces malformed JSON (common with smaller local models).

**Fix:**
1. This is handled automatically — the repair loop retries up to 2 times (configurable in `.forgerwrite/config.toml` → `[repair]` → `max_retries`).
2. If all retries fail, check the model server: `forgerwrite model-status`.
3. Increase `max_retries` in config if needed.

---

## Git / Worktree

### Preview or apply fails with "Worktree is not clean"

**Symptom:** `APPROVAL_ERROR` listing dirty or untracked files.

**Likely cause:** Uncommitted changes in the repo. ForgeWrite requires a clean git worktree.

**Fix:**
1. Run `git status` to see dirty files.
2. Commit or stash all changes.
3. Re-run the operation.

---

## Schema IDs

### Wrong `schema_id` prefix

**Symptom:** `CONTRACT_VALIDATION_ERROR` says `schema_id: 'forgerwrite.X.vY' was expected`.

**Fix:** Use `forgerwrite` (with 'r' after 'g'), NOT `forgewrite`:
- ✅ `forgerwrite.slice.v1`
- ✅ `forgerwrite.operation_batch.v1`
- ✅ `forgerwrite.handoff.v1`
- ❌ `forgewrite.slice.v1`
