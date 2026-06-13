"""RAG retriever — queries the turbovec index and returns relevant documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RagDocument:
    """A single retrievable document in the RAG index."""

    doc_id: str
    title: str
    content: str
    source: str = "curated"

    @property
    def embeddable_text(self) -> str:
        """Text used for embedding. Title + content for semantic search."""
        return f"{self.title}\n{self.content}"


class RagRetriever:
    """Retrieves relevant documents from a RAG index.

    Wraps a turbovec index and an embedding model to turn queries into
    ranked document results.
    """

    def __init__(self, *, index: object, model: object, documents: list[RagDocument]) -> None:
        self._index = index
        self._model = model
        self._docs = documents

    def retrieve(self, query: str, k: int = 5) -> list[RagDocument]:
        """Return the top-k most relevant documents for a query.

        Args:
            query: Natural language search query.
            k: Number of documents to retrieve.

        Returns:
            List of RagDocument, sorted by relevance (most relevant first).
        """
        import numpy as np

        emb = np.array([self._model.encode(query)]).astype(np.float32)
        _scores, indices = self._index.search(emb, k=min(k, len(self._docs)))
        return [self._docs[i] for i in indices[0] if i < len(self._docs)]
