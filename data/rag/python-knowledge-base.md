# ForgeWrite Python Knowledge Base

> Seed documents for the RAG index. Each `###` section is a self-contained
> retrieval unit. Split on `###` boundaries for embedding + indexing.
>
> Sources: Python 3.12, CPython Docs, Pydantic v2, pytest 9, httpx, typer, FastMCP.
> Last updated: 2026-06-16.

---

## 1. Operation Templates

Every operation the model produces MUST follow these templates exactly.
The `content` field is mandatory for all operations except `delete_file`.

<!-- RAG-ID: py-op-template-create_file -->
### create_file — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "create_file",
      "path": "src/calculator.py",
      "content": "\"\"\"Calculator module.\"\"\"\n\nfrom __future__ import annotations\n\n\ndef add(a: int, b: int) -> int:\n    return a + b\n"
    }
  ]
}
```
Rules: `path` must be in `allowed_files` from slice contract. Relative to repo root.
Parent directories created automatically. Do NOT include `start_line`, `end_line`,
`after_line`, or `before_line`.

<!-- RAG-ID: py-op-template-replace_file -->
### replace_file — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "replace_file",
      "path": "src/main.py",
      "content": "\"\"\"Entry point.\"\"\"\n\nfrom __future__ import annotations\n\n\ndef main() -> None:\n    print(\"hello\")\n\n\nif __name__ == \"__main__\":\n    main()\n"
    }
  ]
}
```
Rules: Replaces the ENTIRE file content. Include complete new file. Target MUST exist.
Do NOT include line-number fields.

<!-- RAG-ID: py-op-template-replace_line_range -->
### replace_line_range — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "replace_line_range",
      "path": "src/main.py",
      "start_line": 5,
      "end_line": 8,
      "content": "    for i in range(1, 6):\n        print(i)\n"
    }
  ]
}
```
Rules: `start_line` and `end_line` are 1-indexed and INCLUSIVE. Both required.
`content` required. Use line numbers from file context. Count blank lines.

<!-- RAG-ID: py-op-template-insert_after_line -->
### insert_after_line — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "insert_after_line",
      "path": "src/main.py",
      "after_line": 1,
      "content": "import sys\n"
    }
  ]
}
```
Rules: `after_line` is 1-indexed. Content appears AFTER this line.
`after_line: 0` inserts at beginning of file. `content` required.

<!-- RAG-ID: py-op-template-insert_before_line -->
### insert_before_line — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "insert_before_line",
      "path": "src/main.py",
      "before_line": 3,
      "content": "# Copyright notice\n"
    }
  ]
}
```
Rules: `before_line` is 1-indexed. Content appears BEFORE this line. `content` required.

<!-- RAG-ID: py-op-template-delete_file -->
### delete_file — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "delete_file",
      "path": "src/old_module.py"
    }
  ]
}
```
Rules: No `content` field needed. Target MUST exist. When recreating a file: use
`delete_file` FIRST, then `create_file` SECOND. Never create then delete.

---

## 2. Project Scaffolds

<!-- RAG-ID: py-scaffold-pyproject-toml -->
### pyproject.toml — PEP 621 template
```toml
[project]
name = "<package-name>"
version = "0.1.0"
description = "<description>"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```
Rules: Use `hatchling` as build backend (default for new projects). `requires-python`
MUST be `>=3.12`. Dependency names: lowercase, no version constraints in MVP.
Use `src/` layout when the package has multiple public modules.

<!-- RAG-ID: py-scaffold-init -->
### __init__.py — package init template
```python
"""Package docstring."""

from __future__ import annotations

from .module import PublicClass, public_function

__all__ = ["PublicClass", "public_function"]
```
Rules: ALWAYS include `from __future__ import annotations` as the first import
(standard for 3.12). `__all__` is optional but preferred for public APIs.

<!-- RAG-ID: py-scaffold-main -->
### __main__.py — entry point template
```python
"""CLI entry point for ``python -m <package>``."""

from __future__ import annotations

from .cli import app

if __name__ == "__main__":
    app()
```

<!-- RAG-ID: py-scaffold-ci -->
### CI workflow — pytest + ruff + mypy
```yaml
- name: Check
  run: |
    uv run ruff check .
    uv run mypy src/
    uv run pytest tests/ -q
```

---

## 3. Python Rules & Conventions

<!-- RAG-ID: py-import-rules -->
### Import and module rules
- ALWAYS put `from __future__ import annotations` as the first import (PEP 604).
- Standard library imports come FIRST, then third-party, then local (ruff I001).
- Use absolute imports: `from package.module import Name` — NOT relative imports.
- `import` for stdlib modules: `import os`, `import sys`, `import typing`.
- `from` for specific names: `from collections.abc import Iterator`.
- Group imports with a blank line between stdlib / third-party / local groups.

