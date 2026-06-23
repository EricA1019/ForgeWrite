"""File-backed knowledge entry store.

One JSON file per entry in ``.forgerwrite/knowledge/<entry_id>.json``.
Follows ADR-005: JSON artifacts as source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

_KNOWLEDGE_DIR = ".forgerwrite/knowledge"


# ── KnowledgeStore ───────────────────────────────────────────────────────────


class KnowledgeStore:
    """File-backed store for knowledge entries.

    Each entry is a JSON file on disk. Thread-safe for reads, not for
    concurrent writes to the same entry.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root.resolve()
        self._knowledge_dir = self._repo_root / _KNOWLEDGE_DIR

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def knowledge_dir(self) -> Path:
        return self._knowledge_dir

    # ── CRUD ────────────────────────────────────────────────────────────────

    def save(self, entry: dict[str, Any]) -> None:
        """Persist a knowledge entry to disk.

        Overwrites any existing entry with the same ``id``.
        """
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        entry_id = entry.get("id", "")
        path = self._knowledge_dir / f"{entry_id}.json"
        path.write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Load a knowledge entry by ID. Returns ``None`` if not found."""
        path = self._knowledge_dir / f"{entry_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """List all knowledge entries, optionally filtered by *status*.

        Returns entries sorted by ``id``.
        """
        if not self._knowledge_dir.is_dir():
            return []
        entries: list[dict[str, Any]] = []
        for f in sorted(self._knowledge_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if status is None or data.get("status") == status:
                entries.append(data)
        return entries

    def deprecate(self, entry_id: str) -> None:
        """Set an entry's status to 'deprecated'. No-op if not found."""
        entry = self.get(entry_id)
        if entry is not None:
            entry["status"] = "deprecated"
            self.save(entry)

    def delete(self, entry_id: str) -> None:
        """Delete a knowledge entry file. No-op if not found."""
        path = self._knowledge_dir / f"{entry_id}.json"
        from contextlib import suppress

        with suppress(OSError):
            path.unlink(missing_ok=True)
