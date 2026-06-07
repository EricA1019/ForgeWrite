---
name: decisions
description: Key architectural and technical decisions with reasoning. Load when making design choices or understanding why something is built a certain way.
triggers:
  - "why do we"
  - "why is it"
  - "decision"
  - "alternative"
  - "we chose"
edges:
  - target: context/architecture.md
    condition: when a decision relates to system structure
  - target: context/stack.md
    condition: when a decision relates to technology choice
last_updated: 2026-06-07
---

# Decisions

## Decision Log

### ADR-001 Python MCP First, Rust Harness Later
**Date:** 2026-06-06
**Status:** Active
**Decision:** Implement MVP as Python 3.12 MCP server with separate CLI; extract safety-critical mutation to Rust in mature beta.
**Reasoning:** Fast iteration with MCP SDK; Rust rewrite only if MVP validates the model workflow.
**Alternatives considered:** Rust from day one (slower prototyping), shell scripts (unsafe, unmaintainable).
**Consequences:** Mutation code must be small and heavily tested. MCP interface stabilizes before Rust rewrite.

### ADR-002 llama.cpp as First Backend
**Date:** 2026-06-06
**Status:** Active
**Decision:** Use llama.cpp server with OmniCoder 9B as first local backend; abstract behind `LocalModelBackend` Protocol in mature beta.
**Reasoning:** Best control over schema/grammar; GPT-GGUF compatibility; no vendor lock-in.
**Alternatives considered:** Ollama (less control), KoboldCPP (less structured coding focus), LM Studio (not automation-first).
**Consequences:** MVP assumes llama.cpp is externally launched. Retry + circuit breaker built into `LlamaCppClient`.

### ADR-003 Structured JSON Operations First
**Date:** 2026-06-06
**Status:** Active
**Decision:** Require structured JSON operation batches (6 types); unified diff fallback disabled by default.
**Reasoning:** Strong validation; op-level logs; scope checks per operation.
**Alternatives considered:** Unified diff first (harder semantic validation, bigger blast area), full file replacement only (poor reviewability).
**Consequences:** 6 operation handlers registered via `OperationRegistry`. `allow_unified_diff_fallback: false` by default.

### ADR-004 Clean Worktree Required Before Mutation
**Date:** 2026-06-06
**Status:** Active
**Decision:** ForgeWrite refuses preview/apply unless `git status --porcelain` is clean; re-checked before apply (TOCTOU).
**Reasoning:** Simple, safe, easy restore. Prevents misattribution of changes.
**Alternatives considered:** Allow dirty allowed files (harder attribution), auto-stash (surprising, hard to debug).
**Consequences:** `assert_clean_worktree()` called in both `_preview()` and `_apply()`. Snapshot system enables clean rollback.

### ADR-005 JSON Logs First, SQLite as an Index Later
**Date:** 2026-06-06
**Status:** Active
**Decision:** JSON + Markdown artifacts are the source of truth; SQLite added in mature beta as queryable index only.
**Reasoning:** Debuggable; no migration burden; every run is file-inspectable.
**Alternatives considered:** SQLite first (slower iteration, migration overhead).
**Consequences:** SQLite additions cannot remove JSON files. Artifacts in `.forgerwrite/runs/<run_id>/`.

### ADR-006 No Remote Infrastructure in Product
**Date:** 2026-06-06
**Status:** Active
**Decision:** Local-first, single-user. Kubernetes, Redis, multi-region, Terraform explicitly out of scope.
**Reasoning:** Adding remote infrastructure to a local tool inflates scope, hides risk behind YAML, delays user value.
**Consequences:** No remote collectors, no cloud provisioning. Mature beta may add optional daemon mode (Docker-only).

### ADR-007 Phase 0 Spike GO Decision
**Date:** 2026-06-07
**Status:** Pending — spike reports not yet written.
**Decision:** TO BE CONFIRMED after spike reports are written.
**Reasoning:** Spike directories exist but contain no reports. Retrospective reports needed.
**Consequences:** Phase 0 exit gate not formally passed. Blocking issue B2 in audit.
