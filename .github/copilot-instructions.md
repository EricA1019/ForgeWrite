---
name: agents
description: Always-loaded project anchor. Read this first. Contains project identity, non-negotiables, commands, and pointer to ROUTER.md for full context.
last_updated: 2026-06-16
---

# ForgeWrite

## What This Is
A local-first MCP coding service that delegates narrow file edit slices to a local LLM with hard safety rails.

## Non-Negotiables
- Never use direct file system operations — always use ForgeWrite MCP tools for file operations
- Always validate operations (`fw_validate_operations`) before preview (`fw_preview_operations`)
- Always run validation profile (`fw_run_validation_profile`) after applying operations
- Never bypass the coordinator for production workflows — MCP tool shortcuts are for dev/debug only
- Never modify `paths.py`, `forge/forge.py`, or `approval.py` — they are security chokepoints

## Commands
- Dev: `uv sync --group dev`
- Test: `uv run pytest tests/ -q`
- Lint: `uv run ruff check forgerwrite_mcp/ tests/`
- Format check: `uv run ruff format --check .`
- Type check: `uv run mypy forgerwrite_mcp/`
- All gates: `uv run ruff check forgerwrite_mcp/ tests/ && uv run mypy forgerwrite_mcp/ && uv run pytest tests/ -q`

## After Every Task
After completing any task: update `.mex/ROUTER.md` project state and any `.mex/` files that are now out of date. If no pattern existed for the task you just completed, create one in `.mex/patterns/`.

## Navigation
At the start of every session, read `.mex/ROUTER.md` before doing anything else.
For full project context, patterns, and task guidance — everything is there.
