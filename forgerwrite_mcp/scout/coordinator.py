"""ScoutCoordinator — runs the full Scout evidence pipeline.

Pipeline:
1. TurboVec RAG retrieval (if enricher available)
2. Safe grep on allowed files for relevant queries
3. Normalize evidence into exact_evidence with path:line format
4. Build ScoutPacket
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .safe_grep import safe_grep

# ── Constants ────────────────────────────────────────────────────────────────

_MAX_EVIDENCE_LINES: int = 50
_MAX_GREP_QUERIES: int = 10
_MAX_RETRIEVAL_HITS: int = 10


# ── ScoutPacket ──────────────────────────────────────────────────────────────


@dataclass
class ScoutPacket:
    """Evidence packet produced by a Scout run."""

    schema_id: str = "forgewrite.scout_packet.v1"
    question: str = ""
    retrieval_hits: list[dict[str, Any]] = field(default_factory=list)
    exact_evidence: list[dict[str, Any]] = field(default_factory=list)
    recommended_allowed_files: list[str] = field(default_factory=list)
    recommended_reads: list[dict[str, Any]] = field(default_factory=list)


# ── Query extraction ─────────────────────────────────────────────────────────


def _extract_queries(question: str) -> list[str]:
    """Extract grep queries from a natural-language question.

    Splits on common delimiters, extracts quoted phrases as single tokens,
    and returns non-empty, trimmed fragments suitable for ripgrep.
    """
    # First, extract quoted phrases as single tokens
    quoted = re.findall(r'"([^"]+)"', question)
    # Remove quoted parts from the question for further processing
    rest = re.sub(r'"[^"]+"', "", question)

    # Split remaining text on punctuation and whitespace
    parts = re.split(r"[?.,;!:\s]+", rest)
    queries: list[str] = []

    # Add quoted phrases first
    for q in quoted:
        q = q.strip()
        if q and len(q) > 1:
            queries.append(q)

    # Add meaningful individual words (3+ chars, not common stop words)
    _stop_words: frozenset[str] = frozenset({
        "the", "and", "for", "are", "was", "that", "this", "with",
        "find", "all", "from", "have", "has", "been",
    })
    for p in parts:
        p = p.strip().lower()
        if p and len(p) >= 3 and p not in _stop_words:
            queries.append(p)

    return queries[: _MAX_GREP_QUERIES]


# ── ScoutCoordinator ─────────────────────────────────────────────────────────


class ScoutCoordinator:
    """Runs Scout pipeline: TurboVec retrieval -> grep evidence -> packet."""

    def __init__(
        self,
        repo_root: Path,
        *,
        enricher: object | None = None,
        max_evidence_lines: int = _MAX_EVIDENCE_LINES,
        use_model_planner: bool = False,
    ) -> None:
        self._repo_root = repo_root
        self._enricher = enricher
        self._max_evidence_lines = max_evidence_lines
        self._use_model_planner = use_model_planner

    def scout(
        self,
        question: str,
        allowed_files: list[str] | None = None,
    ) -> ScoutPacket:
        """Run the full Scout pipeline and return an evidence packet."""
        from .planner import plan_queries
        from .summarizer import summarize_evidence

        packet = ScoutPacket(question=question)

        # 1. TurboVec retrieval
        if self._enricher is not None and hasattr(self._enricher, "_retriever"):
            try:
                retriever = self._enricher._retriever
                if retriever is not None:
                    docs = retriever.retrieve(question, k=_MAX_RETRIEVAL_HITS)
                    for doc in docs:
                        packet.retrieval_hits.append({
                            "doc_id": doc.doc_id,
                            "title": doc.title,
                            "snippet": doc.content[:200],
                        })
            except Exception:
                pass

        # 2. Extract grep queries (model-assisted or deterministic)
        queries = plan_queries(
            question,
            use_model=self._use_model_planner,
        )

        # 3. Safe grep on allowed files
        if allowed_files and queries:
            grep_queries: list[str] = []
            for af in allowed_files:
                grep_queries.append(af)
            grep_queries.extend(queries)

            grep_result = safe_grep(
                self._repo_root,
                grep_queries,
                max_matches_per_query=min(20, self._max_evidence_lines),
                max_total_matches=self._max_evidence_lines,
            )

            for m in grep_result.matches:
                packet.exact_evidence.append({
                    "path": m.path,
                    "line_start": m.line_number,
                    "line_end": m.line_number,
                    "finding": m.line_content,
                })

        # 4. Summarize evidence (deduplicate, sort, cap)
        packet.exact_evidence = summarize_evidence(
            packet.exact_evidence,
            max_lines=self._max_evidence_lines,
        )

        # 5. Recommend allowed files from grep hits
        paths_in_evidence = {e["path"] for e in packet.exact_evidence}
        packet.recommended_allowed_files = sorted(paths_in_evidence)

        return packet
