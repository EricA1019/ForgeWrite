"""Path safety — single source of truth for all path resolution.

Every module that resolves a relative path inside a repo uses this module.
No other module implements its own path validation — DRY enforcement point.

Design reference: §5.2
"""

from __future__ import annotations

from pathlib import Path

from .errors import PATH_SAFETY_ERROR, PublicError


class PathSafetyError(PublicError):
    """A path violated safety constraints (traversal, escape, null byte)."""

    def __init__(self, message: str) -> None:
        super().__init__(code=PATH_SAFETY_ERROR, message=message)


def _reject_illegal_rel(rel_path: str) -> None:
    """Raise PathSafetyError if rel_path contains illegal patterns."""
    if not rel_path:
        raise PathSafetyError("Empty path")
    if rel_path.startswith("/") or rel_path.startswith("\\"):
        raise PathSafetyError(f"Absolute path rejected: {rel_path}")
    if "\x00" in rel_path:
        raise PathSafetyError(f"Null byte rejected: {rel_path!r}")
    parts = Path(rel_path).parts
    if ".." in parts:
        raise PathSafetyError(f"Traversal rejected: {rel_path}")


def safe_resolve_path(repo_root: Path, rel_path: str) -> Path:
    """Resolve a relative path safely within a repository root.

    Args:
        repo_root: The repository root directory.
        rel_path: A relative path string from the repository root.

    Returns:
        Resolved absolute Path guaranteed to be inside repo_root.

    Raises:
        PathSafetyError: If the path escapes the repo or contains illegal patterns.
    """
    _reject_illegal_rel(rel_path)
    root = repo_root.resolve(strict=False)
    candidate = (root / rel_path).resolve(strict=False)
    return assert_inside_repo(root, candidate)


def assert_inside_repo(repo_root: Path, candidate: Path) -> Path:
    """Assert that candidate is strictly inside repo_root (not equal to it).

    Returns the resolved candidate on success.
    """
    root = repo_root.resolve()
    cand = candidate.resolve()
    if cand == root:
        raise PathSafetyError("Path resolves to repo root, not a file inside it")
    # Check that root is an ancestor of cand
    if root not in cand.parents and cand != root:
        raise PathSafetyError(f"Path escapes repo: {cand}")
    return cand
