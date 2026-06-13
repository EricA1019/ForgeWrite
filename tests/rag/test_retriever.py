"""Tests for RAG retriever — retrieval quality (C1)."""

import numpy as np
import pytest
from turbovec import TurboQuantIndex


def _make_test_index(documents: list[object]) -> tuple[TurboQuantIndex, object, list[object]]:
    """Build a small test index from documents. Returns (index, model, docs)."""
    from sentence_transformers import SentenceTransformer

    from forgerwrite_mcp.rag.retriever import RagDocument

    model = SentenceTransformer("Alibaba-NLP/gte-modernbert-base", device="cpu")
    docs = [
        RagDocument(doc_id=d["id"], title=d["title"], content=d["content"], source=d.get("source", "curated"))
        for d in documents
    ]
    vectors = np.array([model.encode(d.embeddable_text) for d in docs]).astype(np.float32)
    idx = TurboQuantIndex(dim=vectors.shape[1], bit_width=4)
    idx.add(vectors)
    return idx, model, docs


# ── Test documents (mini knowledge base) ──────────────────────────────────

_TEST_DOCUMENTS = [
    {
        "id": "op-template-create_file",
        "title": "create_file — exact JSON template",
        "content": '{"op": "create_file", "path": "src/lib.rs", "content": "pub fn add(a: i32, b: i32) -> i32 { a + b }\\n"}',
        "source": "curated",
    },
    {
        "id": "op-template-replace_file",
        "title": "replace_file — exact JSON template",
        "content": '{"op": "replace_file", "path": "src/main.rs", "content": "fn main() {\\n    println!(\\"hello\\");\\n}\\n"}',
        "source": "curated",
    },
    {
        "id": "rust-import-rules",
        "title": "Import and module rules",
        "content": "use uses the CRATE NAME from Cargo.toml package name, NOT a made-up name. If Cargo.toml says name = \"calc\", use use calc::add; — never use calc_lib::add.",
        "source": "curated",
    },
    {
        "id": "rust-edition-rules",
        "title": "Edition rules (CRITICAL)",
        "content": "ALWAYS use edition = \"2021\" in generated Cargo.toml. Edition 2024 reserves the gen keyword, which breaks rand::Rng::gen().",
        "source": "curated",
    },
    {
        "id": "crate-pattern-clap-v4",
        "title": "clap v4 — CLI with subcommands (enum pattern)",
        "content": 'use clap::Parser; #[derive(Parser)] enum Cli { Add { a: i32, b: i32 }, Sub { a: i32, b: i32 } }',
        "source": "curated",
    },
    {
        "id": "crate-pattern-rand",
        "title": "rand v0.8 — random number generation",
        "content": "use rand::Rng; fn main() { let mut rng = rand::thread_rng(); let n: u32 = rng.gen(); println!(\"{}\", n); }",
        "source": "curated",
    },
    {
        "id": "fix-wrong-crate-name",
        "title": "Fix: unresolved import (wrong crate name)",
        "content": "Error: unresolved import calc_lib. Fix: Change to exact crate name from Cargo.toml. If name = \"calc\", use use calc::*;. Never append _lib.",
        "source": "curated",
    },
    {
        "id": "fix-test-assertion",
        "title": "Fix: test assertion failure",
        "content": "Error: assertion left == right failed: left: 7, right: 6. Fix: Change assertion to correct expected value. Before: assert_eq!(double(3), 7); After: assert_eq!(double(3), 6);",
        "source": "curated",
    },
    {
        "id": "scaffold-cargo-toml",
        "title": "Cargo.toml — standard template",
        "content": '[package] name = "crate" version = "0.1.0" edition = "2021" [dependencies]',
        "source": "curated",
    },
    {
        "id": "scaffold-full-project",
        "title": "Full project scaffold — 5 files",
        "content": "Cargo.toml (edition 2021), src/main.rs (fn main), src/lib.rs (pub mod ops; pub use ops::*), src/ops.rs (functions), tests/integration_test.rs (use crate::func)",
        "source": "curated",
    },
]

