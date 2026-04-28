"""
Tests for v0.4.0 knowledge-base ingest pipeline.

Covers:
* Parser registry — register / look up by suffix / look up by name.
* MarkdownParser — heading-aware chunking + section_path propagation.
* IngestLog — ring buffer + subscribers + cancel cooperative-flag.
* KnowledgeBaseIngester schema linkage — root + derived_from + sibling
  related edges (using the InMemoryBackend to avoid Ollama / Qdrant).

Docling-specific tests are skipped when the optional ``docling`` extra
isn't installed; the parser registry test confirms the registration
itself works without the package.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from neuromem.core.audit.ingest_log import IngestLog, IngestStage
from neuromem.core.ingest import (
    MarkdownParser,
    ParsedChunk,
    compute_source_id,
    parser_for_name,
    parser_for_path,
    register_parser,
    supported_suffixes,
)


# ---------------------------------------------------------------------------
# Parser registry
# ---------------------------------------------------------------------------


class TestParserRegistry:
    def test_markdown_registered_for_md(self) -> None:
        parser = parser_for_path("notes.md")
        assert parser is not None
        assert isinstance(parser, MarkdownParser)

    def test_markdown_registered_for_txt(self) -> None:
        parser = parser_for_path("notes.TXT")
        assert parser is not None  # case-insensitive

    def test_unknown_suffix_returns_none(self) -> None:
        assert parser_for_path("data.xyz") is None

    def test_supported_suffixes_includes_docling_formats(self) -> None:
        suffixes = set(supported_suffixes())
        # Markdown is always present (zero-dep).
        assert ".md" in suffixes
        # Docling suffixes are registered with explicit ``suffixes=`` so
        # the suffix index is populated even without the docling package
        # installed.
        for s in (".pdf", ".docx", ".xlsx", ".pptx", ".html", ".png", ".jpg"):
            assert s in suffixes

    def test_register_custom_parser_overrides(self) -> None:
        class FakeParser:
            suffixes = (".fake",)
            name = "fake"

            def parse(self, path, *, source_id):
                yield ParsedChunk(
                    content="x", source_id=source_id, source_path=path
                )

        register_parser("fake", FakeParser)
        parser = parser_for_name("fake")
        assert parser is not None
        chunks = list(parser.parse("any.fake", source_id="s"))
        assert chunks[0].content == "x"

    def test_compute_source_id_stable_for_same_path(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("hello")
        a = compute_source_id(str(f))
        b = compute_source_id(str(f))
        assert a == b
        assert len(a) == 16  # 16 hex chars


# ---------------------------------------------------------------------------
# MarkdownParser
# ---------------------------------------------------------------------------


class TestMarkdownParser:
    def test_parses_section_hierarchy(self, tmp_path: Path) -> None:
        f = tmp_path / "n.md"
        f.write_text(
            "Intro paragraph.\n\n"
            "# Top\n\n"
            "Top body.\n\n"
            "## Sub\n\n"
            "Sub body line 1.\n"
            "Sub body line 2.\n\n"
            "## Sub2\n\n"
            "Sibling body.\n",
        )
        chunks = list(MarkdownParser().parse(str(f), source_id="src"))
        assert len(chunks) == 4
        assert chunks[0].section_path == ()
        assert chunks[1].section_path == ("Top",)
        assert chunks[2].section_path == ("Top", "Sub")
        assert chunks[3].section_path == ("Top", "Sub2")

    def test_chunk_index_monotonic(self, tmp_path: Path) -> None:
        f = tmp_path / "n.md"
        f.write_text("# A\n\none\n\n# B\n\ntwo\n")
        chunks = list(MarkdownParser().parse(str(f), source_id="s"))
        assert [c.chunk_index for c in chunks] == [0, 1]

    def test_long_unstructured_text_splits(self, tmp_path: Path) -> None:
        f = tmp_path / "n.txt"
        # No headings, > MAX_CHUNK_CHARS.
        body = ("paragraph " * 200 + "\n\n") * 10
        f.write_text(body)
        chunks = list(MarkdownParser().parse(str(f), source_id="s"))
        assert len(chunks) > 1
        assert all(len(c.content) <= 5000 for c in chunks)


# ---------------------------------------------------------------------------
# IngestLog
# ---------------------------------------------------------------------------


class TestIngestLog:
    def test_disabled_by_default(self) -> None:
        log = IngestLog()
        assert log.enabled is False
        assert log.begin(
            user_id="u", source_path="/x", source_id="s", parser_name="md"
        ) is None

    def test_lifecycle(self) -> None:
        log = IngestLog(capacity=10)
        log.enable()
        job = log.begin(user_id="u", source_path="/x", source_id="s", parser_name="md")
        assert job is not None
        log.add_stage(job, IngestStage(name="parse_chunk", elapsed_ms=1.0, chunk_index=0))
        log.add_stage(job, IngestStage(name="write_chunk", elapsed_ms=2.0, chunk_index=0))
        log.finish(job)
        assert job.status == "completed"
        assert job.parsed_chunks == 1
        assert job.written_chunks == 1

    def test_cancel_marks_status(self) -> None:
        log = IngestLog()
        log.enable()
        job = log.begin(user_id="u", source_path="/x", source_id="s", parser_name="md")
        ok = log.cancel(job.id)
        assert ok
        assert job.status == "cancelled"
        # Re-cancel returns False.
        assert log.cancel(job.id) is False

    def test_subscriber_fires_on_each_stage(self) -> None:
        log = IngestLog()
        log.enable()
        seen = []
        unsubscribe = log.subscribe(lambda j: seen.append(j.status))
        job = log.begin(user_id="u", source_path="/x", source_id="s", parser_name="md")
        log.add_stage(job, IngestStage(name="parse_chunk", elapsed_ms=0, chunk_index=0))
        log.finish(job)
        assert seen[0] == "running"   # begin
        assert seen[-1] == "completed"
        unsubscribe()


# ---------------------------------------------------------------------------
# KnowledgeBaseIngester (uses MarkdownParser + InMemoryBackend)
# ---------------------------------------------------------------------------


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = tmp_path / "doc.md"
    f.write_text(
        "# Q3 Report\n\n"
        "## Revenue\n\n"
        "Total revenue was $5M.\n\n"
        "Growth was 12% QoQ.\n\n"
        "## Risks\n\n"
        "Currency exposure noted.\n",
    )
    return f


@pytest.fixture
def ingester_mock(monkeypatch):
    """Build a KnowledgeBaseIngester whose memory uses an in-memory
    backend so the test doesn't touch Ollama / Qdrant."""
    from neuromem.core.graph import MemoryGraph
    from neuromem.core.ingest.ingester import KnowledgeBaseIngester
    from neuromem.core.verbatim import VerbatimStore
    from neuromem.storage.memory import InMemoryBackend

    backend = InMemoryBackend()

    # Patch get_embedding to return a deterministic vector so the
    # VerbatimStore.store path doesn't hit Ollama.
    monkeypatch.setattr(
        "neuromem.utils.embeddings.get_embedding",
        lambda text, model=None, **kw: [0.1, 0.2, 0.3],
    )
    monkeypatch.setattr(
        "neuromem.core.verbatim.get_embedding",
        lambda text, model=None, **kw: [0.1, 0.2, 0.3],
    )
    monkeypatch.setattr(
        "neuromem.core.ingest.ingester.get_embedding",
        lambda text, model=None, **kw: [0.1, 0.2, 0.3],
        raising=False,
    )

    verbatim = VerbatimStore(backend=backend, user_id="u1")
    graph = MemoryGraph()

    controller = MagicMock()
    controller.episodic.backend = backend
    controller.verbatim = verbatim
    controller.graph = graph

    config = MagicMock()
    config.model.return_value = {"embedding": "stub"}

    memory = MagicMock()
    memory.user_id = "u1"
    memory.controller = controller
    memory.config = config

    return KnowledgeBaseIngester(memory)


