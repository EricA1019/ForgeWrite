"""Context packet builder — builds bounded input for the local writer.

Design reference: §5.4

Reads only allowed files, computes SHA256 hashes, enforces per-file and
total size limits, and respects hygiene globs.
"""

from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path
from typing import Any

from .config import HygieneConfig, LimitsConfig
from .errors import PublicError
from .paths import safe_resolve_path

# Error code for context building failures
_CONTEXT_ERROR_CODE: str = "CONTEXT_ERROR"


class ContextError(PublicError):
    """Context building failed due to size limits or forbidden files."""

    def __init__(self, message: str) -> None:
        super().__init__(code=_CONTEXT_ERROR_CODE, message=message)


def _is_excluded(rel_path: str, hygiene: HygieneConfig) -> bool:
    """Check if a relative path matches any exclusion glob."""
    all_globs = list(hygiene.generated_globs) + list(hygiene.vendor_globs)
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in all_globs)


def _sha256(text: str) -> str:
    """Compute SHA-256 hex digest of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_context_packet(
    repo_root: Path,
    handoff: dict[str, Any],
    slice_contract: dict[str, Any],
    limits: LimitsConfig,
    *,
    hygiene: HygieneConfig | None = None,
) -> dict[str, Any]:
    """Build a bounded context packet for the local model.

    Args:
        repo_root: Repository root directory.
        handoff: Handoff contract dict.
        slice_contract: Slice contract with allowed_files.
        limits: Size and count limits from config.
        hygiene: Exclusion patterns (defaults to empty if None).

    Returns:
        A context packet dict with handoff, slice, and files.

    Raises:
        ContextError: On forbidden files, size limit violations.
    """
    if hygiene is None:
        hygiene = HygieneConfig()

    allowed = slice_contract.get("allowed_files", [])
    forbidden = set(slice_contract.get("forbidden_files", []))

    # Reject forbidden files in allowed list
    overlap = set(allowed) & forbidden
    if overlap:
        raise ContextError(f"Forbidden files in allowed_files: {', '.join(sorted(overlap))}")

    files: dict[str, dict[str, str]] = {}
    total_bytes: int = 0

    for rel_path in allowed:
        # Resolve safely
        abs_path = safe_resolve_path(repo_root, rel_path)

        # Skip excluded paths (generated, vendor)
        if _is_excluded(rel_path, hygiene):
            continue

        if not abs_path.exists():
            raise ContextError(f"File not found: {rel_path}")

        content = abs_path.read_text(encoding="utf-8")
        size = len(content.encode("utf-8"))

        # Per-file limit
        if size > limits.context_file_max_bytes:
            raise ContextError(
                f"File {rel_path} ({size} bytes) exceeds per-file limit "
                f"({limits.context_file_max_bytes} bytes)"
            )

        # Total limit check (before adding)
        if total_bytes + size > limits.context_total_max_bytes:
            raise ContextError(
                f"Total context would exceed limit ({limits.context_total_max_bytes} bytes)"
            )

        files[rel_path] = {
            "content": content,
            "sha256": _sha256(content),
            "size_bytes": size,
        }
        total_bytes += size

    return {
        "handoff": handoff,
        "slice": slice_contract,
        "files": files,
    }
