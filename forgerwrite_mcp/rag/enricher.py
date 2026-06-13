"""RAG prompt enricher — injects retrieved documents into model prompts."""

from __future__ import annotations

# ── Constants ──────────────────────────────────────────────────────────────

_RAG_HEADER: str = "--- RELEVANT KNOWLEDGE ---"
_TASK_HEADER: str = "--- TASK ---"
_DEFAULT_MAX_TOKENS: int = 2048
# Rough heuristic: 1 token ≈ 4 characters for English text
_CHARS_PER_TOKEN: int = 4


class RagPromptEnricher:
    """Wraps a retriever to enrich prompts with relevant knowledge.

    Injects retrieved documents into the prompt with a ``RELEVANT KNOWLEDGE``
    prefix, followed by the original task under a ``TASK`` header::

        --- RELEVANT KNOWLEDGE ---
        [doc 1 title]
        [doc 1 content]

        ---
        [doc 2 title]
        [doc 2 content]

        --- TASK ---
        [original prompt]
    """

    def __init__(self, *, retriever: object, max_rag_tokens: int = _DEFAULT_MAX_TOKENS) -> None:
        self._retriever = retriever
        self._max_rag_tokens = max_rag_tokens

    # ── Public API ─────────────────────────────────────────────────────────

    def enrich(self, base_prompt: str, query: str, k: int = 5) -> str:
        """Retrieve relevant docs and inject them into the prompt.

        Args:
            base_prompt: The original user task / instruction.
            query: A search query for retrieval (can differ from base_prompt).
            k: Number of documents to retrieve.

        Returns:
            The enriched prompt with knowledge prepended.
        """
        docs = self._retriever.retrieve(query, k=k)
        if not docs:
            return f"{_TASK_HEADER}\n{base_prompt}"

        knowledge = self._format_docs(docs)
        return f"{_RAG_HEADER}\n{knowledge}\n{_TASK_HEADER}\n{base_prompt}"

    # ── Internal ───────────────────────────────────────────────────────────

    def _format_docs(self, docs: list[object]) -> str:
        """Format retrieved documents into a string, respecting token budget."""
        max_chars = self._max_rag_tokens * _CHARS_PER_TOKEN
        parts: list[str] = []
        used = 0

        for i, doc in enumerate(docs):
            block = f"{doc.title}\n{doc.content}"
            block_len = len(block)

            if i > 0:
                separator = "\n\n---\n"
                if used + len(separator) + block_len > max_chars:
                    break
                parts.append(separator)
                used += len(separator)

            if used + block_len > max_chars:
                # Truncate this doc to fit
                available = max_chars - used
                if available < 20:  # Not enough room for meaningful content
                    break
                block = block[:available] + "..."
                parts.append(block)
                break

            parts.append(block)
            used += block_len

        return "".join(parts)