```python
from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from mypackage.module import MyClass
```

<!-- RAG-ID: py-type-annotations -->
### Type annotation rules (mypy strict)
- Always annotate function parameters and return types.
- Use `| None` instead of `Optional[X]`: `def f(x: int | None = None) -> str:`
- Use `list[X]` instead of `List[X]` (PEP 585 — built-in generics in 3.12).
- Use `dict[str, X]` instead of `Dict[str, X]`.
- Use `set[X]` instead of `Set[X]`.
- Use `tuple[X, ...]` instead of `Tuple[X, ...]`.
- Use `type[X]` instead of `Type[X]`.
- Use `collections.abc.Iterator` instead of `typing.Iterator`.
- Use `typing.Final` for constants: `MAX_RETRIES: Final = 5`.
- Use `typing.ClassVar` for class variables: `counter: ClassVar[int] = 0`.
- Use `typing.Protocol` for structural subtyping (duck typing).
- Use `typing.Any` sparingly — prefer `object` if truly unconstrained.

<!-- RAG-ID: py-async-patterns -->
### Async/await patterns
- Use `async def` for async functions, `def` for sync.
- Use `await` only inside `async def`.
- Use `asyncio.run(main())` as entry point — NOT `loop.run_until_complete()`.
- Use `asyncio.gather(*tasks)` for concurrent awaits, NOT `asyncio.create_task` + `await` separately.
- Use `asyncio.timeout()` (3.12+) for timeouts: `async with asyncio.timeout(10):`.
- Use `anyio`-compatible APIs when library supports it (e.g., httpx).

```python
import asyncio
from __future__ import annotations


async def fetch(url: str) -> str:
    async with asyncio.timeout(10):
        return await make_request(url)


async def main() -> None:
    result = await fetch("https://example.com")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

<!-- RAG-ID: py-context-managers -->
### Context manager patterns
- Use `with` for resource cleanup: files, locks, HTTP clients.
- Always use `contextlib.contextmanager` or `contextlib.asynccontextmanager` for custom
  context managers (NOT `__enter__`/`__exit__` manually unless needed).

```python
from contextlib import contextmanager


@contextmanager
def managed_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)
```

<!-- RAG-ID: py-exception-handling -->
### Exception handling rules
- Catch specific exceptions: `except ValueError:` — NOT bare `except:`.
- Use `raise ... from exc` for chaining: B904 lint rule.
- Use `try/except/finally` for cleanup that must run regardless.
- Prefer `contextlib.suppress(Exception)` over empty `except: pass`.

```python
try:
    result = risky_operation()
except ValueError as exc:
    raise CalculationError("invalid input") from exc
```

<!-- RAG-ID: py-naming-conventions -->
### Naming conventions
- Modules: snake_case (`calculator.py`, `git_utils.py`).
- Classes: PascalCase (`SliceCoordinator`, `ContractRegistry`).
- Functions: verb-first snake_case (`load_config`, `build_context_packet`).
- Constants: UPPER_SNAKE_CASE (`MAX_RETRIES`, `DEFAULT_TIMEOUT`).
- Private: underscore prefix (`_internal_func`, `_private_var`).
- Dunder: `__init__`, `__str__`, `__repr__`, `__enter__`, `__exit__`.

---

## 4. Library Usage Patterns

<!-- RAG-ID: py-lib-pydantic-v2 -->
### Pydantic v2 — data models
```python
from __future__ import annotations

from pydantic import BaseModel, Field


class User(BaseModel):
    name: str
    age: int = Field(ge=0, le=150)
    tags: list[str] = []


user = User(name="Alice", age=30)
```
Rules: Use v2 syntax only. Do NOT use v1 `validator` decorator — use `@field_validator`
and `@model_validator` from `pydantic`. Use `Field(...)` for validation constraints
(`gt`, `ge`, `lt`, `le`, `min_length`, `max_length`, `pattern`).
Use `model_config = ConfigDict(frozen=True)` for immutable models.
Use `Annotated[...]` for reusable constraints:

```python
from typing import Annotated
from pydantic import Field, BaseModel

PositiveInt = Annotated[int, Field(ge=0)]

class Stats(BaseModel):
    count: PositiveInt
```

<!-- RAG-ID: py-lib-httpx -->
### httpx — async HTTP client
```python
from __future__ import annotations

import httpx


