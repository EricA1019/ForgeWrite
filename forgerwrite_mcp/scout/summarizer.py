"""Evidence summarizer — deduplicates, sorts, and caps evidence entries.

Reduces large evidence sets to a manageable size while preserving the most
relevant results.
"""
from __future__ import annotations

from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

_MAX_SUMMARY_LINES: int = 30


def summarize_evidence(
    evidence: list[dict[str, Any]],
    *,
    max_lines: int = _MAX_SUMMARY_LINES,
) -> list[dict[str, Any]]:
    """Deduplicate, sort, and cap *evidence* entries.

    1. Removes duplicates (same path + line_start).
    2. Sorts by path, then line_start.
    3. Caps at *max_lines* entries.

    Args:
        evidence: List of evidence dicts with at minimum ``path`` and
            ``line_start`` keys.
        max_lines: Maximum number of entries to return.

    Returns:
        A deduplicated, sorted, capped list of evidence dicts.
    """
    if not evidence:
        return []

    # Deduplicate by (path, line_start)
    seen: set[tuple[str, int]] = set()
    unique: list[dict[str, Any]] = []
    for entry in evidence:
        key = (entry.get("path", ""), entry.get("line_start", 0))
        if key not in seen:
            seen.add(key)
            unique.append(entry)

    # Sort by path, then line_start
    unique.sort(key=lambda e: (e.get("path", ""), e.get("line_start", 0)))

    # Cap
    return unique[:max_lines]
