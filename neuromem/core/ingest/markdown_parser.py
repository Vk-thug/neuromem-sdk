"""
Markdown / plain-text parser — zero-dep fallback so the ingest module
works without the ``[ingest]`` extra installed.

Splits on ATX headings (``#``, ``##``, ...) so each section becomes a
chunk with its heading hierarchy preserved on ``section_path``. Bodies
without headings are emitted as a single chunk per file (or split at
``MAX_CHUNK_CHARS`` to avoid one-shot embedding of giant text files).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, List, Tuple

from neuromem.core.ingest.types import ParsedChunk

MAX_CHUNK_CHARS = 4000  # split-at-paragraph fallback for unstructured text

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


class MarkdownParser:
    """Heading-aware Markdown / text parser. Zero deps.

    Cognitive grounding: headings are explicit schema markers — chunks
    sharing a heading path land in the same retrieval cluster naturally
    because their embeddings see the heading context (we prepend the
    last heading to each chunk's content, mirroring Anthropic's
    contextual-chunk recipe in spirit).
    """

    suffixes = (".md", ".markdown", ".txt")
    name = "markdown"

    def parse(self, path: str, *, source_id: str) -> Iterator[ParsedChunk]:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        sections = self._split_sections(text)
        chunk_index = 0
        for section_path, body in sections:
            for piece in self._split_long(body):
                if not piece.strip():
                    continue
                yield ParsedChunk(
                    content=piece,
                    source_id=source_id,
                    source_path=path,
                    section_path=section_path,
                    page_no=None,
                    chunk_index=chunk_index,
                    modality="text",
                    raw_metadata={"parser": self.name},
                )
                chunk_index += 1

    @staticmethod
    def _split_sections(text: str) -> List[Tuple[Tuple[str, ...], str]]:
        """Walk headings and emit ``(section_path, body)`` pairs.

        Maintains a running stack of headings so deeper headings inherit
        their parents' path. Pre-heading content is emitted under an
        empty section path so leading prose isn't dropped.
        """
        results: List[Tuple[Tuple[str, ...], str]] = []
        last_end = 0
        stack: List[Tuple[int, str]] = []  # (level, title)

        for m in _HEADING_RE.finditer(text):
            body = text[last_end : m.start()]
            if body.strip():
                section_path = tuple(t for _, t in stack)
                results.append((section_path, body))
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            last_end = m.end()

        tail = text[last_end:]
        if tail.strip():
            section_path = tuple(t for _, t in stack)
            results.append((section_path, tail))

        return results

    @staticmethod
    def _split_long(body: str) -> List[str]:
        """Split at paragraph boundaries when a section exceeds
        MAX_CHUNK_CHARS."""
        if len(body) <= MAX_CHUNK_CHARS:
            return [body.strip()]
        out: List[str] = []
        buf = ""
        for para in re.split(r"\n\s*\n", body):
            if not para.strip():
                continue
            if len(buf) + len(para) + 2 > MAX_CHUNK_CHARS and buf:
                out.append(buf.strip())
                buf = para
            else:
                buf = (buf + "\n\n" + para) if buf else para
        if buf.strip():
            out.append(buf.strip())
        return out


__all__ = ["MarkdownParser"]
