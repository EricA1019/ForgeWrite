---
name: setup
description: Dev environment setup and commands. Load when setting up the project for the first time or when environment issues arise.
triggers:
  - "setup"
  - "install"
  - "environment"
  - "getting started"
  - "how do I run"
  - "local development"
edges:
  - target: context/stack.md
    condition: when specific technology versions or library details are needed
  - target: context/architecture.md
    condition: when understanding how components connect during setup
last_updated: 2026-06-07
---

# Setup

## Prerequisites
- Python 3.12+ (`python --version`)
- uv package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git 2.40+
- Rust toolchain (`rustup show` — needed for validation commands)
- llama.cpp server with OmniCoder 9B Q8 (see `docs/llama-cpp-setup.md`)
- Node.js 20+ (for MEX scaffold tooling only)

## First-time Setup
1. `uv sync --group dev` — install Python deps + dev tools
2. `uv run forgerwrite init` — scaffold `.forgerwrite/` with config
3. Edit `.forgerwrite/forgerwrite.toml` — set llama.cpp endpoint
4. Launch llama.cpp server (see `docs/llama-cpp-setup.md`)
5. `uv run forgerwrite doctor` — verify environment
6. `uv run pytest -q` — run 180 tests to confirm everything works

## Environment Variables
- `FORGERWRITE_ROOT` (optional) — override project root directory; defaults to cwd

## Common Commands
- `uv run forgerwrite-mcp` — start MCP server over stdio
- `uv run forgerwrite <command>` — CLI (init, doctor, approve, inspect, etc.)
- `uv run pytest -q` — run all tests (180+)
- `uv run pytest tests/<file>.py -v` — run specific test file
- `uv run ruff check .` — lint only (no auto-fix)
- `uv run ruff format --check .` — format check only
- `uv run mypy forgerwrite_mcp/ --strict` — type check
- `uv run pip-audit` — dependency vulnerability scan

## Common Issues
**"Config not found" on CLI commands:** Run `uv run forgerwrite init` first. The `.forgerwrite/` directory must exist at the repo root.
**MCP server not connecting in VS Code:** Verify `.vscode/mcp.json` exists and `FORGERWRITE_ROOT` points to the workspace.
**"Worktree is not clean" on preview/apply:** Commit or stash changes. ForgerWrite requires a clean git status.
**llama.cpp unreachable:** Check the server is running: `curl http://127.0.0.1:8080/health`. Verify `endpoint` in `.forgerwrite/forgerwrite.toml`.
**Import errors after git pull:** Run `uv sync --group dev` to refresh the venv.