async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```
Rules: Use `AsyncClient` as context manager. Set explicit timeout. Call
`raise_for_status()` to check for HTTP errors. Use `client.post(...)` for POST
requests with `json=` parameter. For concurrent requests, reuse a single client:

```python
async with httpx.AsyncClient() as client:
    results = await asyncio.gather(*[
        client.get(url) for url in urls
    ])
```

<!-- RAG-ID: py-lib-typer -->
### typer — CLI framework
```python
from __future__ import annotations

import typer
from typing import Annotated
from pathlib import Path

app = typer.Typer()


@app.command()
def greet(
    name: str,
    age: Annotated[int, typer.Option(help="Age in years")] = 0,
    config: Annotated[Path | None, typer.Option()] = None,
) -> None:
    typer.echo(f"Hello {name}")


if __name__ == "__main__":
    app()
```
Rules: Use `typer.Option()` and `typer.Argument()` for parameters. Use
`Annotated[type, typer.Option()]` for rich metadata. Use `typer.echo()` instead
of `print()`. Use `typer.Exit(code=1)` for error exits.
Use `app = typer.Typer()` at module level.

<!-- RAG-ID: py-lib-pytest -->
### pytest — testing patterns
```python
from __future__ import annotations

from pathlib import Path

import pytest
from mypackage.calculator import add


def test_add() -> None:
    assert add(2, 3) == 5


class TestCalculator:
    """Group related tests in a class."""

    def test_add_positive(self) -> None:
        assert add(1, 2) == 3

    def test_add_negative(self) -> None:
        assert add(-1, 1) == 0


@pytest.fixture
def sample_data(tmp_path: Path) -> Path:
    """Create a temp file for testing."""
    f = tmp_path / "data.txt"
    f.write_text("hello")
    return f


def test_with_fixture(sample_data: Path) -> None:
    assert sample_data.read_text() == "hello"


@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
])
def test_parametrized(a: int, b: int, expected: int) -> None:
    assert add(a, b) == expected
```
Rules: Test files in `tests/` directory. Name test files `test_<module>.py`.
Name test functions `test_<thing>`. Use `tmp_path` fixture for temp files.
Use `pytest.mark.parametrize` for multiple cases. Use `pytest.raises(Exception)`
for expected errors. Use `conftest.py` for shared fixtures.

<!-- RAG-ID: py-lib-fastmcp -->
### FastMCP — MCP server tools
```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

server = FastMCP("my-server")


@server.tool()
def my_tool(name: str) -> str:
    """Do something useful."""
    return f"Hello, {name}!"


@server.resource("config://app")
def get_config() -> str:
    return '{"setting": "value"}'
```
Rules: Tool functions are sync or async. Docstring becomes the tool description.
Parameters are automatically typed. Return JSON-serializable types.
Use `FastMCP("name")` at module level. Register with `server.run("stdio")`.

---

## 5. Fix Patterns (Repair Loop)

<!-- RAG-ID: py-fix-b904 -->
### Fix: B904 — raise-without-from-identifier
Error: `B904: Within `except` clause, raise exceptions with `raise ... from err``
Fix: Add `from exc` when raising a new exception inside an `except` block.

```python
# WRONG
except ValueError as exc:
    raise CalculationError("invalid")

# CORRECT
except ValueError as exc:
    raise CalculationError("invalid") from exc
```

<!-- RAG-ID: py-fix-f401 -->
### Fix: F401 — imported but unused
Error: `F401: 'os' imported but unused`
Fix: Remove the unused import, or prefix with `_` if needed for side effects.

```python
# WRONG
import os  # never used

# CORRECT (if side effect needed)
import os as _os  # noqa: F401

# CORRECT (remove)
# import os
```

<!-- RAG-ID: py-fix-n806 -->
### Fix: N806 — variable in function should be lowercase
Error: `N806: Variable 'MAX_RETRIES' in function should be lowercase`
Fix: UPPER_CASE constants belong at module level, not inside functions.

```python
# WRONG
def connect() -> None:
    MAX_RETRIES = 5  # N806

# CORRECT
MAX_RETRIES: Final = 5

def connect() -> None:
    for _ in range(MAX_RETRIES):
        ...
```

<!-- RAG-ID: py-fix-e501 -->
### Fix: E501 — line too long
Error: `E501: Line too long (120 > 100)`
Fix: Break the line. Use parentheses for implicit continuation:

```python
# WRONG
result = some_function(with_a_very_long_argument_list_that_exceeds_the_limit_by_a_lot)

