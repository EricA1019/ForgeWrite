# Configuration Reference

ForgerWrite is configured via `.forgerwrite/forgerwrite.toml` at the repo root.

Run `forgerwrite init` to scaffold a complete config file.

---

## Full Configuration

```toml
[project]
name = "my-project"
language = "rust"
repo_root = "."

[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "omnicoder-9b"
temperature = 0.20
top_p = 0.90
top_k = 20
max_tokens = 2048
json_retries = 2
request_timeout_seconds = 180
retry_base_delay_seconds = 0.5
retry_max_delay_seconds = 8.0
retry_multiplier = 2.0

[limits]
context_file_max_bytes = 200000
context_total_max_bytes = 8000000
validation_output_max_chars = 16000
operation_batch_max_operations = 32
operation_content_max_bytes = 200000
artifact_retention_days = 90

[validation]
default_timeout_seconds = 300
graceful_kill_timeout_seconds = 5

[validation.commands]
fmt = "cargo fmt -- --check"
check = "cargo check"
test = "cargo test"
clippy = "cargo clippy --all-targets --all-features -- -D warnings"

[validation.profiles]
rust_default = ["fmt", "check", "test", "clippy"]

[permissions]
require_clean_worktree = true
allow_unknown_commands = false
require_approval_for_new_dependencies = true
require_approval_for_delete = true
require_approval_for_full_file_replace = true
allow_unified_diff_fallback = false

[hygiene]
generated_globs = ["target/**"]
vendor_globs = ["vendor/**"]

[repair]
max_attempts = 2
scope_must_match_original_slice = true
```

---

## Section Reference

### `[project]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Project name (used in artifacts) |
| `language` | string | yes | — | Primary language: `"rust"`, `"python"`, `"typescript"` |
| `repo_root` | string | no | `"."` | Path to repo root relative to config |

> **Note:** Setting `language = "python"` produces Python validation commands
> (`ruff check`, `ruff format --check`, `pytest -q`, `mypy --strict`).
> Use `forgerwrite init --language python` to scaffold a new Python project.

### `[local_model]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider` | string | yes | — | Backend provider: `"llama_cpp"` |
| `endpoint` | string | yes | — | HTTP endpoint URL (include `/v1`) |
| `model` | string | yes | — | Model name |
| `temperature` | float | no | `0.20` | Sampling temperature (0.0–2.0; Gemma 4: 1.0) |
| `top_p` | float | no | `0.90` | Nucleus sampling threshold (Gemma 4: 0.95) |
| `top_k` | int | no | `20` | Top-K sampling (Gemma 4: 64) |
| `max_tokens` | int | no | `2048` | Max output tokens (Gemma 4: 4096) |
| `json_retries` | int | no | `2` | Retries on invalid JSON |
| `request_timeout_seconds` | int | no | `180` | HTTP request timeout |
| `retry_base_delay_seconds` | float | no | `0.5` | Starting backoff delay |
| `retry_max_delay_seconds` | float | no | `8.0` | Maximum backoff delay |
| `retry_multiplier` | float | no | `2.0` | Backoff multiplier |

### `[limits]`

| Field | Type | Required | Default | Min | Description |
|-------|------|----------|---------|-----|-------------|
| `context_file_max_bytes` | int | no | `200000` | 64 | Max bytes per file in context packet |
| `context_total_max_bytes` | int | no | `8000000` | 10000 | Max total context packet size |
| `validation_output_max_chars` | int | no | `16000` | 1000 | Max chars of validation output captured |
| `operation_batch_max_operations` | int | no | `32` | 1 | Max operations per batch |
| `operation_content_max_bytes` | int | no | `200000` | 64 | Max content size per operation |
| `artifact_retention_days` | int | no | `90` | 1 | Days before `gc` cleans run directories |

### `[validation]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `default_timeout_seconds` | int | no | `300` | Per-command timeout |
| `graceful_kill_timeout_seconds` | int | no | `5` | Seconds between SIGTERM and SIGKILL |

### `[validation.commands]`

Key-value pairs mapping command names to shell commands. Commands are run with `shell=False` (tokenized). Example:

```toml
[validation.commands]
fmt = "cargo fmt -- --check"
check = "cargo check"
test = "cargo test"
```

### `[validation.profiles]`

Named groups of validation commands. The special profile `default` is used when no profile is specified.

```toml
[validation.profiles]
rust_default = ["fmt", "check", "test", "clippy"]
python_default = ["ruff", "mypy", "pytest"]
```

### `[permissions]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `require_clean_worktree` | bool | no | `true` | Require clean git status before operations |
| `allow_unknown_commands` | bool | no | `false` | Allow operations with unrecognized commands |
| `require_approval_for_new_dependencies` | bool | no | `true` | Extra approval for dependency changes |
| `require_approval_for_delete` | bool | no | `true` | Extra approval for file deletions |
| `require_approval_for_full_file_replace` | bool | no | `true` | Extra approval for `replace_file` |
| `allow_unified_diff_fallback` | bool | no | `false` | Enable unified diff operations (mature beta) |

### `[hygiene]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `generated_globs` | list[string] | no | `["target/**"]` | Glob patterns for generated directories |
| `vendor_globs` | list[string] | no | `["vendor/**"]` | Glob patterns for vendor/third-party directories |

### `[repair]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_attempts` | int | no | `2` | Maximum repair attempts per run |
| `scope_must_match_original_slice` | bool | no | `true` | Repair must stay within original slice scope |

### `[rag]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | no | `false` | Enable RAG prompt enrichment |
| `index_path` | string | no | `"data/rag/index.tqi"` | Path to turbovec index file |
| `k_documents` | int | no | `5` | Documents retrieved per query |
| `embedding_model_name` | string | no | `"Alibaba-NLP/gte-modernbert-base"` | SentenceTransformer model for embeddings |
| `max_rag_tokens` | int | no | `2048` | Token budget for injected knowledge |

Build the index: `forgerwrite build-index`

---

## Validation Profiles

Validation profiles let you define named groups of commands to run after applying operations. The `rust_default` profile is used by default for Rust projects:

```toml
[validation.commands]
fmt = "cargo fmt -- --check"
check = "cargo check"
test = "cargo test"
clippy = "cargo clippy --all-targets --all-features -- -D warnings"

[validation.profiles]
rust_default = ["fmt", "check", "test", "clippy"]
```

Profiles run commands in order and stop on the first failure (fail-fast).

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `FORGERWRITE_ROOT` | Override the project root directory |

---

## See Also

- [llama-cpp-setup.md](llama-cpp-setup.md) — Setting up the local model backend
- [operations.md](operations.md) — Operation types and JSON schema
