"""
KnowledgeBaseIngester — orchestrates parser → embed → write → graph-link
for an uploaded document.

Per chunk, runs:

1. ``VerbatimStore.store(content, metadata)`` — embeds and persists the
   raw chunk with a ``store_type=verbatim_chunk`` marker. This is the
   primary retrieval target for KB content.

2. (optional) ``controller.observe(...)`` — also writes the chunk as an
   episodic memory so the entity index, schema integrator, and brain
   layers see it. Off by default to keep the cognitive layer focused on
   actual conversation.

3. Graph linkage:
   * a single document-root ``MemoryItem`` per upload (stored as
     ``SEMANTIC`` so it lives in the neocortex layer of the 3D view);
   * ``derived_from`` link from each chunk back to the root;
   * ``related`` links between sibling chunks within the same section
     (so retrieval expansion can surface neighbouring context).

This is the structural spine the Obsidian-like UI walks: the file tree
groups chunks by their root document, the backlinks panel uses the
``derived_from`` / ``related`` edges, and the 3D view places the root
in the neocortex shell with chunk satellites orbiting it.

Cognitive grounding: Tse et al. 2007 "schemas accelerate consolidation
when new info is congruent with existing structure." The document-root
node IS the schema; its descendant chunks share the schema and the
SchemaIntegrator can detect this from the shared ``source_id`` metadata.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from neuromem.core.audit.ingest_log import (
    IngestJob,
    IngestStage,
    default_log as default_ingest_log,
)
from neuromem.core.graph import MemoryGraph
from neuromem.core.ingest.registry import compute_source_id, parser_for_path
from neuromem.core.ingest.types import ParsedChunk
from neuromem.core.types import MemoryItem, MemoryLink, MemoryType
from neuromem.utils.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from neuromem import NeuroMem

logger = get_logger(__name__)


class KnowledgeBaseIngester:
    """Drive a parser through the verbatim + graph write pipeline.

    Held by the UI server as a per-process singleton (``NeuroMem`` is
    per-user, so the ingester is constructed against that user's
    NeuroMem instance).
    """

    def __init__(self, memory: "NeuroMem") -> None:
        self.memory = memory
        self.controller = memory.controller
        self.graph: MemoryGraph = self.controller.graph
        self.verbatim = self.controller.verbatim  # may be None if disabled

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def ingest_file(
        self,
        path: str,
        *,
        also_episodic: bool = False,
        log: Optional[Any] = None,
    ) -> IngestJob:
        """Parse + embed + write an entire file. Synchronous; the UI
        server wraps this in a thread for SSE-friendly progress."""

        ingest_log = log if log is not None else default_ingest_log

        if not Path(path).exists():
            raise FileNotFoundError(path)

        parser = parser_for_path(path)
        if parser is None:
            raise UnsupportedFileType(path)

        source_id = compute_source_id(path)
        job = ingest_log.begin(
            user_id=self.memory.user_id,
            source_path=path,
            source_id=source_id,
            parser_name=parser.name,
        )

        try:
            root_id = self._create_document_root(
                source_id=source_id,
                source_path=path,
                parser_name=parser.name,
            )
            ingest_log.record_write(job, memory_id=root_id)

            self._stream_chunks(
                parser=parser,
                path=path,
                source_id=source_id,
                root_id=root_id,
                also_episodic=also_episodic,
                job=job,
                ingest_log=ingest_log,
            )
            ingest_log.finish(job, status="completed")
        except Exception as exc:
            logger.exception("Ingest failed: %s", exc)
            ingest_log.error(job, exc)
            raise

        return job

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _create_document_root(self, *, source_id: str, source_path: str, parser_name: str) -> str:
        """Persist a single SEMANTIC ``MemoryItem`` representing the
        document as a whole. Its content is the filename + a brief
        marker so retrieval-by-content still surfaces it for queries
        like "the Q3 report".
        """
        backend = self.controller.episodic.backend
        root_id = f"doc_{source_id}"

        # Idempotency: if this exact source has been ingested before
        # (same path + mtime → same source_id), skip the root insert.
        existing = backend.get_by_id(root_id)
        if existing is not None:
            return root_id

        title = Path(source_path).name
        content = f"[document] {title}"

        # Embedding: cheap to embed the title; verbatim chunks carry the
        # actual content, so the root is just an index pointer.
        from neuromem.utils.embeddings import get_embedding

        try:
            embedding = get_embedding(
                content, self.memory.config.model().get("embedding", "text-embedding-3-large")
            )
        except Exception:
            embedding = []

        now = datetime.now(timezone.utc)
        item = MemoryItem(
            id=root_id,
            user_id=self.memory.user_id,
            content=content,
            embedding=embedding,
            memory_type=MemoryType.SEMANTIC,
            salience=0.7,
            confidence=1.0,
            created_at=now,
            last_accessed=now,
            decay_rate=0.0,
            reinforcement=0,
            inferred=False,
            editable=False,
            tags=["kb", f"source:{source_id}"],
            metadata={
                "source_id": source_id,
                "source_path": source_path,
                "parser": parser_name,
                "kind": "document_root",
            },
        )
        backend.upsert(item)
        return root_id

    def _stream_chunks(
        self,
        *,
        parser,
        path: str,
        source_id: str,
        root_id: str,
        also_episodic: bool,
        job: Optional[IngestJob],
        ingest_log,
    ) -> None:
        """Walk the parser's iterator and write each chunk."""

        prev_chunk_in_section: Optional[str] = None
        prev_section_path: Optional[tuple] = None

        for chunk in parser.parse(path, source_id=source_id):
            # Cooperative cancellation: the IngestLog ``cancel()`` call
            # flips status; we exit cleanly between chunks.
            if job is not None and job.status == "cancelled":
                logger.info("Ingest cancelled at chunk %d", chunk.chunk_index)
                return

            t_parse = time.time()
            ingest_log.add_stage(
                job,
                IngestStage(
                    name="parse_chunk",
                    elapsed_ms=0.0,
                    chunk_index=chunk.chunk_index,
                    notes={"modality": chunk.modality},
                ),
            )

            # Verbatim write — primary KB retrieval target.
            verbatim_ids: List[str] = []
            if self.verbatim is not None:
                t_write = time.time()
                verbatim_meta = self._chunk_metadata(chunk)
                verbatim_ids = self.verbatim.store(chunk.content, metadata=verbatim_meta)
                for vid in verbatim_ids:
                    ingest_log.record_write(job, verbatim_chunk_id=vid)
                ingest_log.add_stage(
                    job,
                    IngestStage(
                        name="write_chunk",
                        elapsed_ms=(time.time() - t_write) * 1000.0,
                        chunk_index=chunk.chunk_index,
                        notes={"verbatim_ids": verbatim_ids},
                    ),
                )

            # Episodic mirror — opt-in. Routes through the regular
            # observe() pipeline so entity extraction + auto-tagging fire.
            if also_episodic:
                t_obs = time.time()
                self.memory.observe(
                    user_input=chunk.content,
                    assistant_output="",  # one-sided observation; KB is "things the user told us"
                    metadata=self._chunk_metadata(chunk),
                )
                ingest_log.add_stage(
                    job,
                    IngestStage(
                        name="observe_chunk",
                        elapsed_ms=(time.time() - t_obs) * 1000.0,
                        chunk_index=chunk.chunk_index,
                    ),
                )

            # Graph linkage. We attach the FIRST verbatim id (most
            # parsers yield short-enough chunks that ``store()`` returns
            # exactly one id; long chunks split into a few). The root
            # links to every part; sibling-link uses the first part too.
            primary_id = verbatim_ids[0] if verbatim_ids else None
            if primary_id is not None:
                t_link = time.time()
                self.graph.add_link(
                    MemoryLink(
                        source_id=primary_id,
                        target_id=root_id,
                        link_type="derived_from",
                        strength=1.0,
                        created_at=datetime.now(timezone.utc),
                        metadata={"chunk_index": chunk.chunk_index},
                    )
                )
                # Sibling 'related' link within the same section.
                if prev_chunk_in_section is not None and prev_section_path == chunk.section_path:
                    self.graph.add_link(
                        MemoryLink(
                            source_id=primary_id,
                            target_id=prev_chunk_in_section,
                            link_type="related",
                            strength=0.5,
                            created_at=datetime.now(timezone.utc),
                            metadata={"reason": "sibling_in_section"},
                        )
                    )
                prev_chunk_in_section = primary_id
                prev_section_path = chunk.section_path
                ingest_log.add_stage(
                    job,
                    IngestStage(
                        name="link_chunk",
                        elapsed_ms=(time.time() - t_link) * 1000.0,
                        chunk_index=chunk.chunk_index,
                    ),
                )

            _ = t_parse  # keep stage timing local; used only inside the loop

    @staticmethod
    def _chunk_metadata(chunk: ParsedChunk) -> dict:
        meta = {
            "source_id": chunk.source_id,
            "source_path": chunk.source_path,
            "section_path": list(chunk.section_path),
            "modality": chunk.modality,
            "kb_chunk_index": chunk.chunk_index,
        }
        if chunk.page_no is not None:
            meta["page_no"] = chunk.page_no
        if chunk.raw_metadata:
            meta["raw"] = chunk.raw_metadata
        return meta


class UnsupportedFileType(ValueError):
    """Raised when no parser is registered for a path's suffix."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"No registered parser for {path!r}. Install the optional "
            "ingest extras: pip install 'neuromem-sdk[ingest]'"
        )
        self.path = path


__all__ = ["KnowledgeBaseIngester", "UnsupportedFileType"]
