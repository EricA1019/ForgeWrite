"""RAG index — embeds documents and builds a turbovec search index."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from forgerwrite_mcp.rag.preprocessor import ProcessedDoc
from forgerwrite_mcp.rag.retriever import RagDocument

# Module-level SentenceTransformer cache — model load is expensive (~130MB, 5-10s)
# on first call. Subsequent calls reuse the cached instance.
_EMBEDDING_MODEL_CACHE: dict[str, object] = {}


def _get_embedding_model(
    model_name: str = "Alibaba-NLP/gte-modernbert-base",
    device: str = "cpu",
) -> object:
    """Get or create a cached SentenceTransformer instance."""
    key = f"{model_name}:{device}"
    if key not in _EMBEDDING_MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL_CACHE[key] = SentenceTransformer(model_name, device=device)
    return _EMBEDDING_MODEL_CACHE[key]


class RagIndex:
    """Builds and persists a turbovec index from preprocessed documents.

    Wraps :class:`turbovec.TurboQuantIndex` with embedding, save, and load.
    After ``build()`` the instance can be passed directly to
    :class:`~forgerwrite_mcp.rag.retriever.RagRetriever` as the ``index`` parameter.
    """

    def __init__(self, *, dim: int = 768, bit_width: int = 4) -> None:
        self._dim = dim
        self._bit_width = bit_width
        self._turbovec: object | None = None

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def bit_width(self) -> int:
        return self._bit_width

    # ── Search (delegated to turbovec) ─────────────────────────────────────

    def search(self, query_vectors: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Search for top-k nearest neighbours. Returns (scores, indices)."""
        if self._turbovec is None:
            raise RuntimeError("Index not built yet. Call build() first.")
        return self._turbovec.search(query_vectors, k=k)

    # ── Build ──────────────────────────────────────────────────────────────

    def build(self, documents: list[ProcessedDoc]) -> None:
        """Embed documents and build the search index.

        Creates embeddings via gte-modernbert-base, then builds a
        TurboQuantIndex. After this call the instance is usable as a
        :class:`RagRetriever` index.
        """
        if not documents:
            self._turbovec = None
            return

        from turbovec import TurboQuantIndex
        model = _get_embedding_model()

        # Truncate long documents to avoid CPU overload during embedding.
        # gte-modernbert-base has 8192 token context; we cap content at 2000
        # chars (~500 tokens) so the title + content fits comfortably.
        max_content_chars: int = 2000
        batch_size: int = 32
        texts: list[str] = []
        for d in documents:
            content = d.content[:max_content_chars]
            texts.append(f"{d.title}\n{content}")

        num_batches = (len(texts) + batch_size - 1) // batch_size
        print(f"  Embedding {len(texts)} documents on CPU in {num_batches} "
              f"batches (content capped at {max_content_chars} chars)...")

        all_vectors: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vecs = model.encode(batch, show_progress_bar=False)
            all_vectors.append(np.array(vecs).astype(np.float32))
            batch_num = i // batch_size + 1
            print(f"    Batch {batch_num}/{num_batches} done ({len(batch)} docs)", flush=True)
        vectors = np.concatenate(all_vectors, axis=0)

        print(f"  Building TurboQuantIndex ({self._dim}d, {self._bit_width}-bit)...")
        idx = TurboQuantIndex(dim=self._dim, bit_width=self._bit_width)
        idx.add(vectors)
        self._turbovec = idx

    # ── Persistence ────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Persist the turbovec index to disk using native binary format."""
        if self._turbovec is None:
            raise RuntimeError("Nothing to save — build() first.")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._turbovec.write(str(p))

    @classmethod
    def load(cls, path: str, *, documents: list[RagDocument]) -> RagIndex:
        """Load a persisted turbovec index from disk.

        Args:
            path: Path to the binary file written by ``save()``.
            documents: The document list that was indexed (not stored in the file).
        """
        from turbovec import TurboQuantIndex

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Index file not found: {path}")

        turbovec = TurboQuantIndex.load(str(p))
        index = cls(dim=turbovec.dim, bit_width=turbovec.bit_width)
        index._turbovec = turbovec
        return index

