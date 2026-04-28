"""
Shared types for the v0.4.0 knowledge-base ingest pipeline.

A ``ParsedChunk`` is the atomic unit a parser yields. It carries enough
provenance for the ``KnowledgeBaseIngester`` to (a) store the chunk
verbatim, (b) optionally observe it as an episodic memory, and (c) wire
graph relationships back to the source document and sibling chunks.

Design principle (Tse et al. 2007 schema theory): every chunk from the
same source shares ``source_id`` so the ``SchemaIntegrator`` can detect
document boundaries and consolidate document-internal facts faster than
cross-document ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional, Protocol, Tuple

# Modality tags. ``text`` covers paragraphs / headings; ``table`` covers
# Docling-extracted tabular blocks (preserved as Markdown tables);
# ``image`` covers OCR'd or alt-text-described images; ``code`` covers
# fenced code blocks.
Modality = str  # "text" | "table" | "image" | "code"


@dataclass
class ParsedChunk:
    """A single chunk of content extracted from a source document."""

    content: str
    """The chunk text. Tables are serialised as Markdown; code blocks
    keep fences; images get OCR'd text or the alt-text fallback."""

    source_id: str
    """Stable id for the source document (sha1 of the original file
    path + mtime). All chunks from one upload share this id, which the
    graph uses to attach a single 'document root' node and the schema
    integrator uses to recognise document boundaries."""

    source_path: str
    """Original filesystem path (or upload filename for in-memory uploads)."""

    section_path: Tuple[str, ...] = field(default_factory=tuple)
    """Heading hierarchy that scopes this chunk, e.g.
    ('Q3 Report', 'Revenue', 'By Region'). Empty for documents without
    headings."""

    page_no: Optional[int] = None
    """1-indexed page number for paginated formats (PDF, PPTX). None
    otherwise."""

    chunk_index: int = 0
    """Sequential index within the source document, starting at 0."""

    modality: Modality = "text"

    raw_metadata: dict = field(default_factory=dict)
    """Anything extra a parser wants to surface (Docling table cells,
    figure captions, slide layout name, ...). Stored on the resulting
    MemoryItem.metadata so retrieval/explain can inspect it."""


class FileParser(Protocol):
    """A parser knows how to extract ``ParsedChunk`` records from a
    file path it claims via ``suffixes``.

    Parsers MUST yield lazily — large PDFs/spreadsheets must not
    materialise every chunk in memory before the first chunk reaches
    the ingester. The ``KnowledgeBaseIngester`` drives the iterator
    chunk-by-chunk so embedding+write can stream.
    """

    suffixes: Tuple[str, ...]
    """Lowercase file extensions this parser handles, including the
    leading dot. Example: ``(".pdf", ".docx")``."""

    name: str
    """Stable identifier for telemetry / error messages."""

    def parse(self, path: str, *, source_id: str) -> Iterator[ParsedChunk]:
        ...


__all__ = ["FileParser", "Modality", "ParsedChunk"]