class TestKnowledgeBaseIngester:
    def test_creates_document_root_and_chunks(self, ingester_mock, md_file: Path) -> None:
        log = IngestLog()
        log.enable()
        job = ingester_mock.ingest_file(str(md_file), log=log)
        assert job.status == "completed"
        # MarkdownParser yields one chunk per heading-section body. The
        # fixture has two non-empty sections (Revenue, Risks) — the
        # ``# Q3 Report`` body is empty since ``## Revenue`` comes
        # immediately after.
        assert job.written_chunks == 2
        assert job.parsed_chunks == 2

    def test_root_node_persisted_and_links_present(
        self, ingester_mock, md_file: Path
    ) -> None:
        ingester_mock.ingest_file(str(md_file))
        backend = ingester_mock.controller.episodic.backend
        graph = ingester_mock.controller.graph
        source_id = compute_source_id(str(md_file))
        root = backend.get_by_id(f"doc_{source_id}")
        assert root is not None
        assert root.metadata["kind"] == "document_root"
        # Every chunk should have a derived_from edge to the root.
        backlinks = graph.get_backlinks(f"doc_{source_id}", link_type="derived_from")
        assert len(backlinks) >= 1

    def test_idempotent_re_ingest(self, ingester_mock, md_file: Path) -> None:
        ingester_mock.ingest_file(str(md_file))
        backend = ingester_mock.controller.episodic.backend
        first_count = len(backend.list_all(user_id="u1", limit=1000))
        ingester_mock.ingest_file(str(md_file))
        # VerbatimStore dedupes by content hash; re-ingest should not
        # duplicate chunks (root stays single, chunk hashes match).
        second_count = len(backend.list_all(user_id="u1", limit=1000))
        assert second_count == first_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
