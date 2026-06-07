# Operations Reference

ForgerWrite uses **structured JSON operation batches** for all file mutations. The local model must produce a JSON object matching the `operation_batch.v1.json` schema.

---

## Operation Batch Schema

```json
{
  "schema_id": "forgerwrite.operation_batch.v1",
  "handoff_id": "<uuid>",
  "slice_id": "<uuid>",
  "operations": [
    { "...": "..." }
  ]
}
```

---

## Operation Types

### 1. `create_file`

Create a new file. Fails if the file already exists.

```json
{
  "op": "create_file",
  "path": "src/new_module.rs",
  "content": "pub fn hello() {\n    println!(\"Hello\");\n}\n"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | yes | Must be `"create_file"` |
| `path` | string | yes | Relative path from repo root |
| `content` | string | yes | UTF-8 file content |

---

### 2. `replace_file`

Replace the entire content of an existing file.

```json
{
  "op": "replace_file",
  "path": "src/lib.rs",
  "content": "pub mod new_module;\n"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | yes | Must be `"replace_file"` |
| `path` | string | yes | Relative path, must exist |
| `content` | string | yes | Complete new file content |

Security: `replace_file` requires `require_approval_for_full_file_replace = true` in config.

---

### 3. `replace_line_range`

Replace a contiguous range of lines (1-indexed, inclusive).

```json
{
  "op": "replace_line_range",
  "path": "src/main.rs",
  "start_line": 5,
  "end_line": 10,
  "content": "    // New implementation\n    let x = compute();\n"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | yes | Must be `"replace_line_range"` |
| `path` | string | yes | Relative path, must exist |
| `start_line` | integer | yes | 1-indexed start line (inclusive) |
| `end_line` | integer | yes | 1-indexed end line (inclusive) |
| `content` | string | yes | Replacement text |

---

### 4. `insert_after_line`

Insert content after a specific line. The line must exist.

```json
{
  "op": "insert_after_line",
  "path": "src/main.rs",
  "line": 3,
  "content": "    let config = load_config()?;\n"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | yes | Must be `"insert_after_line"` |
| `path` | string | yes | Relative path, must exist |
| `line` | integer | yes | 1-indexed line number to insert after |
| `content` | string | yes | Text to insert |

---

### 5. `insert_before_line`

Insert content before a specific line. The line must exist.

```json
{
  "op": "insert_before_line",
  "path": "src/main.rs",
  "line": 1,
  "content": "// Copyright 2026\n// SPDX-License-Identifier: MIT\n\n"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | yes | Must be `"insert_before_line"` |
| `path` | string | yes | Relative path, must exist |
| `line` | integer | yes | 1-indexed line number to insert before |
| `content` | string | yes | Text to insert |

---

### 6. `delete_file`

Remove a file from the repository.

```json
{
  "op": "delete_file",
  "path": "src/deprecated.rs"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | yes | Must be `"delete_file"` |
| `path` | string | yes | Relative path, must exist |

Security: `delete_file` requires `require_approval_for_delete = true` in config.

---

## Validation Rules

All operations are validated against these rules:

1. **Schema validation**: Must match `operation_batch.v1.json` (JSON Schema Draft 2020-12).
2. **Scope check**: All paths must be within the slice contract's `allowed_files`.
3. **Size check**: No single operation's `content` may exceed `limits.operation_content_max_bytes`.
4. **Forbidden targets**: No operation may target generated files (`hygiene.generated_globs`) or vendor files (`hygiene.vendor_globs`).
5. **Permission checks**: `delete_file` and `replace_file` operations require the corresponding config permission to be enabled.

---

## Error Codes

| Code | Meaning |
|------|---------|
| `OPERATION_APPLY_ERROR` | Operation application failed (e.g., file doesn't exist) |
| `CONTRACT_VALIDATION_ERROR` | Operation batch schema invalid |
| `VALIDATION_ERROR` | Semantic validation failed |
| `PATH_SAFETY_ERROR` | Path rejected by safety check |
