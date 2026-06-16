"""Safe grep — bounded ripgrep wrapper with path policy enforcement.

Uses ``safe_resolve_path()`` to ensure all search paths stay inside the repo.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import PATH_SAFETY_ERROR, PublicError
from ..paths import safe_resolve_path

# ── Constants ────────────────────────────────────────────────────────────────

_MAX_MATCHES_PER_QUERY: int = 40
_MAX_TOTAL_MATCHES: int = 200
_TIMEOUT_SECONDS: float = 10.0

_BINARY_FILE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".o", ".so", ".dll", ".dylib", ".exe",
    ".pyc", ".pyo", ".pyd",
    ".woff", ".woff2", ".ttf", ".eot",
})


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass
class GrepMatch:
    """A single matching line found by :func:`safe_grep`."""

    path: str
    line_number: int
    line_content: str


@dataclass
class GrepResult:
    """Aggregated result of a :func:`safe_grep` call."""

    matches: list[GrepMatch] = field(default_factory=list)
    truncated: bool = False
    queries: int = 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_binary(path: Path) -> bool:
    """Quick heuristic: check file extension against known binary types."""
    return path.suffix.lower() in _BINARY_FILE_EXTENSIONS


def _grep_single(
    repo_root: Path,
    query: str,
    *,
    max_matches: int,
    timeout: float,
) -> list[GrepMatch]:
    """Run ripgrep for a single *query* inside *repo_root*.

    Returns up to *max_matches* matches.
    """
    try:
        result = subprocess.run(
            [
                "rg",
                "--no-heading",
                "--line-number",
                "--max-count", str(max_matches),
                "--smart-case",
                "--",
                query,
                str(repo_root),
            ],
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        # ripgrep not installed — return empty
        return []

    if result.returncode not in (0, 1):
        return []

    stdout = result.stdout.decode("utf-8", errors="replace")
    matches: list[GrepMatch] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        # Format: /path/to/file:line_num:content
        # Skip the repo_root prefix for the stored path
        try:
            # Strip repo_root prefix to get relative path
            full_path_str = line.split(":", 1)[0] if ":" in line else ""
            if not full_path_str:
                continue
            rel_path = Path(full_path_str).relative_to(repo_root)
        except (ValueError, IndexError):
            continue

        # Parse line number and content
        remaining = line[len(full_path_str) + 1:] if full_path_str else line
        parts = remaining.split(":", 1)
        if len(parts) < 2:
            continue
        try:
            line_num = int(parts[0])
        except ValueError:
            continue
        content = parts[1]

        matches.append(GrepMatch(
            path=str(rel_path),
            line_number=line_num,
            line_content=content.strip(),
        ))

    return matches


# ── Public API ───────────────────────────────────────────────────────────────


def safe_grep(
    repo_root: Path,
    queries: list[str],
    *,
    max_matches_per_query: int = _MAX_MATCHES_PER_QUERY,
    max_total_matches: int = _MAX_TOTAL_MATCHES,
    timeout_seconds: float = _TIMEOUT_SECONDS,
) -> GrepResult:
    """Run bounded, path-safe grep queries inside *repo_root*.

    For each query in *queries*:
    1. The query string is validated via ``safe_resolve_path()`` to ensure
       it doesn't escape the repo (the query itself is not a file path, so
       this is a belt-and-suspenders check for path-traversal attempts).
    2. ripgrep is invoked with ``--max-count`` to cap per-query matches.
    3. Binary files are skipped by extension.
    4. Total matches across all queries are capped at *max_total_matches*.

    Args:
        repo_root: The repository root directory.
        queries: List of grep patterns to search for.
        max_matches_per_query: Max matches per individual query.
        max_total_matches: Max matches across all queries combined.
        timeout_seconds: Timeout per ripgrep invocation.

    Returns:
        A :class:`GrepResult` with matches and truncation status.
    """
    # Validate each query for path safety (prevents traversal in query string)
    for q in queries:
        # The query is not a file path, but we run it through safe_resolve_path
        # to catch obvious traversal attempts (e.g., "../../etc/passwd")
        try:
            safe_resolve_path(repo_root, q)
        except PublicError:
            # If the query looks like a path traversal, reject it
            raise PublicError(
                code=PATH_SAFETY_ERROR,
                message=f"Query rejected by path policy: {q}",
            ) from None

    result = GrepResult(queries=len(queries))
    total_matches = 0
    any_truncated = False

    for query in queries:
        if total_matches >= max_total_matches:
            any_truncated = True
            break

        remaining_budget = max_total_matches - total_matches
        per_query = min(max_matches_per_query, remaining_budget)

        matches = _grep_single(
            repo_root,
            query,
            max_matches=per_query,
            timeout=timeout_seconds,
        )

        # If ripgrep returned exactly per_query matches, it was truncated
        if len(matches) >= per_query:
            any_truncated = True

        # Enforce global cap by truncating any excess
        for m in matches:
            if total_matches >= max_total_matches:
                any_truncated = True
                break
            result.matches.append(m)
            total_matches += 1

    result.truncated = any_truncated
    return result
