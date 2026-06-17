# Isolated Run ID Pattern

**Problem:** Multiple preview→apply cycles collide when they share the same `run_id`, causing stale approval errors.

**Solution:** Use a unique `run_id` for each operation batch. The `fw_preview_operations` and `fw_apply_approved_operations` MCP tools accept an optional `run_id` parameter (default: `"preview"`).

**Example:**

```
fw_preview_operations(batch, slice, run_id="my-unique-id")
fw_apply_approved_operations(batch, slice, run_id="my-unique-id")
```

This creates an isolated run directory at `.forgerwrite/runs/my-unique-id/` with its own `approval_record.json`, `preview.diff`, and `audit.jsonl`.

**Language:** all
