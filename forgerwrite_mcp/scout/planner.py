"""Query planner — generates grep queries from a natural-language question.

Two modes:
1. **Model-assisted** — calls the local LLM to generate targeted grep queries.
2. **Deterministic fallback** — extracts keywords heuristically (reuses
   ``_extract_queries`` from the coordinator module).

The planner always produces a valid list of query strings. If the model fails
or returns invalid output, the deterministic fallback is used.
"""
from __future__ import annotations

from .coordinator import _extract_queries

# ── Constants ────────────────────────────────────────────────────────────────

_MAX_QUERIES: int = 8


def _plan_with_model(question: str, max_queries: int) -> list[str] | None:
    """Call the local model to produce grep queries from *question*.

    Returns a list of query strings, or ``None`` if the model call fails
    or returns invalid output.

    The model call is wrapped with a 10-second timeout to avoid hanging
    when the server is unavailable.
    """
    try:
        import asyncio
        from pathlib import Path

        import httpx

        from ..config import load_config
        from ..llama_client import LlamaCppClient

        config = load_config(Path.cwd())
        endpoint = config.local_model.endpoint.rstrip("/")

        # Quick health check before making the full model call
        try:
            health_url = f"{endpoint}/models"
            with httpx.Client(timeout=2.0) as hc:
                resp = hc.get(health_url)
                resp.raise_for_status()
        except Exception:
            return None

        client = LlamaCppClient.from_config(config.local_model)

        system_prompt = (
            "You are a code search query planner. Given a natural-language "
            "description of a coding task, produce a list of grep queries "
            "that would find the relevant code.\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            '{"queries": ["query1", "query2", ...]}\n\n'
            "Rules:\n"
            f"- Return at most {max_queries} queries.\n"
            "- Each query should be a short keyword or phrase (2-4 words).\n"
            "- Use identifiers, function names, error messages, or code patterns.\n"
            "- Do NOT include file paths — those go in allowed_files, not queries.\n"
            "- Do NOT include explanation, markdown, or any text outside the JSON."
        )

        async def _call() -> str:
            return await client.generate_operation_batch(
                system_prompt=system_prompt,
                user_prompt=f"Task: {question}\n\nProduce grep queries.",
            )

        raw = asyncio.run(asyncio.wait_for(_call(), timeout=10.0))

        import json

        parsed = json.loads(raw)
        queries: list[str] = parsed.get("queries", [])

        if not isinstance(queries, list) or len(queries) == 0:
            return None

        # Clean and validate
        valid: list[str] = []
        for q in queries:
            if isinstance(q, str) and q.strip() and len(q.strip()) >= 2:
                valid.append(q.strip())

        return valid[:max_queries] if valid else None

    except Exception:
        return None


def plan_queries(
    question: str,
    *,
    max_queries: int = _MAX_QUERIES,
    use_model: bool = True,
) -> list[str]:
    """Generate grep queries from a natural-language *question*.

    If *use_model* is ``True`` (default), attempts the local LLM first.
    Falls back to deterministic keyword extraction when the model is
    unavailable, returns invalid output, or *use_model* is ``False``.

    Args:
        question: Natural-language description of what to find.
        max_queries: Maximum number of queries to return.
        use_model: Whether to attempt model-assisted planning.

    Returns:
        A list of query strings (always at least 1 if question is non-empty).
    """
    if not question.strip():
        return []

    if use_model:
        model_queries = _plan_with_model(question, max_queries)
        if model_queries is not None:
            return model_queries

    # Deterministic fallback
    return _extract_queries(question)[:max_queries]
