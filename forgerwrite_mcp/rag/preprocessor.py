"""Document preprocessor — splits raw markdown into RAG-ready documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ── Patterns ────────────────────────────────────────────────────────────────

_RAG_ID_RE: re.Pattern[str] = re.compile(r"<!--\s*RAG-ID:\s*(\S+)\s*-->")
_HTML_COMMENT_RE: re.Pattern[str] = re.compile(r"<!--.*?-->", re.DOTALL)
_INCLUDE_RE: re.Pattern[str] = re.compile(r"\{\{#include\s+\S+\}\}")
# Match any markdown header: #, ##, ###, etc.
_HEADER_RE: re.Pattern[str] = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


# ── Dataclass ───────────────────────────────────────────────────────────────


@dataclass
class ProcessedDoc:
    """A preprocessed document ready for embedding."""

    doc_id: str
    title: str
    content: str
    source: str = "curated"


# ── Public API ──────────────────────────────────────────────────────────────


class DocumentPreprocessor:
    """Preprocesses markdown knowledge base files into ProcessedDocs.

    Supports two formats:
      - Curated KB: splits on ``###`` boundaries with ``<!-- RAG-ID: ... -->`` markers.
      - External docs: splits on ``#`` / ``##`` boundaries, auto-generates slugs.
    """

    def __init__(self, *, source: str = "curated") -> None:
        self._source = source

    # ── Entry points ────────────────────────────────────────────────────────

    def process_file(self, path: str) -> list[ProcessedDoc]:
        """Split a markdown file into individual ProcessedDocs."""
        text = Path(path).read_text(encoding="utf-8")
        return self.process_text(text)

    def process_text(self, text: str) -> list[ProcessedDoc]:
        """Split markdown text into ProcessedDocs."""
        if self._source == "curated":
            return list(self._split_curated(text))
        return list(self._split_external(text))

    # ── Curated (### + RAG-ID) ──────────────────────────────────────────────

    def _split_curated(self, text: str) -> list[ProcessedDoc]:
        """Split on ``###`` boundaries, extracting RAG-ID as doc_id.

        RAG-ID anchors sit *before* the ``###`` header, so we need to
        look backwards for each match.
        """
        # Build matches for ### headers
        pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(text))
        if not matches:
            return []

        docs: list[ProcessedDoc] = []
        for i, m in enumerate(matches):
            # Body: from end of ### line to start of next ### (or EOF)
            body_start = m.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            # RAG-ID: look backwards from this ### to previous ### (or start of text)
            search_start = matches[i - 1].end() if i > 0 else 0
            preceding = text[search_start : m.start()]
            rag_id = self._extract_rag_id(preceding)

            if not rag_id:
                continue

            title = _clean_title(m.group(1))
            content = self._clean_content(text[body_start:body_end])
            docs.append(
                ProcessedDoc(
                    doc_id=rag_id, title=title, content=content, source=self._source
                )
            )

        return docs

    def _extract_rag_id(self, text: str) -> str | None:
        """Extract ``<!-- RAG-ID: foo -->`` from text. Returns None if absent."""
        m = _RAG_ID_RE.search(text)
        return m.group(1) if m else None

    # ── External (# / ## boundaries) ────────────────────────────────────────

    def _split_external(self, text: str) -> list[ProcessedDoc]:
        """Split on ``#`` and ``##`` boundaries, auto-generating slugs."""
        sections = self._chunk_by_header(text, header_level=None)
        docs: list[ProcessedDoc] = []

        for header_line, body in sections:
            title = _clean_title(header_line)
            doc_id = _slugify(title)
            content = self._clean_content(body)
            docs.append(
                ProcessedDoc(
                    doc_id=doc_id, title=title, content=content, source=self._source
                )
            )

        return docs

    # ── Content cleaning ────────────────────────────────────────────────────

    @staticmethod
    def _clean_content(text: str) -> str:
        """Remove HTML comments and include directives, then strip whitespace."""
        text = _HTML_COMMENT_RE.sub("", text)
        text = _INCLUDE_RE.sub("", text)
        # Collapse 3+ blank lines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ── Generic header chunker ──────────────────────────────────────────────

    @staticmethod
    def _chunk_by_header(
        text: str, *, header_level: int | None
    ) -> list[tuple[str, str]]:
        """Split text into (header_line, body) tuples.

        Args:
            text: Raw markdown.
            header_level: ``3`` for ``###`` only, ``None`` for any ``#`` / ``##``.
        """
        # Build the pattern
        if header_level is not None:
            prefix = "#" * header_level
            pattern = re.compile(rf"^{prefix}\s+(.+)$", re.MULTILINE)
        else:
            pattern = re.compile(r"^#{1,2}\s+(.+)$", re.MULTILINE)

        matches = list(pattern.finditer(text))
        if not matches:
            return []

        chunks: list[tuple[str, str]] = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end]
            chunks.append((m.group(1), body))

        return chunks


# ── Helpers ─────────────────────────────────────────────────────────────────


def _clean_title(raw: str) -> str:
    """Remove leading/trailing ``#`` and whitespace from a header line."""
    return re.sub(r"^#+\s*", "", raw).strip()


def _slugify(title: str) -> str:
    """Convert a title to a lowercase underscore-separated slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    slug = re.sub(r"\s+", "_", slug)
    return slug.strip("_")
