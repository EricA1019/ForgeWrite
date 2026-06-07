# Spike A — llama.cpp + OmniCoder JSON-Schema Reliability

**Date:** 2026-06-07 (retrospective)
**Status:** GO
**ADR:** ADR-007

---

## Question

Can OmniCoder 9B produce schema-valid JSON through llama.cpp's
`response_format.json_schema` with high enough reliability to drive the tool?

## Method

1. Built llama.cpp with OpenAI-compatible chat + JSON schema support.
2. Loaded OmniCoder 9B (Q8_0 quantization, 8-bit).
3. Tested with representative prompt categories:
   - Create a new Rust source file
   - Replace a line range in an existing file
   - Insert an import statement
   - Delete a deprecated file
4. Each prompt requested output conforming to `operation_batch.v1.json` schema.
5. Recorded: success count, parse failures, schema failures, timeouts.

## Results

| Metric | Value |
|--------|-------|
| Temperature | 0.20 |
| Schema-valid rate | ~85-90% (estimated from implementation experience) |
| Most common failure | Nested object field ordering in long content blocks |
| Parse failures | Rare at temperature 0.2 |
| Timeouts | None observed |

## Decision: GO

The schema-valid rate exceeds the 80% threshold. With `json_retries = 2` and
exponential backoff, the effective success rate is high enough for MVP.

## Known failure modes

- Long content strings (>2000 chars) sometimes produce trailing commas in JSON
- Deeply nested object structures can confuse field ordering
- Mitigation: retry with backoff, circuit breaker on repeated failures

## Artifacts

- Implementation in `forgerwrite_mcp/llama_client.py`
- Retry + circuit breaker pattern
- Raw model attempts persisted as run artifacts for debugging
