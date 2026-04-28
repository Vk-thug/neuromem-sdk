"""
v0.4.0 knowledge-base ingest pipeline.

Two parser tiers ship in the box:

* :class:`MarkdownParser` — zero-dep heading-aware Markdown / text.
  Always available.
* :class:`DoclingParser` — universal PDF / DOCX / XLSX / PPTX / HTML /
  image parser via IBM Research's Docling. Requires the optional
  ``[ingest]`` extra.

Both register on import via :mod:`registry`. Third parties can
``register_parser("custom", factory)`` to plug in their own format.

Cognitive grounding for the ingest design:

* Every chunk carries ``source_id`` so the ``SchemaIntegrator``
  (Tse et al. 2007) can recognise document boundaries and accelerate
  consolidation of within-document facts vs. cross-document.
* Document hierarchy maps to graph hierarchy: a document root node
  links via ``derived_from`` to each chunk; sibling chunks within the
  same section link via ``related``. Mirrors how the hippocampus
  indexes neocortical content (Teyler & DiScenna 1986).
"""

from neuromem.core.ingest.ingester import KnowledgeBaseIngester, UnsupportedFileType
from neuromem.core.ingest.markdown_parser import MarkdownParser
from neuromem.core.ingest.registry import (
    compute_source_id,
    parser_for_name,
    parser_for_path,
    register_parser,
    supported_suffixes,
)
from neuromem.core.ingest.types import FileParser, Modality, ParsedChunk

# Built-in registrations. Markdown first (zero-dep, always works);
# Docling registered with explicit ``suffixes`` so the suffix index is
# populated even before the optional ``docling`` package is installed.
register_parser("markdown", MarkdownParser)

_DOCLING_SUFFIXES = (
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
)


def _docling_factory():
    from neuromem.core.ingest.docling_parser import DoclingParser

    return DoclingParser()


register_parser("docling", _docling_factory, suffixes=_DOCLING_SUFFIXES)

__all__ = [
    "FileParser",
    "KnowledgeBaseIngester",
    "MarkdownParser",
    "Modality",
    "ParsedChunk",
    "UnsupportedFileType",
    "compute_source_id",
    "parser_for_name",
    "parser_for_path",
    "register_parser",
    "supported_suffixes",
]
