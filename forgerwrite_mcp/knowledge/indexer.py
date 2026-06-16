"""Knowledge indexer — embeds knowledge entries for semantic search.

Uses the same gte-modernbert-base model as the RAG pipeline for consistency.
Entries are stored in a lightweight TurboQuantIndex for fast retrieval.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# ── Constants ────────────────────────────────────────────────────────────────

_EMBEDDING_MODEL: str = "Alibaba-NLP/gte-modernbert-base"
_DIM: int = 768
_BIT_WIDTH: int = 4


# ── KnowledgeIndexer ─────────────────────────────────────────────────────────


class KnowledgeIndexer:
    """Indexes knowledge entries for semantic search.

    Uses SentenceTransformer for embeddings and TurboQuantIndex for
    vector storage. Lightweight — does not share the full RAG pipeline.
    """

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._index: object | None = None
        self._model: object | None = None

    # ── Lazy init ──────────────────────────────────────────────────────────

    def _ensure_model(self) -> object:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(_EMBEDDING_MODEL, device="cpu")
        return self._model

    # ── Public API ──────────────────────────────────────────────────────────

    def index(self, entries: list[dict[str, Any]]) -> None:
        """Embed *entries* and build a searchable index.

        Each entry must have ``id``, ``title``, ``description``, and
        ``problem_statement`` keys.
        """
        if not entries:
            self._entries = []
            self._index = None
            return

        self._entries = list(entries)
        model = self._ensure_model()

        texts = [
            f"{e.get('title', '')}\n{e.get('description', '')}\n{e.get('problem_statement', '')}"
            for e in entries
        ]
        vectors = np.array(model.encode(texts, show_progress_bar=False)).astype(np.float32)

        from turbovec import TurboQuantIndex

        idx = TurboQuantIndex(dim=_DIM, bit_width=_BIT_WIDTH)
        idx.add(vectors)
        self._index = idx

    def search(self, query: str, *, k: int = 5) -> list[dict[str, Any]]:
        """Search for knowledge entries matching *query*.

        Returns up to *k* entries, ranked by semantic similarity.
        """
        if self._index is None or not self._entries:
            return []

        model = self._ensure_model()
        query_vec = np.array(model.encode([query], show_progress_bar=False)).astype(np.float32)

        scores, indices = self._index.search(query_vec, k=min(k, len(self._entries)))
        # scores and indices are (1, result_count) arrays
        results: list[dict[str, Any]] = []
        seen: set[int] = set()
        for idx_val in indices[0]:
            idx_int = int(idx_val)
            if 0 <= idx_int < len(self._entries) and idx_int not in seen:
                seen.add(idx_int)
                results.append(self._entries[idx_int])
            if len(results) >= k:
                break
        return results
