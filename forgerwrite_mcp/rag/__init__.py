"""RAG (Retrieval-Augmented Generation) module for ForgeWrite MCP.

Provides document preprocessing, embedding, indexing, retrieval, and prompt
enrichment for the local model pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from .enricher import RagPromptEnricher
from .index import RagIndex
from .preprocessor import DocumentPreprocessor, ProcessedDoc
from .retriever import RagDocument, RagRetriever

if TYPE_CHECKING:
    from ..config import ForgerWriteConfig

__all__ = [
    "DocumentPreprocessor",
    "ProcessedDoc",
    "RagDocument",
    "RagIndex",
    "RagPromptEnricher",
    "RagRetriever",
    "build_rag_enricher",
    "build_rag_index",
]


# ── Factory ─────────────────────────────────────────────────────────────────


def build_rag_enricher(
    config: ForgerWriteConfig,
    *,
    project_root: Path | None = None,
) -> RagPromptEnricher | None:
    """Build a :class:`RagPromptEnricher` from project config.

    Args:
        config: The project configuration.
        project_root: Absolute path to the project root. Defaults to cwd.

    Returns:
        The enricher, or ``None`` if RAG is disabled or the index is missing.
    """
    if not config.rag.enabled:
        return None

    from pathlib import Path as _Path

    root = _Path(project_root).resolve() if project_root else _Path.cwd()
    root = root.resolve()

    index_path = root / config.rag.index_path
    if not index_path.exists():
        return None

from .index import _get_embedding_model

    kb_path = root / "data" / "rag" / "rust-knowledge-base.md"
    if kb_path.exists():
        processor = DocumentPreprocessor(source="curated")
        processed = processor.process_file(str(kb_path))
    else:
        processed = []

    rag_docs = [
        RagDocument(
            doc_id=d.doc_id,
            title=d.title,
            content=d.content,
            source=d.source,
        )
        for d in processed
    ]

    index = RagIndex.load(str(index_path), documents=rag_docs)
    model = _get_embedding_model(config.rag.embedding_model_name)
    retriever = RagRetriever(index=index, model=model, documents=rag_docs)

    return RagPromptEnricher(
        retriever=retriever,
        max_rag_tokens=config.rag.max_rag_tokens,
    )


def build_rag_index(kb_dir: str = "data/rag", index_path: str = "data/rag/index.tqi") -> RagIndex:
    """Build (or rebuild) the RAG index from all knowledge base files.

    Processes the curated KB and any external markdown docs found in the
    kb directory, embeds them with gte-modernbert-base, and writes a
    TurboQuantIndex to disk.

    Args:
        kb_dir: Directory containing knowledge base markdown files.
        index_path: Where to write the index file.

    Returns:
        The built :class:`RagIndex` (also saved to *index_path*).
    """
    from pathlib import Path

    kb = Path(kb_dir)

    all_docs: list[ProcessedDoc] = []

    # Curated KB: Rust
    curated = kb / "rust-knowledge-base.md"
    if curated.exists():
        print(f"Processing {curated.name}...")
        processor = DocumentPreprocessor(source="curated")
        all_docs.extend(processor.process_file(str(curated)))

    # Curated KB: Python
    py_curated = kb / "python-knowledge-base.md"
    if py_curated.exists():
        print(f"Processing {py_curated.name}...")
        processor = DocumentPreprocessor(source="curated")
        all_docs.extend(processor.process_file(str(py_curated)))

    # External: rust-cookbook
    cookbook_dir = kb / "rust-cookbook" / "src"
    if cookbook_dir.is_dir():
        md_files = sorted(cookbook_dir.rglob("*.md"))
        print(f"Processing rust-cookbook ({len(md_files)} files)...")
        processor = DocumentPreprocessor(source="rust-cookbook")
        for md_file in md_files:
            all_docs.extend(processor.process_file(str(md_file)))

    # External: rust-by-example
    rbe_dir = kb / "rust-by-example" / "src"
    if rbe_dir.is_dir():
        md_files = sorted(rbe_dir.rglob("*.md"))
        print(f"Processing rust-by-example ({len(md_files)} files)...")
        processor = DocumentPreprocessor(source="rust-by-example")
        for md_file in md_files:
            all_docs.extend(processor.process_file(str(md_file)))

    # External: pydantic v2 docs (markdown)
    pydantic_dir = kb / "pydantic-docs" / "docs"
    if pydantic_dir.is_dir():
        md_files = sorted(pydantic_dir.rglob("*.md"))
        print(f"Processing pydantic-docs ({len(md_files)} files)...")
        processor = DocumentPreprocessor(source="pydantic")
        for md_file in md_files:
            all_docs.extend(processor.process_file(str(md_file)))

    # External: httpx docs (markdown)
    httpx_dir = kb / "httpx-docs" / "docs"
    if httpx_dir.is_dir():
        md_files = sorted(httpx_dir.rglob("*.md"))
        print(f"Processing httpx-docs ({len(md_files)} files)...")
        processor = DocumentPreprocessor(source="httpx")
        for md_file in md_files:
            all_docs.extend(processor.process_file(str(md_file)))

    # Filter out empty docs (thin wrappers with only {{#include}} directives)
    all_docs = [d for d in all_docs if d.content.strip()]
    print(f"Total documents after filtering: {len(all_docs)}")

    index = RagIndex(dim=768, bit_width=4)
    index.build(all_docs)

    out = Path(index_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving index to {index_path}...")
    if all_docs:
        index.save(str(out))

    return index
