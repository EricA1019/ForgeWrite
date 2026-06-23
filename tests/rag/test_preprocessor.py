"""Tests for DocumentPreprocessor — splitting markdown into RAG-ready docs."""

from __future__ import annotations

import textwrap

import pytest

from forgerwrite_mcp.rag.preprocessor import DocumentPreprocessor, ProcessedDoc

# ── Helpers ─────────────────────────────────────────────────────────────────

def _dedent(text: str) -> str:
    return textwrap.dedent(text).strip()


# ── Fixture: curated KB snippet ─────────────────────────────────────────────

@pytest.fixture
def curated_kb_content() -> str:
    return _dedent("""
        # ForgeWrite Rust Knowledge Base

        > Intro text.

        ## 1. Operation Templates

        <!-- RAG-ID: op-template-create_file -->
        ### create_file — exact JSON template
        ```json
        {"op": "create_file", "path": "x.rs", "content": "fn main() {}\\n"}
        ```
        Rules: path must be in allowed_files.

        <!-- RAG-ID: op-template-replace_file -->
        ### replace_file — exact JSON template
        ```json
        {"op": "replace_file", "path": "x.rs", "content": "fn main() {}\\n"}
        ```
        Rules: Replaces the ENTIRE file content.

        ## 2. Rust Rules

        <!-- RAG-ID: rust-edition-rules -->
        ### Edition rules (CRITICAL)
        ALWAYS use edition = "2021". The `gen` keyword is reserved in 2024.
    """)


@pytest.fixture
def external_doc_content() -> str:
    return _dedent("""
        # Hello World

        This is the classic "Hello, World!" program.

        ```rust
        fn main() {
            println!("Hello, world!");
        }
        ```

        ## Formatted Print

        Printing is handled by macros like `println!`.

        ```rust
        println!("{} days", 31);
        ```

        ## Comments

        Rust supports line comments and doc comments.
    """)


# ── Tests ───────────────────────────────────────────────────────────────────

class TestDocumentPreprocessorCurated:
    """Tests for curated KB format: ### sections with <!-- RAG-ID --> markers."""

    def test_splits_on_h3_boundaries(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        processor = DocumentPreprocessor()
        docs = processor.process_file(str(p))

        assert len(docs) == 3

    def test_extracts_rag_id_as_doc_id(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        docs = DocumentPreprocessor().process_file(str(p))

        doc_ids = [d.doc_id for d in docs]
        assert "op-template-create_file" in doc_ids
        assert "op-template-replace_file" in doc_ids
        assert "rust-edition-rules" in doc_ids

    def test_extracts_h3_text_as_title(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        docs = DocumentPreprocessor().process_file(str(p))

        titles = [d.title for d in docs]
        assert "create_file — exact JSON template" in titles
        assert "replace_file — exact JSON template" in titles
        assert "Edition rules (CRITICAL)" in titles

    def test_content_is_everything_after_title(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        docs = DocumentPreprocessor().process_file(str(p))

        # First doc should have JSON code + "Rules:" text but NOT the next h3
        first = docs[0]
        assert "```json" in first.content
        assert "path must be in allowed_files" in first.content
        assert "replace_file" not in first.content  # next section

    def test_last_doc_includes_trailing_content(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        docs = DocumentPreprocessor().process_file(str(p))

        last = docs[2]
        assert 'edition = "2021"' in last.content
        assert "gen" in last.content

    def test_strips_html_comments_from_content(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        docs = DocumentPreprocessor().process_file(str(p))

        for d in docs:
            assert "<!--" not in d.content
            assert "-->" not in d.content
            assert "RAG-ID" not in d.content

    def test_source_is_curated(self, curated_kb_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(curated_kb_content)

        docs = DocumentPreprocessor().process_file(str(p))

        for d in docs:
            assert d.source == "curated"


class TestDocumentPreprocessorExternal:
    """Tests for external doc format: # and ## sections, no RAG-ID markers."""

    def test_splits_on_h1_and_h2_boundaries(self, external_doc_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(external_doc_content)

        processor = DocumentPreprocessor(source="rust-by-example")
        docs = processor.process_file(str(p))

        assert len(docs) >= 3  # Hello World, Formatted Print, Comments

    def test_doc_id_is_slug_from_title(self, external_doc_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(external_doc_content)

        docs = DocumentPreprocessor(source="rust-by-example").process_file(str(p))

        doc_ids = [d.doc_id for d in docs]
        assert "hello_world" in doc_ids
        assert "formatted_print" in doc_ids
        assert "comments" in doc_ids

    def test_title_is_header_text(self, external_doc_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(external_doc_content)

        docs = DocumentPreprocessor(source="rust-by-example").process_file(str(p))

        titles = [d.title for d in docs]
        assert "Hello World" in titles
        assert "Formatted Print" in titles
        assert "Comments" in titles

    def test_content_includes_code_blocks(self, external_doc_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(external_doc_content)

        docs = DocumentPreprocessor(source="rust-by-example").process_file(str(p))

        # Hello World section should have the println code
        hello = docs[0]
        assert 'println!("Hello, world!")' in hello.content

    def test_source_is_passed_through(self, external_doc_content: str, tmp_path):
        p = tmp_path / "test.md"
        p.write_text(external_doc_content)

        docs = DocumentPreprocessor(source="rust-cookbook").process_file(str(p))

        for d in docs:
            assert d.source == "rust-cookbook"

    def test_strips_include_directives(self, tmp_path):
        """Rust Cookbook uses {{#include ...}} directives — strip them."""
        content = _dedent("""
            # Parse command line arguments

            {{#include arguments/basic.md}}
            {{#include arguments/clap-basic.md}}

            {{#include ../links.md}}
        """)
        p = tmp_path / "test.md"
        p.write_text(content)

        docs = DocumentPreprocessor(source="rust-cookbook").process_file(str(p))

        assert len(docs) == 1
        assert "{{#include" not in docs[0].content


class TestProcessedDoc:
    """Unit tests for the ProcessedDoc dataclass."""

    def test_all_fields(self):
        doc = ProcessedDoc(
            doc_id="test-1",
            title="Test Doc",
            content="Some content",
            source="curated",
        )
        assert doc.doc_id == "test-1"
        assert doc.title == "Test Doc"
        assert doc.content == "Some content"
        assert doc.source == "curated"

    def test_default_source(self):
        doc = ProcessedDoc(doc_id="t", title="T", content="c")
        assert doc.source == "curated"
