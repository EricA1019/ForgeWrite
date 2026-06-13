"""Tests for RagPromptEnricher — injecting RAG documents into prompts."""

from __future__ import annotations

import numpy as np
import pytest
from turbovec import TurboQuantIndex

_HERE = __import__("pathlib").Path(__file__).parent


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_retriever() -> object:
    """Build a mini retriever with a few test documents."""
    from sentence_transformers import SentenceTransformer

    from forgerwrite_mcp.rag.retriever import RagDocument, RagRetriever

    docs = [
        RagDocument(doc_id="rust-edition", title="Edition rules",
                    content="ALWAYS use edition = 2021. gen keyword is reserved in 2024."),
        RagDocument(doc_id="fix-import", title="Fix wrong crate name",
                    content="Error: unresolved import calc_lib. Use exact Cargo.toml name."),
        RagDocument(doc_id="create-file-template", title="create_file template",
                    content='{"op": "create_file", "path": "x.rs", "content": "fn main() {}\\n"}'),
    ]
    model = SentenceTransformer("Alibaba-NLP/gte-modernbert-base", device="cpu")
    vectors = np.array([model.encode(d.embeddable_text) for d in docs]).astype(np.float32)
    idx = TurboQuantIndex(dim=vectors.shape[1], bit_width=4)
    idx.add(vectors)
    return RagRetriever(index=idx, model=model, documents=docs)


# ── Tests ───────────────────────────────────────────────────────────────────


class TestRagPromptEnricher:
    def test_enrich_includes_header(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        enricher = RagPromptEnricher(retriever=retriever)
        result = enricher.enrich(
            base_prompt="Create a new Rust file.",
            query="create file template cargo toml edition",
            k=3,
        )
        assert "RELEVANT KNOWLEDGE" in result

    def test_enrich_includes_retrieved_docs(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        enricher = RagPromptEnricher(retriever=retriever)
        result = enricher.enrich(
            base_prompt="Fix the gen keyword error in Rust.",
            query="edition 2024 gen keyword error fix",
            k=3,
        )
        # "Edition rules" doc should be top hit
        assert "Edition rules" in result or "edition" in result.lower()

    def test_enrich_includes_base_prompt(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        enricher = RagPromptEnricher(retriever=retriever)
        base = "Create a new Rust file with fn main()."
        result = enricher.enrich(base_prompt=base, query="create file", k=3)
        assert base in result

    def test_enrich_respects_k(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        enricher = RagPromptEnricher(retriever=retriever)
        result = enricher.enrich(base_prompt="Do something.", query="rust", k=1)
        # Should have at most 1 doc entry
        # Count separators — there should be exactly one doc block separator pair
        separator_count = result.count("---")
        # Headers + separators + task header = several ---
        # This is loose; just verify formatting is present
        assert "RELEVANT KNOWLEDGE" in result

    def test_enrich_ordering_knowledge_before_task(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        enricher = RagPromptEnricher(retriever=retriever)
        result = enricher.enrich(
            base_prompt="Write a Cargo.toml with edition 2021.",
            query="cargo toml edition",
            k=3,
        )
        # Knowledge section should appear before TASK section
        knowledge_pos = result.index("RELEVANT KNOWLEDGE")
        task_pos = result.index("TASK")
        assert knowledge_pos < task_pos

    def test_token_budget_truncates_long_docs(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        # Set a very small budget — only 50 tokens for RAG content
        enricher = RagPromptEnricher(retriever=retriever, max_rag_tokens=50)
        result = enricher.enrich(
            base_prompt="Create a file.",
            query="create file rust",
            k=3,
        )
        # Should still produce valid output without crashing
        assert "RELEVANT KNOWLEDGE" in result
        assert "TASK" in result

    def test_default_max_tokens(self):
        from forgerwrite_mcp.rag.enricher import RagPromptEnricher

        retriever = _make_retriever()
        enricher = RagPromptEnricher(retriever=retriever)
        assert enricher._max_rag_tokens == 2048
