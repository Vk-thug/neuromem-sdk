"""
Audit log infrastructure for v0.4.0 UI.

Captures every ``observe()`` and ``retrieve()`` call into thread-safe ring
buffers so the local UI can render a live observation feed and an
Inngest-style retrieval-run inspector. Defaults are off-by-default for
production; the ``neuromem ui`` CLI flips them on.

Cognitive grounding: NeuroMem's ``explain(memory_id)`` already returns a
per-memory attribution dict (cited in `research/03-competitive-gap-analysis.md`
§4 as a unique developer-ergonomics win). The audit log generalises the same
idea over time: every retrieval call captures its full per-stage trace, and
every observation captures the salience / emotional / brain-tag derivations.
This is the substrate for the v0.5.0 H2-D7 calibrated-abstention work — once
the data is captured, the abstention threshold is tunable on real query
distributions.
"""

from neuromem.core.audit.ingest_log import IngestJob, IngestLog, IngestStage
from neuromem.core.audit.observation_log import ObservationEvent, ObservationLog
from neuromem.core.audit.retrieval_log import (
    RetrievalLog,
    RetrievalRun,
    RetrievalStage,
)

__all__ = [
    "IngestJob",
    "IngestLog",
    "IngestStage",
    "ObservationEvent",
    "ObservationLog",
    "RetrievalLog",
    "RetrievalRun",
    "RetrievalStage",
]
