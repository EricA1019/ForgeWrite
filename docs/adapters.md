# Language Adapters

Language adapters provide language-specific validation commands and profiles. Each adapter is a class that satisfies the `LanguageAdapter` protocol.

## RustAdapter

Provides cargo-based validation for Rust projects.

- **Language:** `rust`
- **Default profile:** `rust_default`

### Commands

| Command ID | Shell Command |
|-----------|---------------|
| `fmt` | `cargo fmt -- --check` |
| `check` | `cargo check` |
| `test` | `cargo test` |
| `clippy` | `cargo clippy --all-targets --all-features -- -D warnings` |

### Profiles

| Profile | Commands |
|---------|----------|
| `rust_default` | fmt, check, test, clippy |

## PythonAdapter

Provides ruff/pytest/mypy-based validation for Python projects.

- **Language:** `python`
- **Default profile:** `python_default`

### Commands

| Command ID | Shell Command |
|-----------|---------------|
| `lint` | `ruff check .` |
| `format_check` | `ruff format --check .` |
| `test` | `pytest -q` |
| `typecheck` | `mypy forgerwrite_mcp/` |

### Profiles

| Profile | Commands |
|---------|----------|
| `python_default` | lint, format_check, test, typecheck |

## Configuration

Validation commands and profiles are configured in `[validation]` section of `.forgerwrite/forgerwrite.toml`. When running `forgerwrite init`, the template is populated from the language adapter for the selected language.

## Extending

To add a new language adapter, create a class in `forgerwrite_mcp/languages/` that implements the `LanguageAdapter` protocol:

```python
class MyAdapter:
    language: str = "my_lang"

    def get_validation_commands(self) -> dict[str, str]:
        return {"check": "my_checker"}

    def get_default_profile_name(self) -> str:
        return "default"

    def get_profiles(self) -> dict[str, list[str]]:
        return {"default": ["check"]}
```

Register it in `forgerwrite_mcp/languages/__init__.py`.