# ── Query → expected doc mapping ──────────────────────────────────────────

# Each query should retrieve the listed doc IDs in the top-k (recall-oriented)
_RETRIEVAL_TESTS = [
    # Task: create a new file
    ("Create a new Rust source file with a function", ["op-template-create_file"]),
    # Task: modify existing file
    ("Rewrite the entire main.rs to add a helper function", ["op-template-replace_file"]),
    # Task: import something
    ("Use the calc crate in main.rs to call the add function", ["rust-import-rules"]),
    # Task: Cargo.toml generation
    ("Generate a Cargo.toml for a new Rust project with rand dependency", ["scaffold-cargo-toml", "rust-edition-rules"]),
    # Task: CLI app
    ("Build a CLI calculator with add and sub commands using clap", ["crate-pattern-clap-v4", "scaffold-full-project"]),
    # Task: random numbers
    ("Create a program that generates random numbers", ["crate-pattern-rand"]),
    # Fix: wrong import name
    ("Fix unresolved import calc_lib error in Rust code", ["fix-wrong-crate-name", "rust-import-rules"]),
    # Fix: test failure
    ("Fix a failing test: assertion double(3) == 7 but expected 6", ["fix-test-assertion"]),
]


class TestRetrievalQuality:
    """C1: Retrieval quality tests — TDD for RagRetriever."""

    @pytest.fixture(scope="class")
    def retriever(self) -> object:
        """Build a RagRetriever with the test document set."""
        from forgerwrite_mcp.rag.retriever import RagRetriever

        idx, model, docs = _make_test_index(_TEST_DOCUMENTS)
        return RagRetriever(index=idx, model=model, documents=docs)

    @pytest.mark.parametrize("query,expected_ids", _RETRIEVAL_TESTS)
    def test_retrieval_recall_at_3(self, retriever: object, query: str, expected_ids: list[str]) -> None:
        """Each query must retrieve at least one expected doc in top-3."""
        results = retriever.retrieve(query, k=3)
        retrieved_ids = {r.doc_id for r in results}
        overlap = retrieved_ids & set(expected_ids)
        assert overlap, (
            f"Query '{query[:60]}...' failed recall: "
            f"expected any of {expected_ids}, got {retrieved_ids}"
        )

    def test_retrieval_recall_at_1_threshold(self, retriever: object) -> None:
        """At least 5 of 8 queries must have the top-1 doc in expected set."""
        hits = 0
        for query, expected_ids in _RETRIEVAL_TESTS:
            results = retriever.retrieve(query, k=1)
            if results and results[0].doc_id in expected_ids:
                hits += 1
        recall_at_1 = hits / len(_RETRIEVAL_TESTS)
        assert recall_at_1 >= 0.5, f"Recall@1 too low: {recall_at_1:.2f} < 0.5"

    def test_relevance_ordering(self, retriever: object) -> None:
        """For 'create a new file', create_file should rank above delete_file."""
        results = retriever.retrieve("create a new Rust source file", k=5)
        # The top result should be create_file, not a random doc
        top_titles = [r.title for r in results[:3]]
        assert any("create_file" in t for t in top_titles), f"create_file not in top 3: {top_titles}"

    def test_repair_query_retrieves_fix_pattern(self, retriever: object) -> None:
        """Repair queries should retrieve fix patterns."""
        results = retriever.retrieve(
            "error: unresolved import 'calc_lib' use of unresolved module",
            k=3,
        )
        retrieved_ids = {r.doc_id for r in results}
        assert "fix-wrong-crate-name" in retrieved_ids, f"fix pattern not retrieved: {retrieved_ids}"

    def test_k_limits_results(self, retriever: object) -> None:
        """retrieve(k=N) returns at most N documents."""
        for k in (1, 3, 5):
            results = retriever.retrieve("Rust project creation", k=k)
            assert len(results) <= k, f"k={k} returned {len(results)} results"
