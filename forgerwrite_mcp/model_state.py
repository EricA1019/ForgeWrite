"""Model state persistence — remembers the last-used model configuration.

Stores model name, endpoint, and health history in
``.forgerwrite/model_state.json``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STATE_FILE: str = ".forgerwrite/model_state.json"


def load_last_model(repo_root: Path) -> dict[str, Any]:
    """Load the last-used model configuration.

    Returns a dict with ``model_name`` and ``endpoint``.
    Returns empty dict if no state file exists.
    """
    path = repo_root / _STATE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_model_state(
    repo_root: Path,
    model_name: str,
    endpoint: str,
    healthy: bool,
) -> None:
    """Save the current model configuration. Only writes on state change."""
    path = repo_root / _STATE_FILE
    data = {
        "model_name": model_name,
        "endpoint": endpoint,
        "healthy": healthy,
        "last_checked": datetime.now(UTC).isoformat(),
    }

    # Skip write if state is unchanged (avoid constant churn)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if (
                existing.get("model_name") == model_name
                and existing.get("endpoint") == endpoint
                and existing.get("healthy") == healthy
            ):
                return
        except (json.JSONDecodeError, OSError):
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
