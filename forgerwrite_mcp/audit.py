"""Audit event writer — JSON Lines audit log per run.

Design reference: §12

Every approve, apply, restore, and abort action writes an audit event.
Events are appended to audit.jsonl in JSON Lines format (one JSON object per line).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_audit_event(
    run_dir: Path,
    event_type: str,
    details: dict[str, Any] | None = None,
) -> Path:
    """Append an audit event to the run's audit.jsonl file.

    Args:
        run_dir: The run artifact directory.
        event_type: One of 'approve', 'apply', 'restore', 'abort'.
        details: Optional structured details about the event.

    Returns:
        Path to the audit log file.
    """
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "details": details or {},
    }
    dest = run_dir / "audit.jsonl"
    line = json.dumps(event, default=str) + "\n"
    with dest.open("a", encoding="utf-8") as f:
        f.write(line)
    return dest
