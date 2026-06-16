# ADR-0001: Public Name is ForgeWrite

**Status:** Accepted
**Date:** 2026-06-13

## Decision

The public product name is **ForgeWrite**. The internal Python package
`forgerwrite_mcp/` will be renamed to `forgewrite_mcp/` in a future
ADR when import-compatibility concerns are resolved.

## Scope

- README, docstrings, CLI help text, MCP tool descriptions: "ForgeWrite"
- Config directory `.forgerwrite/`: stays for now
- Python package `forgerwrite_mcp/`: stays for now
- CLI binary `forgerwrite`: stays for now

## Rationale

"ForgeWrite" is cleaner English than "ForgerWrite" when spoken aloud. The extra "r"
in "ForgerWrite" was a typo that stuck. Fixing it now prevents 9 phases
of documentation drift.

## Known Technical Debt (documented, not fixed in this ADR)

- RAG enrichment is duplicated in `fw_generate_operations_local` (server.py)
  and `SliceCoordinator._generate_operations()` (coordinator.py). The
  coordinator already accepts an `enricher` parameter. The server tool's
  direct enrichment path should be merged into the coordinator in Phase 3.
