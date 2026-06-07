---
name: stack
description: Technology stack, library choices, and the reasoning behind them. Load when working with specific technologies or making decisions about libraries and tools.
triggers:
  - "library"
  - "package"
  - "dependency"
  - "which tool"
  - "technology"
edges:
  - target: context/decisions.md
    condition: when the reasoning behind a tech choice is needed
  - target: context/conventions.md
    condition: when understanding how to use a technology in this codebase
last_updated: 2026-06-07
---

# Stack

## Core Technologies
- **Python 3.12** — primary language; requires `>=3.12`
- **FastMCP** (`mcp[cli]>=1.0.0`) — MCP server over stdio JSON-RPC
- **Pydantic v2** — typed config models with `Annotated` + `Field` constraints
- **jsonschema 4.x** — Draft 2020-12 contract validation; `Draft202012Validator` (NOT deprecated `RefResolver`)
- **httpx 0.27.x+** — async HTTP client for llama.cpp backend
- **Typer 0.12.x+** — typed CLI with `--json` flag on all commands
- **Rich 13.x+** — syntax-highlighted terminal output for diffs and summaries

## Key Libraries
- **pytest 9.x** (not unittest) — all tests use pytest style; `pytest-asyncio` for async tests
- **ruff 0.6.x+** (not flake8/black) — lint + format; `line-length = 100`
- **mypy 1.x** — review-grade type checking; `--strict` in CI
- **pip-audit** — dependency vulnerability scanning
- **hatchling** — build backend for `pyproject.toml`
- **uv** — package manager and resolver; `uv sync`, `uv run`, `uv pip install`

## What We Deliberately Do NOT Use
- No SQLite in MVP — JSON + Markdown artifacts are the source of truth (ADR-005)
- No Docker in MVP — only for optional daemon packaging in mature beta
- No `shell=True` — all subprocess calls use `shlex.split` + `shell=False`
- No `RefResolver` — deprecated in jsonschema 4.x; use `Draft202012Validator` directly
- No `print()` to stdout in MCP server — corrupts stdio protocol; `_redirect_stdout_to_stderr()` at boot

## Version Constraints
- Python: `>=3.12` (uses `tomllib`, `Annotated`, `@runtime_checkable`)
- jsonschema: `4.x` (Draft 2020-12 support; Draft 2019-09 deprecated)
- httpx: `>=0.27.0` (async HTTP/2 support)
