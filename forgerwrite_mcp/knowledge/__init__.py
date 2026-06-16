"""Knowledge module — Saved Work KB for ForgeWrite.

Stores reusable coding patterns extracted from successful runs.
File-backed JSON, one file per entry in ``.forgerwrite/knowledge/``.
"""

from __future__ import annotations

from .indexer import KnowledgeIndexer
from .promotion import promote_from_run
from .store import KnowledgeStore

__all__ = [
    "KnowledgeIndexer",
    "KnowledgeStore",
    "promote_from_run",
]
