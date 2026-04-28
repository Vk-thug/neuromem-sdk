"""
Docling-backed parser for PDF / DOCX / XLSX / PPTX / HTML / images.

Docling (https://github.com/DS4SD/docling) is IBM Research's
open-source document processor. It produces a unified
``DoclingDocument`` IR that preserves layout (headings, tables,
figures, captions) and supports OCR for scanned PDFs and images.

We walk the IR and yield ``ParsedChunk`` records:

* ``TextItem`` / ``SectionHeaderItem`` → ``modality="text"`` chunks
  with the heading hierarchy on ``section_path``.
* ``TableItem`` → ``modality="table"`` chunks rendered as Markdown
  tables (preserves column / row structure for retrieval).
* ``PictureItem`` → ``modality="image"`` chunks. Uses the OCR result
  if Docling produced one; falls back to the figure caption.

Lazy iteration: Docling materialises the full document on parse, but
we yield chunks one at a time so the ingester's embed+write loop
streams.

Heavy dep — Docling pulls EasyOCR + a layout model (~500MB). Gated
behind ``[ingest]`` extra; the registry imports this lazily so the
rest of the SDK doesn't pay the cost.
"""

from __future__ import annotations

from typing import Iterator, List, Optional, Tuple

from neuromem.core.ingest.types import ParsedChunk
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


class DoclingNotInstalled(RuntimeError):
    """Raised when DoclingParser is constructed without the optional
    ``docling`` package available. The error message names the install
    command — same UX the cloudflared tunnel helper uses."""


class DoclingParser:
    """Universal document parser backed by Docling."""

    # Docling supports many more, but these are the ones we ship as
    # first-class in v0.4.0. ``.md`` is intentionally NOT here —
    # MarkdownParser handles it without the heavy Docling dep.
    suffixes = (
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
    name = "docling"

    def __init__(self, *, do_ocr: bool = True) -> None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise DoclingNotInstalled(
                "Docling is not installed. Install with:\n"
                "  pip install 'neuromem-sdk[ingest]'\n"
                "or directly:\n"
                "  pip install docling"
            ) from exc

        self._converter_cls = DocumentConverter
        self._do_ocr = do_ocr
        self._converter = None  # lazy-init on first parse — heavy

    # ----- public API ----------------------------------------------------

    def parse(self, path: str, *, source_id: str) -> Iterator[ParsedChunk]:
        """Yield ``ParsedChunk`` records for ``path``.

        Walks the DoclingDocument's iterator API and emits one chunk
        per text/table/image element with full provenance.
        """
        doc = self._convert(path)
        chunk_index = 0
        section_stack: List[Tuple[int, str]] = []

        # The ``iterate_items`` generator walks document order. Each
        # element exposes ``label`` (heading / paragraph / table /
        # picture) and ``self_ref`` (an in-document path). Page number
        # is on ``prov[*].page_no`` for paginated formats.
        for element, _level in self._iterate_items(doc):
            chunk = self._element_to_chunk(
                element=element,
                source_id=source_id,
                source_path=path,
                section_stack=section_stack,
                chunk_index=chunk_index,
            )
            if chunk is None:
                continue
            yield chunk
            chunk_index += 1

    # ----- internals -----------------------------------------------------

    def _convert(self, path: str):
        if self._converter is None:
            self._converter = self._converter_cls()
        result = self._converter.convert(path)
        return result.document

    @staticmethod
    def _iterate_items(doc):
        """Defensive wrapper around Docling's iterator API. The exact
        method name shifted across docling 1.x — try the documented
        ``iterate_items`` first, fall back to ``texts`` + ``tables`` +
        ``pictures`` accessors."""
        if hasattr(doc, "iterate_items"):
            yield from doc.iterate_items()
            return
        # Fallback: enumerate by category. Loses document order but
        # preserves coverage on older docling builds.
        for attr in ("texts", "tables", "pictures"):
            for item in getattr(doc, attr, []) or []:
                yield item, 0

    def _element_to_chunk(
        self,
        *,
        element,
        source_id: str,
        source_path: str,
        section_stack: List[Tuple[int, str]],
        chunk_index: int,
    ) -> Optional[ParsedChunk]:
        """Map a single Docling element to a ``ParsedChunk``.

        Heading elements update the section stack and emit no chunk of
        their own — their text becomes the ``section_path`` of the
        chunks that follow.
        """
        label = getattr(element, "label", "") or ""
        page_no = self._page_no(element)

        # Headings: update stack, no chunk emitted.
        if label in ("section_header", "title", "heading"):
            level = self._heading_level(element)
            text = (getattr(element, "text", "") or "").strip()
            if text:
                while section_stack and section_stack[-1][0] >= level:
                    section_stack.pop()
                section_stack.append((level, text))
            return None

        section_path = tuple(t for _, t in section_stack)

        # Tables: serialise as Markdown for retrieval-friendly text.
        if label == "table" or hasattr(element, "data") and label.endswith("table"):
            md = self._table_to_markdown(element)
            if not md:
                return None
            return ParsedChunk(
                content=md,
                source_id=source_id,
                source_path=source_path,
                section_path=section_path,
                page_no=page_no,
                chunk_index=chunk_index,
                modality="table",
                raw_metadata={"parser": self.name, "label": label},
            )

        # Pictures: prefer OCR text, fall back to caption / alt-text.
        if label in ("picture", "figure"):
            text = self._picture_text(element)
            if not text:
                return None
            return ParsedChunk(
                content=text,
                source_id=source_id,
                source_path=source_path,
                section_path=section_path,
                page_no=page_no,
                chunk_index=chunk_index,
                modality="image",
                raw_metadata={"parser": self.name, "label": label},
            )

        # Default: prose paragraph / list-item / caption.
        text = (getattr(element, "text", "") or "").strip()
        if not text:
            return None
        return ParsedChunk(
            content=text,
            source_id=source_id,
            source_path=source_path,
            section_path=section_path,
            page_no=page_no,
            chunk_index=chunk_index,
            modality="text",
            raw_metadata={"parser": self.name, "label": label or "paragraph"},
        )

    @staticmethod
    def _page_no(element) -> Optional[int]:
        prov = getattr(element, "prov", None)
        if not prov:
            return None
        try:
            return int(prov[0].page_no)
        except (AttributeError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _heading_level(element) -> int:
        # Docling stores level on `level` (1-6). Default 2 if missing
        # so an unattributed heading still nests under a top-level one.
        return int(getattr(element, "level", 2) or 2)

    @staticmethod
    def _table_to_markdown(element) -> str:
        """Serialise a Docling TableItem to Markdown so embeddings see
        column headers next to cell values. Best-effort — falls back to
        the element's plain text if structured access fails."""
        if hasattr(element, "export_to_markdown"):
            try:
                md = element.export_to_markdown()
                if md:
                    return md
            except Exception:
                pass
        # Fall back to whatever text the IR has.
        return (getattr(element, "text", "") or "").strip()

    @staticmethod
    def _picture_text(element) -> str:
        # Docling exposes OCR'd text on PictureItem under various
        # attribute names depending on version. Try them in order.
        for attr in ("text", "caption", "alt_text"):
            value = getattr(element, attr, None)
            if value:
                value = str(value).strip()
                if value:
                    return value
        return ""


__all__ = ["DoclingNotInstalled", "DoclingParser"]
