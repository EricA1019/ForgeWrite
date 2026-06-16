---
name: agents
description: Always-loaded project anchor. Read this first. Contains project identity, non-negotiables, commands, and pointer to ROUTER.md for full context.
last_updated: 2026-06-07
---

# ForgeWrite MCP

## What This Is
A local-first MCP coding service that delegates narrow file edit slices to a local LLM (llama.cpp + OmniCoder 9B) with hard safety rails — preview, hash-bound approval, TOCTOU guards, and bounded repair.

## Non-Negotiables
- Never write file mutations outside the operation handler registry — all mutations go through `safe_resolve_path` + `OperationHandler.apply`
- Never leak exception class names or raw messages — all errors use `PublicError` → `ErrorEnvelope` → `envelope_from()`
- Never use `shell=True` in subprocess calls — validation runner uses `shlex.split` + `shell=False`
- Never commit without passing `uv run pytest -q` and `uv run ruff check .`
- Never merge to main without updating `docs/project-state.md` and `.mex/` scaffold

## Commands
- Dev server (MCP): `uv run forgerwrite-mcp`
- CLI: `uv run forgerwrite <command>`
- Test: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format --check .`
- Type check: `uv run mypy forgerwrite_mcp/ --strict`
- Security audit: `uv run pip-audit`

## Scaffold Growth
After every task: if no pattern exists for the task type you just completed, create one. If a pattern or context file is now out of date, update it. The scaffold grows from real work, not just setup. See the GROW step in `ROUTER.md` for details.

## Navigation
At the start of every session, read `ROUTER.md` before doing anything else.
For full project context, patterns, and task guidance — everything is there.
