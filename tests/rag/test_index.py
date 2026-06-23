"""Tests for RagIndex — embedding, building, persistence."""

from __future__ import annotations

from forgerwrite_mcp.rag.index import RagIndex
from forgerwrite_mcp.rag.preprocessor import ProcessedDoc
from forgerwrite_mcp.rag.retriever import RagDocument, RagRetriever

# ── Test documents ──────────────────────────────────────────────────────────

def _make_docs(n: int = 5) -> list[ProcessedDoc]:
    return [
        ProcessedDoc(
            doc_id=f"doc-{i}",
            title=f"Document {i}",
            content=f"Content of document {i}. This is unique text {i}.",
        )
        for i in range(n)
    ]


# ── Tests ───────────────────────────────────────────────────────────────────


class TestRagIndexBuild:
    """build() creates a searchable turbovec index from ProcessedDocs."""

    def test_build_returns_index(self):
        docs = _make_docs(5)
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)
        assert index is not None

    def test_build_creates_searchable_index(self):
        """After build, we can retrieve documents with RagRetriever."""
        docs = _make_docs(5)
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("Alibaba-NLP/gte-modernbert-base", device="cpu")

        rag_docs = [
            RagDocument(doc_id=d.doc_id, title=d.title, content=d.content, source=d.source)
            for d in docs
        ]
        retriever = RagRetriever(index=index, model=model, documents=rag_docs)
        results = retriever.retrieve("unique text 2", k=3)
        assert len(results) <= 3
        assert any(r.doc_id == "doc-2" for r in results)

    def test_build_minimum_documents(self):
        """Single doc should work."""
        docs = _make_docs(1)
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)
        assert index is not None

    def test_build_empty_docs(self):
        """Empty docs list should not crash."""
        index = RagIndex(dim=768, bit_width=4)
        index.build([])
        # Should not have created an internal index yet
        assert index is not None


class TestRagIndexPersistence:
    """save() and load() round-trip."""

    def test_save_and_load_roundtrip(self, tmp_path):
        docs = _make_docs(4)
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)

        idx_path = tmp_path / "test_index.tqi"
        index.save(str(idx_path))

        assert idx_path.exists()

        loaded = RagIndex.load(str(idx_path), documents=docs)
        assert loaded is not None

    def test_loaded_index_is_searchable(self, tmp_path):
        """After load, the index should still produce correct retrieval."""
        docs = _make_docs(4)
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)

        idx_path = tmp_path / "test_index.tqi"
        index.save(str(idx_path))

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("Alibaba-NLP/gte-modernbert-base", device="cpu")

        rag_docs = [
            RagDocument(doc_id=d.doc_id, title=d.title, content=d.content, source=d.source)
            for d in docs
        ]

        loaded = RagIndex.load(str(idx_path), documents=rag_docs)
        retriever = RagRetriever(index=loaded, model=model, documents=rag_docs)
        results = retriever.retrieve("content of document 3", k=1)
        assert len(results) == 1
        assert results[0].doc_id == "doc-3"


class TestRagIndexDefaults:
    def test_default_dim_is_768(self):
        index = RagIndex()
        assert index._dim == 768

    def test_default_bit_width_is_4(self):
        index = RagIndex()
        assert index._bit_width == 4


class TestRagIndexIntegration:
    """End-to-end: ProcessedDoc → RagIndex → RagRetriever → results."""

    def test_full_pipeline(self, tmp_path):
        """Preprocess curated KB → build index → retrieve."""
        from forgerwrite_mcp.rag.preprocessor import DocumentPreprocessor

        kb_text = """\
# Test KB

<!-- RAG-ID: rust-edition -->
### Edition rules
ALWAYS use edition = "2021". The gen keyword is reserved in 2024.

<!-- RAG-ID: fix-wrong-import -->
### Fix wrong crate name
Error: unresolved import calc_lib. Use exact name from Cargo.toml.
"""
        kb_path = tmp_path / "kb.md"
        kb_path.write_text(kb_text)

        # Step 1: Preprocess
        processor = DocumentPreprocessor(source="curated")
        processed = processor.process_file(str(kb_path))
        assert len(processed) == 2

        # Step 2: Build index
        index = RagIndex(dim=768, bit_width=4)
        index.build(processed)

        # Step 3: Retrieve
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("Alibaba-NLP/gte-modernbert-base", device="cpu")
        rag_docs = [
            RagDocument(doc_id=d.doc_id, title=d.title, content=d.content, source=d.source)
            for d in processed
        ]
        retriever = RagRetriever(index=index, model=model, documents=rag_docs)
        results = retriever.retrieve("import error calc_lib", k=2)
        assert results[0].doc_id == "fix-wrong-import"
