"""Scout — evidence discovery for ForgeWrite.

Runs before context building to gather evidence via ripgrep and RAG retrieval.
Produces a ``scout_packet.json`` with path:line evidence.
"""

from __future__ import annotations

from .coordinator import ScoutCoordinator
from .planner import plan_queries
from .safe_grep import GrepMatch, GrepResult, safe_grep
from .summarizer import summarize_evidence

__all__ = [
    "GrepMatch",
    "GrepResult",
    "ScoutCoordinator",
    "plan_queries",
    "safe_grep",
    "summarize_evidence",
]
