"""Dead letter writer — centralized module for unrecoverable failure records.

Design reference: §9.4

Used by SliceCoordinator and CLI abort to write dead_letter.json
when a run cannot be recovered.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_dead_letter(
    run_dir: Path,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> Path:
    """Write a dead_letter.json into the run directory.

    Args:
        run_dir: The run artifact directory.
        reason: Human-readable reason for the failure.
        payload: Optional structured data about the failure context.

    Returns:
        Path to the written file.
    """
    import json

    record = {
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }
    dest = run_dir / "dead_letter.json"
    dest.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return dest
