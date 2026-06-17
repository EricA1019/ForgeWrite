# Knowledge Base User Guide

The Saved Work Knowledge Base stores reusable patterns from successful ForgeWrite runs. It's indexed by TurboVec for semantic search.

## When to Use the KB

Before generating new operations, search the KB for patterns similar to your task. The KB often has the answer already — saving you a full generate → validate → repair cycle.

## MCP Tools

There are 6 KB-related MCP tools. All are in the `forgerwrite` namespace.

### fw_knowledge_search

Search the KB for patterns matching a natural-language query.

```
fw_knowledge_search(query="pytest fixture session scope", k=5)
```

Returns up to `k` matching entries with title, description, tags, and source run ID.

### fw_knowledge_get_entry

Retrieve a full entry by ID.

```
fw_knowledge_get_entry(entry_id="9dd20a4b-8666-4417-9b80-722e28a89a6f")
```

Returns the complete entry including operations and validation summary.

### fw_knowledge_save_entry

Save a new entry directly (without promoting from a run).

```
fw_knowledge_save_entry(entry={
    "schema_id": "forgewrite.knowledge_entry.v1",
    "title": "Your pattern title",
    "description": "Brief description",
    "tags": ["relevant", "tags"],
    "language": "python",
    "problem_statement": "What problem this solves",
    "operations": [...],
})
```

### fw_knowledge_promote_from_run

The standard promotion workflow: after a successful run, promote it to the KB.

```
fw_knowledge_promote_from_run(run_id="<run-uuid>", curator_notes="Optional notes about the pattern")
```

This reads the run artifacts (handoff, operation_batch, validation result), constructs a knowledge entry, validates it, and saves it.

### fw_knowledge_record_usage

Record whether a KB entry helped or didn't help.

```
fw_knowledge_record_usage(entry_id="...", outcome="helped", notes="Fixed the same issue in project X")
```

Outcome must be one of: `"helped"`, `"did_not_help"`, `"neutral"`.

### fw_knowledge_deprecate_entry

Mark an entry as deprecated (e.g., because a pattern was superseded).

```
fw_knowledge_deprecate_entry(entry_id="...")
```

## Promotion Workflow

1. Run a slice through the coordinator (or MCP tools)
2. Verify the run succeeded (validation passed)
3. Promote: `fw_knowledge_promote_from_run(run_id)`
4. Index into TurboVec: `fw_turbovec_index()`
5. The next `fw_knowledge_search` will find the new entry

## Seed Entries

The KB ships with 5 seed entries:

| Title | Language | Pattern |
|-------|----------|---------|
| Fix unresolved import | Rust | Use exact crate name from Cargo.toml |
| Fix pytest fixture scope | Python | Session-scoped fixtures for shared setup |
| Fix gen keyword edition 2024 | Rust | Use edition 2021 or r#gen() |
| Async HTTP client | Python | httpx.AsyncClient with context manager |
| Rust project scaffold | Rust | 5-file create_file batch |
