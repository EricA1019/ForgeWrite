# Phase 7 — Dogfood Hardening Plan

**Date:** 2026-06-16
**Baseline:** 344 tests, 0 failures, v0.1.0-rc1 tagged
**Goal:** Fix every issue discovered during ForgeWrite self-use. Add defenses to prevent recurrence.

---

## Issues Found During Dogfood

| # | Issue | Root cause | When discovered |
|---|-------|-----------|----------------|
| H1 | MCP server hung on connect | `_redirect_stdout_to_stderr()` in `boot()` killed JSON-RPC | VS Code reconnect |
| H2 | Heredoc breaks large `create_file` | No content size validation — multi-KB strings break pipeline | TUI creation |
| H3 | Token tracker empty-return missing `by_model` | Two divergent return paths — no test covered empty path | Stats query |
| H4 | No end-to-end MCP protocol test | Only unit tests, never tested `tools/list` over stdio | Server debugging |
| H5 | `fw_scout` CLI never tested with real data | CLI tests only check `--help` output | Scout verification |
| H6 | Docs say "10 tools" but we have 21 | Docs drifted from reality across phases | README audit |
| H7 | Python heredoc corrupted during generation | Shell heredoc + Python triple-quoted strings conflict | Operation batch delivery |

---

## Task Breakdown

### H1: Remove dead redirect code + MCP smoke test

**What:** `_redirect_stdout_to_stderr()` was called in `boot()` and broke MCP JSON-RPC communication. The call was removed in Phase 7 hotfix, but the function and its tests remain as dead code. Remove both and add a proper integration test.

```
Files:
  forgerwrite_mcp/server.py        — Delete _redirect_stdout_to_stderr()
  tests/test_server.py             — Delete redirect tests, add MCP smoke tests

New tests (2):
  test_mcp_server_fw_ping_returns_ok()         — pipes initialize + tools/call
  test_mcp_server_tools_list_returns_all_tools() — pipes initialize + tools/list
```

Acceptance: Server boots and responds to `fw_ping` via stdio in under 2 seconds.

### H2: Content size validation

**What:** `create_file` handler accepts arbitrarily large content. Multi-KB strings break the operation batch pipeline (heredoc corruption, JSON encoding limits). Add a hard cap with a clear error message.

```
Files:
  forgerwrite_mcp/operations/create_file.py    — Add MAX_CONTENT_BYTES check
  tests/operations/test_create_file.py         — Add oversized-content test

New tests (1):
  test_create_file_rejects_content_over_100kb() — raises PublicError with clear message
```

Acceptance: Content > 100KB is rejected. Error message includes the actual vs. max sizes.

### H3: Dual-return coverage pattern

**What:** `TokenTracker.get_stats()` has two return paths (empty and populated). The empty path was missing the `by_model` key introduced in Phase 5.6. Fix is already applied — add guard test to prevent recurrence.

```
Files:
  tests/test_token_tracker.py    — Add empty-stats-keys test

New tests (1):
  test_empty_stats_has_all_required_keys() — verifies total_calls, by_purpose, by_model, estimated_savings
```

Acceptance: If a new stat key is added, the test fails until both return paths include it.

### H4: MCP integration tests

**What:** No test verifies the MCP server works over stdio. The `_redirect_stdout_to_stderr` bug went undetected because only unit tests exist. Add three stdio-pipe integration tests.

```
Files:
  tests/test_mcp_integration.py (new)         — 3 integration tests

New tests (3):
  test_mcp_initialize_returns_server_info()    — server name + version
  test_mcp_tools_list_returns_21_tools()       — count all registered tools
  test_mcp_fw_scout_grep_works()              — real grep via MCP protocol
```

Acceptance: All three tests pass using the real `forgerwrite-mcp` binary over stdio.

### H5: CLI integration tests

**What:** CLI tests only verify `--help` output. No test runs `forgerwrite scout` against real files or `forgerwrite token-stats` against real data.

```
Files:
  tests/test_cli.py    — Add real-data integration tests

New tests (2):
  test_scout_finds_evidence_in_source_tree()   — scout a known pattern in forgerwrite_mcp/
  test_token_stats_cli_shows_by_model()        — verify --json includes by_model key
```

Acceptance: Scout returns evidence matches for the project's own source tree. Token stats CLI returns by_model in JSON output.

### H6: Error envelope consistency audit

**What:** Most tools use `envelope_from()` but some may return raw dicts. Audit every tool and fix inconsistencies.

```
Files:
  forgerwrite_mcp/server.py    — Audit all 21 tool functions
  tests/test_server.py         — Add envelope consistency test (if not already)

New tests (1):
  test_all_tools_wrap_errors_in_envelope() — forces error in each tool, checks response format
```

Acceptance: Every tool error response has `{"ok": false, "error": {"code": "...", "message": "..."}}` format.

### H7: Doc staleness fix

**What:** README says "10 tools" — we have 21. Update all documentation to match current reality.

```
Files:
  README.md                  — Update tool count, tool list, test count
  docs/implementation-plan.md — Mark Phase 7 complete
  .mex/ROUTER.md             — Update project state
  forgerwrite_mcp/server.py  — Update docstring
  docs/release-notes-v0.1.0.md — Add hardening notes
```

Acceptance: README lists all 21 tools. Tool count matches actual registration count.

---

## Estimated Impact

| Task | New tests | Type | Risk |
|------|-----------|------|------|
| H1 | 2 | Integration (stdio pipe) | Low |
| H2 | 1 | Unit (create_file handler) | Low |
| H3 | 1 | Unit (token tracker guard) | Low |
| H4 | 3 | Integration (MCP protocol) | Medium — first stdio-pipe tests |
| H5 | 2 | Integration (CLI) | Low |
| H6 | 1 | Unit (error path) | Low |
| H7 | 0 | Documentation | None |

**Test count:** 344 → **~354**

---

## Execution Order

Dependency chain:
```
H7 (docs) ← independent, can run anytime
H3 (guard test) ← independent
H2 (content cap) ← independent
H1 (dead code) → H4 (MCP tests) ← H1 enables MCP to work
H5 (CLI tests) → H6 (envelope audit) ← depends on working CLI
```

Recommended: **H7 → H3 → H2 → H1 → H4 → H5 → H6**

---

## Kill Criteria

- [ ] All 354+ tests pass
- [ ] MCP server boots and responds to `tools/list` in < 3 seconds
- [ ] `create_file` rejects content > 100KB with clear error
- [ ] Zero occurrences of raw dict error returns in server.py
- [ ] `fw_scout` CLI finds real evidence in source tree
- [ ] README lists all 21 tools
- [ ] `by_model` present in both empty and populated `get_stats()` returns
