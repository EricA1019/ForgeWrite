# Spike B — MCP stdio Server Minimal Viable

**Date:** 2026-06-07 (retrospective)
**Status:** GO
**ADR:** ADR-007

---

## Question

Does FastMCP over stdio work cleanly in VS Code without protocol corruption?

## Method

1. Built a minimal FastMCP server with `fw_ping` and `fw_echo` tools.
2. Configured `.vscode/mcp.json` to launch it via `uv run forgerwrite-mcp`.
3. Confirmed tool calls round-trip between VS Code and server.
4. Tested: `print()` inside a tool handler — confirmed it corrupts stdio.
5. Added `_redirect_stdout_to_stderr()` at server boot — confirmed corruption is prevented.

## Results

| Test | Result |
|------|--------|
| Tool call round-trip | ✅ Working |
| `print()` without redirect | ❌ Corrupts stdio (confirmed) |
| `print()` with redirect | ✅ No corruption |

## Decision: GO

The stdout-to-stderr redirect is effective and mandatory. The implementation
uses `os.dup2(sys.stderr.fileno(), sys.stdout.fileno())` at server boot.

## Implementation

- `forgerwrite_mcp/server.py:boot()`
- `_redirect_stdout_to_stderr()` called before `mcp.run(transport="stdio")`
- All errors use `envelope_from()` → public error codes only

## Known limitations

- Any code that bypasses the redirect (e.g., C extensions writing to fd 1)
  could still corrupt stdio. No such code exists in the codebase.
- Logging must use stderr or file sinks, never stdout.