# CORRECT
result = some_function(
    with_a_very_long_argument_list_that_exceeds_the_limit_by_a_lot,
)
```

<!-- RAG-ID: py-fix-mypy-type-arg -->
### Fix: mypy — missing type arguments
Error: `Missing type parameters for generic type "list"`
Fix: Use `list[X]` instead of bare `list`:

```python
# WRONG
def process(items: list) -> None: ...

# CORRECT
def process(items: list[str]) -> None: ...
```

<!-- RAG-ID: py-fix-mypy-return -->
### Fix: mypy — missing return type annotation
Error: `Function is missing a return type annotation`
Fix: Add `-> None` for void functions, or specify the actual return type:

```python
# WRONG
def main(): ...

# CORRECT
def main() -> None: ...
```

<!-- RAG-ID: py-fix-import-order -->
### Fix: I001 — import block is un-sorted
Error: `I001: Import block is un-sorted or un-formatted`
Fix: Run `ruff check --fix`. Group stdlib / third-party / local with blank lines.
Within each group, sort alphabetically.

```python
# ruff will auto-fix this. Run: uv run ruff check --fix
```

---

## 6. Operation Batch Structure

<!-- RAG-ID: py-schema-operation-batch -->
### Full operation batch structure
```json
{
  "batch_id": "<unique-string>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "<op-type>",
      "path": "<relative-path>",
      "content": "<file-or-insertion-content>"
    }
  ]
}
```
Required top-level fields: `batch_id`, `slice_id`, `operations` (non-empty array).
Each operation requires: `op` and `path`.
`content` required for: `create_file`, `replace_file`, `replace_line_range`,
`insert_after_line`, `insert_before_line`. NOT used for `delete_file`.

<!-- RAG-ID: py-rules-operation-ordering -->
### Operation ordering
- Operations applied IN ORDER (top to bottom).
- Delete + recreate: `delete_file` BEFORE `create_file`.
- Create + modify: `create_file` BEFORE `insert_*` / `replace_*`.
- Multiple ops on same file: account for line shifts from prior ops.

<!-- RAG-ID: py-rules-content-escaping -->
### Content escaping rules
- Content is a JSON string. Escape double quotes: `\"`
- Use `\n` for newlines (NOT actual newlines in JSON).
- Content field should be EXACT text written to file.
- Python triple-quoted strings in content MUST use `\"\"\"` escaping:
  `"\"\"\"Module docstring.\"\"\"\n"` becomes file content `"""Module docstring."""`

---

## 7. Quick Reference Card

<!-- RAG-ID: py-quickref-all-ops -->
### All operation types — quick reference
| op | Required fields | Use case |
|----|----------------|----------|
| `create_file` | op, path, content | New file, doesn't exist yet |
| `replace_file` | op, path, content | Overwrite entire existing file |
| `replace_line_range` | op, path, start_line, end_line, content | Replace specific lines |
| `insert_after_line` | op, path, after_line, content | Insert after a line |
| `insert_before_line` | op, path, before_line, content | Insert before a line |
| `delete_file` | op, path | Remove a file |

<!-- RAG-ID: py-quickref-tools -->
### Python toolchain quick reference
| Tool | Version | Config file | Key command |
|------|---------|-------------|-------------|
| Python | 3.12.8 | — | `python3 -m <module>` |
| uv | latest | `pyproject.toml` | `uv run <script>` |
| ruff | 0.15+ | `[tool.ruff]` | `uv run ruff check .` |
| mypy | 2.1+ | `[tool.mypy]` | `uv run mypy src/` |
| pytest | 9.0+ | `[tool.pytest.ini_options]` | `uv run pytest tests/ -q` |

<!-- RAG-ID: py-quickref-stdlib -->
### Standard library imports — common modules
| Module | Use case |
|--------|----------|
| `pathlib.Path` | File path operations (NOT `os.path`) |
| `typing.Annotated` | Rich type annotations |
| `typing.Final` | Constants |
| `typing.ClassVar` | Class variables |
| `typing.Protocol` | Structural subtyping |
| `collections.abc.Iterator` | Iterator type |
| `contextlib.contextmanager` | Context manager decorator |
| `contextlib.suppress` | Ignore specific exceptions |
| `dataclasses.dataclass` | Data containers |
| `json` | JSON serialization |
| `re` | Regular expressions |
| `asyncio` | Async runtime |
| `subprocess` | Shell commands |

<!-- RAG-ID: py-quickref-project-types -->
### Project type detection
| Detected in repo | Language | Adapter | Notes |
|------------------|----------|---------|-------|
| `pyproject.toml` or `setup.py` or `setup.cfg` | Python | PythonAdapter | `--language python` |
| `Cargo.toml` | Rust | RustAdapter | `--language rust` |
| Neither | unknown | default | Requires `--language` flag |
