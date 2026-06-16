---
name: router
description: Session bootstrap and navigation hub. Read at the start of every session before any task. Contains project state, routing table, and behavioural contract.
edges:
  - target: context/architecture.md
    condition: when working on system design, integrations, or understanding how components connect
  - target: context/stack.md
    condition: when working with specific technologies, libraries, or making tech decisions
  - target: context/conventions.md
    condition: when writing new code, reviewing code, or unsure about project patterns
  - target: context/decisions.md
    condition: when making architectural choices or understanding why something is built a certain way
  - target: context/setup.md
    condition: when setting up the dev environment or running the project for the first time
  - target: patterns/INDEX.md
    condition: when starting a task — check the pattern index for a matching pattern file
last_updated: 2026-06-13
---

# Session Bootstrap

If you haven't already read `AGENTS.md`, read it now — it contains the project identity, non-negotiables, and commands.

Then read this file fully before doing anything else in this session.

## Current Project State

**Working:**
- 14-state SliceCoordinator pipeline (validate → context → generate → schema → semantic → preview → approve → apply → validate → repair)
- Schema repair loop: retries on schema/semantic errors (missing fields, wrong types)
- 12 MCP tools over stdio with stdout-to-stderr redirect (fw_turbovec_health, fw_turbovec_index)
- 13 CLI commands (init, doctor, approve, show-diff, inspect, restore, abort, gc, runs list, project status, build-index)
- 6 operation handlers via registry
- 8 config sections with Pydantic validation
- Git snapshot create/restore with TOCTOU re-check
- Hash-bound terminal approval with fcntl file locking
- LlamaCppClient with retry + circuit breaker, JSON extraction from reasoning_content
- Gemma 4 12B QAT (Q4_K_XL) on RTX 3060 via CUDA
- RAG pipeline: 5 modules (preprocessor, index, retriever, enricher, factory)
- 251+14 = **265 unit tests, 0 failures**
- Async-safe coordinator (run_async + _maybe_repair_async)
- RAG health checks in doctor
- Naming ADR (ADR-0001)
- **LanguageAdapter Seam** — RustAdapter + PythonAdapter, adapter discovery, `--language` flag on `init`
- **Python Dogfood** — P1-P3, P5 complete; P4 attempted (model JSON issue); acceptance report committed

**Not yet built:**
- Full external doc index (rebuild via `forgerwrite build-index`, ~500 docs, ~2-3 min CPU)
- Production deployment / persistent hosting

**Not yet built:**
- Full external doc index (rebuild via `forgerwrite build-index`, ~500 docs, ~2-3 min CPU)
- Production deployment / persistent hosting

**Known issues:**
- Gemma 4 12B Q4 produces valid JSON with json_object but may still omit fields on first attempt; schema repair loop retries

**Resolved debt:**
- PV1: ✅ Verified — `test_permission_rule_reads_config_*` (2 tests pass)
- PV2: ✅ Fixed — added `run_async()` + `_maybe_repair_async()`, `run()` delegates via `asyncio.run()`

**Known debt (deferred to Phase 3):**
- RAG enrichment duplicated in server tool (`fw_generate_operations_local`) and coordinator — two code paths

**Implementation plan:** `docs/implementation-plan.md` (design reference)
**Handoff (DeepSeek Flash):** `docs/handoff/phase-0-handoff.md` (copy-paste executable tasks)
- Phase 0: Stabilize (PV1/PV2, naming, TurboVec MCP tools, RAG health in doctor) ✅
- Phase 1: Rust MVP Acceptance (3 formal slices) — ⚠️ See `docs/acceptance/rust.md`
- Phase 2: Language Adapter Seam (Protocol + Rust/Python adapters)
- Phase 3: Python Dogfood (5 slices) — ✅ P1-P3, P5 complete; P4 LLM issue documented
- Phase 4: Scout v1 (evidence pipeline, safe_grep, scout_packet)
- Phase 5: Model-Assisted Scout (planner + summarizer + fallback)
- Phase 6: Saved Work KB (knowledge entries, TurboVec-indexed, DeepSeek-curated)
- Phase 7: Integrations + RC (MEX/Graphify/Headroom adapters, docs, release tag)
- Phase 8+ (deferred): Third language, package rename, production hosting

## Routing Table

Load the relevant file based on the current task. Always load `context/architecture.md` first if not already in context this session.

| Task type | Load |
|-----------|------|
| Understanding how the system works | `context/architecture.md` |
| Working with a specific technology | `context/stack.md` |
| Writing or reviewing code | `context/conventions.md` |
| Making a design decision | `context/decisions.md` |
| Setting up or running the project | `context/setup.md` |
| Any specific task | Check `patterns/INDEX.md` for a matching pattern |

## Behavioural Contract

For every task, follow this loop:

1. **CONTEXT** — Load the relevant context file(s) from the routing table above. Check `patterns/INDEX.md` for a matching pattern. If one exists, follow it. Narrate what you load: "Loading architecture context..."
2. **BUILD** — Do the work. If a pattern exists, follow its Steps. If you are about to deviate from an established pattern, say so before writing any code — state the deviation and why.
3. **VERIFY** — Load `context/conventions.md` and run the Verify Checklist item by item. State each item and whether the output passes. Do not summarise — enumerate explicitly.
4. **DEBUG** — If verification fails or something breaks, check `patterns/INDEX.md` for a debug pattern. Follow it. Fix the issue and re-run VERIFY.
5. **GROW** — After completing the task:
   - If no pattern exists for this task type, create one in `patterns/` using the format in `patterns/README.md`. Add it to `patterns/INDEX.md`. Flag it: "Created `patterns/<name>.md` from this session."
   - If a pattern exists but you deviated from it or discovered a new gotcha, update it with what you learned.
   - If any `context/` file is now out of date because of this work, update it surgically — do not rewrite entire files.
   - Update the "Current Project State" section above if the work was significant.
