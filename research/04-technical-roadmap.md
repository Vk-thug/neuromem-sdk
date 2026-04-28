# Phase 6 — Technical Roadmap

*The payload. Every item below has a citable Phase-0/1/2/3/4/5 origin and a concrete line-item diff. Items are not ordered by "interesting" — they are ordered by severity × (1/effort) per Phase 5 §5, then resequenced when horizon dependencies force a change.*

**Snapshot date:** 2026-04-24. **Base version:** neuromem-sdk v0.3.2.

---

## 0. Horizons & ownership assumption

- **H1 — table stakes (0-4 weeks).** Where NeuroMem is visibly behind commodity expectations, or a documented user pain point is close to free. Must not degrade any §4 win from Phase 5.
- **H2 — differentiators (1-3 months).** Where NeuroMem can *win*, not just catch up. Cognitive grounding is mandatory here — these are the "brain-faithful" roadmap items.
- **H3 — research bets (3-6 months).** High variance, high upside. Required ROI is lower because the downside is a publishable negative result.

**Staffing assumption.** One senior engineer (Vikram) part-time, mode "start the week on H1, pull H2 forward on Fridays." Large items (H1-R3 persistent graph, H2-D2 replay scheduler) get explicit multi-week slots.

**Cross-cutting constraint.** Every item is held to: (a) benchmark regression bar — no drop on MemBench / LongMemEval / ConvoMem vs v0.3.2; (b) Phase-0 §20 bug debts are paid as the item touches them (double-counted reinforcement; `new_procedural_memories` empty; `observe_multimodal` stub); (c) Phase-3 §16.1.4 LangGraph correctness lessons (awaited writes; `created_at` preservation) apply wherever we touch stores.

---

## H1 — Table stakes (0-4 weeks)

### H1-R1 — `NeuroMemStore(BaseStore)` for LangGraph

**Problem.** Adapter `neuromem/adapters/langgraph.py` advertises `NeuroMemStore — LangGraph BaseStore implementation` in the module docstring but the class is absent; exports are only node-factory helpers (Phase 0 §13). LangGraph users today rebuild semantic retrieval by hand (LangMem #154, Phase 3 §16.1.3). Closing this gap is the single most impactful distribution win (Phase 5 §5 Gap 1).

**Cognitive grounding.** Engineering catch-up. No cognitive claim.

**Prior art.** LangMem `create_manage_memory_tool` / `create_search_memory_tool` over `AsyncPostgresStore`. Phase 3 §16.1.4 issue #7411 ("`InMemoryStore.put()` overwrites `created_at` on update") and #7094 ("memory leak with `durability="async"`") define the correctness bar.

**Proposed API.**
```python
# neuromem/adapters/langgraph_store.py
from __future__ import annotations
from typing import Any, AsyncIterator, Iterable, Sequence
from langgraph.store.base import BaseStore, Item, SearchItem, PutOp, GetOp, SearchOp

class NeuroMemStore(BaseStore):
    """LangGraph BaseStore backed by a NeuroMem instance.

    Maps BaseStore namespaces to NeuroMem ``user_id``:
      namespace = (user_id, *optional_sub_ns)
    All operations are awaited (never fire-and-forget) per LangGraph #7094.
    ``created_at`` is preserved on update per LangGraph #7411.
    """
    def __init__(self, neuromem: "NeuroMem", k: int = 8) -> None: ...
    async def aget(self, namespace: tuple[str, ...], key: str) -> Item | None: ...
    async def aput(
        self, namespace: tuple[str, ...], key: str, value: dict[str, Any]
    ) -> None: ...
    async def adelete(self, namespace: tuple[str, ...], key: str) -> None: ...
    async def asearch(
        self,
        namespace_prefix: tuple[str, ...],
        *,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[SearchItem]: ...
    async def abatch(self, ops: Sequence[PutOp | GetOp | SearchOp]) -> list[Any]: ...
    # Sync variants defer to asyncio.run on the async methods.
```

**Data-model delta.** None to existing storage backends. Maps `namespace` to a `(user_id, scope)` tuple stored in `MemoryItem.metadata["langgraph_namespace"]`; keys become `MemoryItem.id`. `created_at` is the existing field.

**LangGraph integration.** The class *is* the LangGraph integration. Package in a new `neuromem-sdk[langgraph]` extra; `langgraph>=1.0.0,<2.0.0` pin. Do not introduce `langgraph` into core.

**Test plan.**
- Unit: every `BaseStore` method against an in-memory NeuroMem.
- Integration: pytest suite importing `langgraph==1.0.10` (matches LangGraph #7094 repro) running a 50-superstep graph that writes/reads memory, asserting no checkpoint-dict accumulation.
- Correctness: regression test for `created_at` preservation on update.
- E2E: a real LangGraph agent using `NeuroMemStore` over Postgres; compares retrieval quality vs plain `AsyncPostgresStore` + keyword search — NeuroMem must win on a representative question set.

**Effort.** **S-M** (~1 week). New file ~200-300 LOC + tests.

**Risk / cost.** Low. `BaseStore` surface is small. Mitigations: pin langgraph version; opt-in extra; do not expose async semantics into NeuroMem core.

---

### H1-R2 — Contextual-chunk embeddings in `VerbatimStore`

**Problem.** `VerbatimStore.store` (`neuromem/core/verbatim.py:132`) chunks raw text and embeds directly, with no document-level context prepended. Anthropic's documented recipe reduces retrieval failure rate −35% relative from this single step (Phase 4 §16.3.7). This is Phase 5 Gap 2.

**Cognitive grounding.** Engineering catch-up. No cognitive claim; grounded in published empirical data.

**Prior art.** Anthropic Contextual Retrieval blog 2024-09-19. Failure-rate table: plain embeddings 5.7% → contextual 3.7% → +BM25 2.9% → +reranker 1.9%. NeuroMem already has BM25 and reranker, so contextual prepend is the missing step.

**Proposed API.**
```python
# neuromem.yaml
verbatim:
  contextual_prepend:
    enabled: false               # opt-in for v0.4.0
    provider: ollama             # ollama | openai | anthropic
    model: qwen2.5-coder:7b
    max_context_tokens: 100
    cache_dir: ~/.cache/neuromem/contextual
```
```python
# neuromem/core/verbatim.py
def _contextualize(
    self, document: str, chunk: str, chunk_index: int, cfg: dict
) -> str:
    """Return ``chunk`` with an LLM-generated 50-100 token prefix.

    Prompt caches the document once per document; per-chunk cost is only
    the completion. Returns raw chunk on any error (fallback, never fail).
    """
```

**Data-model delta.** New `MemoryItem.metadata["contextual_prefix"]` (optional). Embedding is computed over `prefix + "\n\n" + chunk`. Storage of the prefix is for audit/replay only; retrieval uses only the concat.

**LangGraph integration.** Transparent — `VerbatimStore` is internal.

**Test plan.**
- Unit: mock-LLM returning a canned prefix; assert it lands in `metadata` and that the embedding is computed over `prefix + chunk`.
- Cache: round-trip test that re-ingesting the same document re-uses the prefix cache.
- Benchmark: LongMemEval with `contextual_prepend.enabled=true` vs baseline. **Success criterion: R@5 ≥ v0.3.2 baseline +1 pt**. Expected delta from Anthropic study is much larger; we accept 1 pt because NeuroMem's stack already includes BM25 + reranker.
- Regression: MemBench / ConvoMem must not drop.

**Effort.** **S** (~3-5 days).

**Risk / cost.** Index-time LLM calls add cost. Mitigations: off by default; prompt caching reduces per-chunk cost to ~$1/M document tokens (Anthropic figure); failure of contextualiser falls through to raw-chunk behaviour (defence-in-depth).

---

### H1-R3 — Persistent graph via `GraphBackend` Protocol

**Problem.** `MemoryGraph` is an in-process Python dict (Phase 0 §11). Lost on process exit; divergent across workers; blocks any production multi-worker deploy. Phase 5 Gap 3, severity H.

**Cognitive grounding.** Engineering catch-up.

**Prior art.** Graphiti's Neo4j/FalkorDB/Kuzu/Neptune backends (Phase 1 §7). MemPalace's local-SQLite temporal KG (Phase 1 §14). Phase 3 §16.1.2 scaling lessons — any graph layer must be async from day one and avoid all-members LLM scans.

**Proposed API.**
```python
# neuromem/storage/graph_base.py
from typing import Protocol
class GraphBackend(Protocol):
    def add_link(self, link: MemoryLink) -> None: ...
    def remove_link(self, source_id: str, target_id: str) -> bool: ...
    def remove_all_links(self, memory_id: str) -> int: ...
    def get_links(self, memory_id: str, link_type: str | None = None) -> list[MemoryLink]: ...
    def get_backlinks(self, memory_id: str, link_type: str | None = None) -> list[MemoryLink]: ...
    def get_related(self, memory_id: str, depth: int) -> list[str]: ...
    def register_entities(self, memory_id: str, entities: list[str]) -> None: ...
    def find_memories_by_entity(self, entity: str) -> set[str]: ...
    def query_as_of(self, memory_id: str, as_of: datetime | None = None) -> list[MemoryLink]: ...
    def invalidate(self, source: str, target: str, link_type: str, ended_at: datetime | None = None) -> bool: ...
    def export(self) -> dict: ...

# neuromem/storage/graph_inprocess.py  — current MemoryGraph becomes this
# neuromem/storage/graph_postgres.py   — new: JSONB tables
# neuromem/storage/graph_neo4j.py      — H2 optional add
```

**Data-model delta.**
- Postgres schema:
  - `memory_links(source_id UUID, target_id UUID, link_type TEXT, strength REAL, created_at TIMESTAMPTZ, valid_from TIMESTAMPTZ, valid_to TIMESTAMPTZ, metadata JSONB, PRIMARY KEY (source_id, target_id, link_type))`.
  - Index on `(source_id)`, `(target_id)`, `(link_type)`, and a partial index `WHERE valid_to IS NULL` for "currently active" queries.
  - `memory_entities(entity TEXT, memory_id UUID, PRIMARY KEY (entity, memory_id))`.
- `MemoryGraph` becomes a thin orchestrator: `MemoryGraph(backend: GraphBackend)`.

**LangGraph integration.** Orthogonal. Phase H1-R1 `NeuroMemStore` does not touch the graph.

**Test plan.**
- Protocol conformance: all existing graph tests (`test_graph.py` 267 LOC) pass unchanged on `InProcessGraphBackend`.
- Parity: same test suite passes on `PostgresGraphBackend` against a docker-compose Postgres.
- Benchmark: no regression on MemBench / LongMemEval / ConvoMem.
- Crash test: kill the process after 100 `observe()` calls, restart, assert graph state is intact on Postgres backend; assert it's *gone* on in-process (documents the expected divergence).

**Effort.** **L** (~3-4 weeks).

**Risk / cost.** This is a core-surface change. Mitigations: new Protocol + new backend + current behaviour preserved under `InProcessGraphBackend`; ship behind a feature flag `storage.graph.backend` defaulting to `inprocess`. Benchmarks run against `inprocess` to prove zero regression; then run against `postgres` to validate parity.

---

### H1-R4 — Swappable reranker config section

**Problem.** `neuromem/core/cross_encoder_reranker.py` hardcodes `ms-marco-MiniLM-L-12-v2`. Graphiti #1393 shows the exact failure mode when a reranker is hardcoded to one provider — users running Anthropic / Gemini / Groq for LLM + embedder cannot remove the OpenAI dependency. Phase 5 Gap 6.

**Cognitive grounding.** Engineering catch-up.

**Prior art.** Graphiti reranker providers (`OpenAIRerankerClient`, `GeminiRerankerClient`, `BGERerankerClient`). Phase 3 §16.1.2 #1393 has the fix shape — a `reranker` config section parallel to `llm` and `embedder`.

**Proposed API.**
```yaml
# neuromem.yaml
retrieval:
  reranker:
    provider: sentence-transformers  # sentence-transformers | cohere | bge | openai | gemini
    model: cross-encoder/ms-marco-MiniLM-L-12-v2
    top_n: 30
    blend_weight: 0.9
```
```python
# neuromem/core/cross_encoder_reranker.py
def get_reranker(provider: str, model: str, **kwargs) -> Reranker: ...

class Reranker(Protocol):
    def rerank(self, query: str, docs: list[str]) -> list[float]: ...
```

**Data-model delta.** None.

**LangGraph integration.** Transparent.

**Test plan.**
- Unit per provider with mocked HTTP where needed.
- Integration: real sentence-transformers smoke test; Cohere/BGE/OpenAI behind `pytest -m external` marker.
- Regression: MemBench/LongMemEval/ConvoMem on the default provider — no drop.

**Effort.** **S** (~3 days).

**Risk / cost.** Low. Mitigations: default preserves current model.

---

### H1-R5 — `forget()` sweep across all surfaces

**Problem.** `NeuroMem.forget(memory_id)` deletes from episodic/semantic/procedural and removes graph links only (Phase 0 §13 `forget_memory`). Residual traces remain in: `VerbatimStore` chunks sharing `cognitive_id`; `_entity_index`; brain `SparseCode` metadata; `WorkingMemoryBuffer`; `RetrievalStats` cache; `ReconsolidationPolicy` state; auto-tagger outputs; HyDE cache if query strings contain the memory. Enterprise compliance table stakes. Phase 5 Gap 7.

**Cognitive grounding.** Larimar (Phase 1 §9) — explicit selective-forget with leakage prevention. Phase 2 §6 on forgetting-as-a-first-class-API.

**Prior art.** Larimar `forget` API. `arxiv 2403.11901`.

**Proposed API.**
```python
# neuromem/__init__.py  NeuroMem facade
def forget(
    self,
    memory_id: str,
    scope: Literal["memory", "all"] = "memory",
    verify: bool = False,
) -> ForgetReport: ...

@dataclass(frozen=True)
class ForgetReport:
    memory_id: str
    cleaned: list[str]     # surfaces successfully cleared
    residual: list[str]    # surfaces that still contained references
    swept_chunk_ids: list[str]
    swept_entity_entries: int
    swept_brain_state: bool
    swept_reconsolidation_cache: bool
    swept_retrieval_cache: bool
```

**Data-model delta.** No schema change. Sweep additions at:
- `VerbatimStore` — delete chunks where `metadata["cognitive_id"] == memory_id`.
- `MemoryGraph._entity_index` — remove memory_id from every entity set; purge entities whose set is now empty.
- `BrainSystem` — call `working_memory.remove(memory_id)` and delete the sparse-code entry from persisted `BrainState`.
- `MemoryController._retrieval_cache` — pop the key.
- `ReconsolidationPolicy` — no per-memory state today; add a clear hook that is a no-op now but available for future state.

**LangGraph integration.** `NeuroMemStore.adelete` calls `forget(id, scope="all")` by default — wraps the compliance guarantee at the store surface.

**Test plan.**
- Unit: per-surface assertion that `forget(memory_id, scope="all")` removes all traces.
- Audit: `verify=True` runs a parallel grep against all surfaces and populates `ForgetReport.residual` — used in compliance tests.
- Regression: retrieval on un-forgotten memories unaffected.

**Effort.** **S** (~3 days).

**Risk / cost.** Low. Mitigations: `scope="memory"` preserves current behaviour; `scope="all"` is opt-in until v0.4.0 changes default.

---

### H1-R6 — Tokenizer / entity-extractor injection points

**Problem.** `core/bm25_scorer.py` uses whitespace tokenisation + English stopwords; `core/graph.py::extract_entities` uses English capitalization heuristics. Non-English users silently get degraded retrieval (Mem0 #4884, Phase 3 §16.1.1). Phase 5 Gap 10.

**Cognitive grounding.** Engineering catch-up; fairness concern.

**Prior art.** Mem0 #4884 documents the failure mode. LangChain's `TokenizerBase`.

**Proposed API.**
```python
# neuromem/core/bm25_scorer.py
class BM25Scorer:
    def __init__(
        self,
        documents: list[str],
        tokenizer_fn: Callable[[str], list[str]] | None = None,
    ): ...

# neuromem/core/graph.py
def extract_entities(
    text: str,
    extractor_fn: Callable[[str], list[str]] | None = None,
) -> list[str]: ...

# neuromem/tokenizers/__init__.py  NEW
def whitespace_english(text: str) -> list[str]: ...       # current default
def spacy_multilang(text: str, lang: str) -> list[str]: ...  # opt-in via `neuromem-sdk[multilang]`
def char_ngram(text: str, n: int = 3) -> list[str]: ...   # CJK fallback
```

**Data-model delta.** None.

**LangGraph integration.** Transparent.

**Test plan.**
- Unit with CJK, Arabic, Thai, Devanagari strings — assert entities and BM25 tokens are non-empty with `char_ngram` fallback.
- Benchmark regression on English (default path unchanged).

**Effort.** **S** (~2-3 days).

**Risk / cost.** Low. Mitigations: default tokenizer unchanged; injection is opt-in.

---

### H1-R7 — Provider-tagged exceptions

**Problem.** Embedding, LLM rerank, HyDE, consolidation, and auto-tagging paths call providers without exception wrapping. When a non-OpenAI upstream rate-limits, the error propagates as whatever the SDK raised — Letta #3310 is the cautionary example ("Rate limited by OpenAI" when talking to z.ai). Phase 5 Gap 9.

**Cognitive grounding.** Engineering catch-up.

**Prior art.** Letta #3310.

**Proposed API.**
```python
# neuromem/utils/providers.py  NEW
class ProviderError(Exception):
    def __init__(self, provider: str, upstream: Exception, operation: str) -> None: ...

def with_provider(provider: str, operation: str):
    """Decorator that wraps upstream exceptions with ``ProviderError``."""

# Usage in neuromem/utils/embeddings.py
@with_provider("openai", "embed")
def get_embedding(...): ...
```

**Data-model delta.** None.

**LangGraph integration.** `NeuroMemStore.asearch` surfaces `ProviderError` unchanged — users catch by provider.

**Test plan.**
- Unit: inject a raising mock per provider; assert `ProviderError` with correct `.provider` and `.operation`.

**Effort.** **S** (~1-2 days).

**Risk / cost.** Low.

---

### H1-R8 — Docker + Cloud Run manifests

**Problem.** No `Dockerfile`, no `compose.yaml`, no Cloud Run spec (Phase 0 §17, Phase 5 Gap 8). Every enterprise user's first question.

**Cognitive grounding.** Engineering catch-up.

**Prior art.** Letta's `compose.yaml`, Alembic migrations. Mem0's `deploy/` layout (but see Mem0 #4945 for the pitfalls — multi-arch manifests need GH Actions).

**Proposed API.**
```
deploy/
  Dockerfile                 # python:3.12-slim base
  docker-compose.yml         # neuromem + postgres(+pgvector) + qdrant
  cloudrun/
    service.yaml             # memory-efficient Cloud Run config
  README.md                  # env vars, secrets, scaling notes
```

**Data-model delta.** None.

**LangGraph integration.** None.

**Test plan.**
- CI: build the docker image in GH Actions; boot it; run `python -c "from neuromem import NeuroMem; ..."` smoke; deploy to Cloud Run in a preview env for each tagged release.

**Effort.** **S** (~2-3 days).

**Risk / cost.** Low.

---

### H1-R9 — Pay down Phase 0 §20 bug debts

**Problem.** Four concrete correctness bugs surfaced in Phase 0:
- **Double-counted reinforcement** — `DecayEngine.reinforce` and `ReconsolidationPolicy.update_memory_after_retrieval` both bump `reinforcement` in the same retrieve loop.
- **`new_procedural_memories` is always empty** — `Consolidator` branches exist but never populate this list.
- **`observe_multimodal` is a text-only stub** despite the multimodal/ tree.
- **Consolidation `days_threshold=0`** makes every episodic item immediately eligible, defeating CLS grounding (though this is a Phase 2 §2 finding; the fix is partly H1 config default, partly H2 replay scheduler).

**Cognitive grounding.** Phase 2 §2 (CLS-slow) for the `days_threshold` item.

**Prior art.** Phase 0 §20 bug list.

**Proposed API.** No surface change.

**Data-model delta.** None.

**LangGraph integration.** None.

**Test plan.**
- Regression test that `reinforcement` increments by 1 per retrieval, not 2.
- Regression test that consolidation of "user prefers X" landed in `procedural`, not `semantic`.
- `observe_multimodal` returns a clear `NotImplementedError` or routes to a new text-fallback branch *with a user-visible warning*, not a silent stub.
- `days_threshold` default changes to `1` (day); add `consolidation.immediate_mode: bool = false` escape hatch for the current behaviour.

**Effort.** **S** (~2-3 days across the four items).

**Risk / cost.** Low, and these are already Phase-5 §4 wins we're defending. Mitigations: changes are additive or guarded.

---

### H1 total estimate

**~4 engineer-weeks** for 9 items:
- R1 `NeuroMemStore` (~1w)
- R2 contextual embeddings (~3-5d)
- R3 persistent graph (~3-4w — but runs in parallel as background thread through H1 and spills into H2)
- R4 reranker config (~3d)
- R5 `forget()` sweep (~3d)
- R6 tokenizer injection (~2-3d)
- R7 provider exceptions (~1-2d)
- R8 docker/cloud-run (~2-3d)
- R9 bug debts (~2-3d)

R3 is the dominant cost. If it slips into H2, that's fine; the rest of H1 is parallelisable around it.

---

## H2 — Differentiators (1-3 months)

### H2-D1 — Personalized PageRank on entity graph

**Problem.** `MemoryController._graph_retrieve` uses BFS (Phase 0 §6, Phase 1 §3). HippoRAG's 6-13× speed advantage and 20% multi-hop improvement over SOTA retrievers comes from PPR, not the KG shape. Phase 5 Gap 4.

**Cognitive grounding.** Hippocampal indexing theory (Phase 2 §3) + spreading activation (Collins & Loftus 1975) modelled over schema-congruent communities (Phase 2 §9). Entities-as-indices activate in parallel; PPR is the algorithmic form of spreading activation at equilibrium.

**Prior art.** HippoRAG, Gutiérrez et al., arXiv 2405.14831, NeurIPS 2024. HippoRAG 2, arXiv 2502.14802, ICML 2025. Reference implementation: `OSU-NLP-Group/HippoRAG`.

**Proposed API.**
```python
# neuromem/core/graph_retrieve.py  NEW
class GraphRetriever:
    def __init__(self, graph_backend: GraphBackend): ...

    def retrieve(
        self,
        query_entities: list[str],
        mode: Literal["bfs", "ppr"] = "ppr",
        k: int = 10,
        ppr_restart: float = 0.5,
        ppr_max_iter: int = 30,
        ppr_tol: float = 1e-6,
    ) -> list[tuple[str, float]]:  # (memory_id, ppr_mass)
        ...
```
```yaml
# neuromem.yaml
retrieval:
  graph:
    mode: ppr            # bfs | ppr
    ppr_restart: 0.5
    ppr_blend_weight: 0.3  # how strongly PPR score blends into reranker
```

**Data-model delta.** None. Uses existing `_entity_index` + adjacency maps. PPR is computed ad-hoc over a NumPy sparse matrix built at query time from the current in-memory or Postgres graph slice (filtered to the user_id's partition).

**LangGraph integration.** Transparent — `_graph_retrieve` is behind the retrieve pipeline.

**Test plan.**
- Unit: synthetic graph where PPR-mass ordering differs from BFS-depth ordering; assert PPR returns the HippoRAG-expected winner.
- Benchmark: LongMemEval multi-session subset (the 2/30 counting-type failures Phase 0 §1 called out). **Success criterion: LongMemEval multi-session ≥ 95.0%** (up from 93.3%).
- Latency: assert PPR query latency < 50ms on a 10k-node user graph.

**Effort.** **M** (~2 weeks).

**Risk / cost.** PPR requires constructing the sparse adjacency matrix on each query. Mitigations: cache the matrix keyed on `(user_id, graph_version)`; invalidate on `add_link` / `invalidate`. For very large graphs (>100k nodes per user — unlikely but possible in long-running deployments), fall back to BFS.

---

### H2-D2 — Replay / CLS-slow consolidation scheduler

**Problem.** Consolidation fires every `consolidation_interval=10` turns at `days_threshold=0` (Phase 0 §9) — the opposite of CLS-slow. The `brain.hippocampus.ripple_interval_minutes` / `ripple_batch_size` config fields exist with no consumer (Phase 0 §20.10). Phase 5 Gap 5. Marquee differentiator — **no surveyed system has this**.

**Cognitive grounding.** Complementary Learning Systems, McClelland/McNaughton/O'Reilly 1995 (Phase 2 §2). Sharp-wave ripple replay, Buzsáki 1989 + Wilson & McNaughton 1994 + Ji & Wilson 2007 (Phase 2 §5). Schema-congruent consolidation speedup, Tse et al. 2007 (Phase 2 §9).

**Prior art.** Phase 2 §16.1 "Replay / Consolidation Scheduler" proposal. No AI-memory system ships this — see Phase 1 §17 cross-system matrix row "CLS-style slow consolidation".

**Proposed API.**
```yaml
# neuromem.yaml
brain:
  hippocampus:
    ripple_interval_minutes: 20
    ripple_batch_size: 10
  replay:
    enabled: true
    idle_threshold_minutes: 15     # fire only after N min with no observe()
    interleave_ratio: 0.3          # 70% recent episodic, 30% old semantic
    update_existing_semantic: true # vs always-add
    min_sequence_length: 3         # replay a *sequence*, not single memories
    schema_congruence_gate: true   # Tse et al. 2007 — congruent consolidates sooner
```
```python
# neuromem/core/workers/replay_worker.py  NEW
class ReplayWorker(BaseWorker):
    """CLS-faithful offline consolidation.

    Fires on a cron OR after ``idle_threshold_minutes`` of no observe() calls.
    Per tick:
      1. Sample ``ripple_batch_size`` recent episodic items as a sequence
         (sorted by created_at) — compressed-replay analogue.
      2. Sample ``ripple_batch_size * interleave_ratio`` existing semantic
         items that are schema-congruent (via SchemaIntegrator centroids).
      3. Run fact-extraction over the combined sequence.
      4. For each extracted fact, decide add / update-existing-id / no-op
         via the reconsolidation LLM call (cf. H2-D3).
    """
```

**Data-model delta.** No schema change. Adds `metadata["replay_generation"]: int` to semantic items — tracks which replay pass they're from, so we can roll back.

**LangGraph integration.** None directly; the worker runs in the existing `MaintenanceWorker` / Inngest infrastructure (Phase 0 §12).

**Test plan.**
- Unit: mock clock; assert `ReplayWorker` fires on `idle_threshold_minutes`.
- Behavioural: ingest 100 episodic memories across 3 topics; run replay; assert semantic items are updated-in-place (not always added) and that schema-congruent items consolidate faster than incongruent ones (Tse et al. prediction).
- Benchmark: LongMemEval *with replay enabled and simulated idle windows* should improve on the knowledge-update category. Measure.
- Differentiator benchmark: on a synthetic conversation with contradictions over time, assert the old-fact is updated-not-duplicated — the opposite of Mem0 v3 ADD-only failure mode (#4956).

**Effort.** **M-L** (~3-4 weeks).

**Risk / cost.** LLM cost scales with replay frequency. Mitigations: cap `ripple_batch_size`; use `gpt-4o-mini` by default; off by default in v0.4.0, opt-in in v0.5.0 once benchmarks validate. High-risk item — if replay degrades retrieval (over-specific consolidation), kill switch is the config flag.

---

### H2-D3 — Prediction-error-gated reconsolidation

**Problem.** `ReconsolidationPolicy` uses a heuristic trigger (`retrieval_count ≥ 3` + `new_context > 1.5× content_length`) and naïve string-append merge (Phase 0 §8). Cognitively, reconsolidation is **prediction-error-gated** (Phase 2 §7, Sevenster et al. 2013). Phase 5 §6 second-tier gap.

**Cognitive grounding.** Nader/Schafe/LeDoux (2000) reconsolidation; Sevenster/Beckers/Kindt (2013) prediction-error gate.

**Prior art.** Mem0's paper write-schema (add/update/delete) at first-write (Phase 1 §6) — we apply it at reconsolidation time instead. Generative Agents reflection pattern (Phase 1 §2) for the question-then-answer structure.

**Proposed API.**
```python
# neuromem/core/policies/reconsolidation.py  extension
class ReconsolidationPolicy:
    def detect_prediction_error(
        self, memory: MemoryItem, new_observation_embedding: list[float]
    ) -> float:
        """Return cosine-distance between stored content embedding and the
        new observation context. High distance = prediction error."""

    def arbitrate_update(
        self, memory: MemoryItem, new_context: str, llm_model: str
    ) -> Literal["add", "update", "no_op", "contradict"]:
        """LLM-arbitrated decision. Runs only when prediction_error > threshold."""
```
```yaml
# neuromem.yaml
reconsolidation:
  prediction_error_threshold: 0.3
  arbitration_llm: gpt-4o-mini
  cache_dir: ~/.cache/neuromem/reconsolidation
```

**Data-model delta.** `MemoryItem.metadata["reconsolidation_trace"]: list[{timestamp, decision, error_score}]` for auditability.

**LangGraph integration.** Transparent.

**Test plan.**
- Unit: ingest "I work at A"; ingest "I work at B" later; assert the arbitrate_update returns `contradict` or `update`, and that `ConflictResolver` is triggered to resolve.
- Benchmark: LongMemEval's knowledge-update category. **Success criterion: ≥ +2 pts vs v0.3.2.**
- Ablation: prediction_error_threshold sweep.

**Effort.** **M** (~2 weeks).

**Risk / cost.** LLM call per retrieval where prediction error exceeds threshold. Mitigations: threshold conservatively high (0.3); cache arbitration decisions by (memory_id, new_content_hash); gate behind config flag.

---

### H2-D4 — Working-memory / session unification + `ContextBudgetPlanner`

**Problem.** `SessionMemory` (RAM deque) and `brain.prefrontal.WorkingMemoryBuffer` both claim the "working memory" role (Phase 0 §4). Neither is wired into `RetrievalEngine.score` or context assembly. The existing `ContextManager` L0-L3 is orthogonal. Phase 2 §16.2 proposal.

**Cognitive grounding.** Baddeley multi-component model (Phase 2 §8). Cowan (2001) embedded-processes model — "working memory is long-term memory in the focus of attention."

**Prior art.** Phase 2 §8 maps the components. MemPalace L0-L3 (Phase 1 §14) inspired NeuroMem's `ContextManager`.

**Proposed API.**
```python
# neuromem/core/context_planner.py  NEW
@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int
    working_memory_weight: float = 0.3
    essential_weight: float = 0.2
    retrieved_weight: float = 0.5

class ContextBudgetPlanner:
    """Cowan/Baddeley-inspired allocator.

    Given a query, current WM slots, L0-L3 layered context, and a token budget,
    decides *which* memories from *which* layer populate the LLM context, in
    what proportion, under the budget cap. Replaces ContextManager.load() and
    get_working_memory() as user-facing APIs.
    """
    def plan(
        self,
        query: str,
        budget: ContextBudget,
    ) -> PlannedContext: ...

@dataclass(frozen=True)
class PlannedContext:
    text: str
    token_estimate: int
    contributions: dict[str, list[MemoryItem]]  # "wm" | "l0" | "l1" | "l2" | "l3" | "retrieved"
```

**Data-model delta.** None; composes existing components.

**LangGraph integration.** `NeuroMemStore.asearch` can optionally return a `PlannedContext` when called with a new `return_planned_context=True` kwarg.

**Test plan.**
- Unit: budget=500 tokens, 10 retrieved items at 200 tokens each → planner selects 1 WM + 1 L1 + 1 retrieved.
- Behavioural: working-memory items that scored higher than retrieved-k+1 are included; WM never silently dropped when attention-gated.
- Benchmark: run existing suite with `ContextBudgetPlanner` in the retrieval path. **Success criterion: no regression**.

**Effort.** **M** (~2-3 weeks).

**Risk / cost.** Potential regression — this is a retrieval-path touch. Mitigations: ship behind `retrieval.context_planner.enabled`; default off for v0.4.0.

---

### H2-D5 — Sample-top-K community summaries (GraphRAG, async)

**Problem.** `MemoryGraph.get_clusters` returns connected components but no summary per cluster (Phase 0 §11). GraphRAG-style community summaries answer query-focused-summarisation queries that chunk-level retrieval cannot ("what are my recurring themes?"). Must be *async* and *sample-top-K* from day one per Phase 3 §16.1.2 Graphiti lessons.

**Cognitive grounding.** Schema theory (Phase 2 §9) — communities ≈ schemas; summaries are the gist-extraction step.

**Prior art.** GraphRAG (arXiv 2404.16130, Phase 4 §16.3.1). Graphiti bugs #1400 / #1401 (Phase 3 §16.1.2) define what *not* to do.

**Proposed API.**
```yaml
# neuromem.yaml
brain:
  community_summaries:
    enabled: false
    sample_top_k: 10        # per community, not all members
    refresh_interval_hours: 24
    summary_model: gpt-4o-mini
```
```python
# neuromem/core/workers/community_worker.py  NEW
class CommunityWorker(BaseWorker):
    """Periodic community detection + sampled summarisation.

    - Runs Leiden (async) on the current graph.
    - For each community, samples top-K members by in-community degree.
    - LLM-summarises the sample.
    - Stores per-community summary on ``MemoryGraph.community_summaries[community_id]``.
    """
```

**Data-model delta.** New table / field `community_summaries(community_id TEXT PRIMARY KEY, summary TEXT, member_count INT, sampled_member_ids TEXT[], generated_at TIMESTAMPTZ)`.

**LangGraph integration.** Transparent.

**Test plan.**
- Unit: 3-community synthetic graph; assert 3 summaries produced; assert sampling respects top-K.
- Scaling: 1000-node graph; assert LLM call count ≤ `num_communities * sample_top_k`, not `total_nodes`.
- Behavioural: summary-style query ("what are my main topics?") routes to community summaries vs chunk-level retrieval; compare.

**Effort.** **L** (~4 weeks).

**Risk / cost.** Graphiti's exact cost-scaling bug (#1401) if we don't sample. Mitigations: sample-top-K is the *default*, not an option; async LPA form per Graphiti #1400 lesson; opt-in config flag; never in hot-path retrieve, only via explicit summary queries.

---

### H2-D6 — Mem0-parity migration doc + benchmark

**Problem.** Mem0 v3 OSS has documented correctness issues (Phase 3 §16.1.1). NeuroMem's existing conflict resolver + graph `contradicts` + `deprecated=True` already solves the #4956 stale-fact problem. Users don't know.

**Cognitive grounding.** Phase 2 §7 reconsolidation.

**Prior art.** Mem0 #4956 reproduction scenario (employer A → employer B). Phase 5 §5 Gap 2.

**Proposed API.** Documentation + one benchmark script `benchmarks/runners/mem0_migration_runner.py` that reproduces #4956's scenario on both NeuroMem and Mem0 v3 OSS and reports recall-of-correct-current-fact.

**Data-model delta.** None.

**LangGraph integration.** None.

**Test plan.** The benchmark itself.

**Effort.** **S** (~3-5 days, pure doc + script).

**Risk / cost.** Low. Mitigations: none needed.

---

### H2 total estimate

**~12 engineer-weeks** (~3 months) for 6 items, with H1-R3 (persistent graph) possibly spilling into here:
- D1 PPR (~2w)
- D2 replay scheduler (~3-4w)
- D3 prediction-error reconsolidation (~2w)
- D4 context budget planner (~2-3w)
- D5 community summaries (~4w)
- D6 Mem0-migration doc (~1w)

Ordering priority: D1 → D3 → D6 → D2 → D4 → D5. D1 closes LongMemEval multi-session gap (the one "honest open item" in the v0.3.2 README). D3 precedes D2 because D2's update-in-place path relies on D3's LLM arbitration.

---

## H3 — Research bets (3-6 months)

### H3-B1 — RAPTOR collapsed-tree on `VerbatimStore`

**Problem.** Chunk-level retrieval cannot answer queries about cross-document themes or corpus-level summaries. `daily_summary` / `weekly_digest` are time-driven, not content-driven (Phase 4 §16.3.9).

**Cognitive grounding.** Schema hierarchy — schemas contain sub-schemas (Phase 2 §9).

**Prior art.** RAPTOR, arXiv 2401.18059 (Phase 4 §16.3.9). Clustering: GMM over UMAP-reduced embeddings.

**Proposed API.**
```yaml
# neuromem.yaml
verbatim:
  raptor:
    enabled: false
    levels: 3
    clustering: gmm_umap    # gmm_umap | kmeans
    summary_model: gpt-4o-mini
```
```python
# neuromem/core/raptor.py  NEW
class RAPTORIndex:
    def build(self, chunks: list[MemoryItem]) -> None: ...
    def retrieve_collapsed(self, query_embedding, k: int) -> list[MemoryItem]: ...
```

**Data-model delta.** Tree nodes stored as `MemoryItem` with `metadata["raptor_level"]: int` and `metadata["raptor_children"]: list[str]`.

**LangGraph integration.** Transparent.

**Test plan.**
- Unit on a 100-chunk synthetic corpus across 3 clusters; assert level-1 summaries contain cluster-specific vocabulary.
- Benchmark: QASPER or NarrativeQA subset; compare to chunk-level retrieval.

**Effort.** **M-L** (~3-4 weeks).

**Risk / cost.** Index-build cost is `O(n log n)` LLM calls. Mitigations: off by default; cache tree across sessions; rebuild only on significant corpus growth.

---

### H3-B2 — Should-I-retrieve-at-all gate (Self-RAG-ish)

**Problem.** NeuroMem retrieves on every `retrieve()` call, even for pure chitchat ("hi", "thanks"). Token waste.

**Cognitive grounding.** Engineering optimisation.

**Prior art.** Self-RAG (arXiv 2310.11511, Phase 4 §16.3.3). The reflection-token approach is too heavy — we want the *gate* without the fine-tuning.

**Proposed API.**
```python
# neuromem/core/retrieval_gate.py  NEW
class RetrievalGate:
    """Classify whether a query needs memory retrieval."""
    def should_retrieve(self, query: str) -> bool: ...
```

Default: classifier over query embedding with a small MLP trained on NeuroMem's own benchmark queries. Fallback to "retrieve always" when classifier is unavailable.

**Data-model delta.** None.

**LangGraph integration.** Transparent.

**Test plan.** Benchmark: token-cost reduction on a chitchat-heavy synthetic conversation; zero regression on retrieval-required queries.

**Effort.** **S-M** (~2 weeks).

**Risk / cost.** False negatives (gate says "don't retrieve" when it should) hurt worse than false positives. Mitigations: high-recall threshold bias; off by default.

---

### H3-B3 — Multimodal `observe_multimodal` for real

**Problem.** `observe_multimodal` is a text-only stub (Phase 0 §15). Multimodal encoders exist but are not wired.

**Cognitive grounding.** Baddeley (2000) visuospatial sketchpad + phonological loop → modality-specific working-memory buffers (Phase 2 §8).

**Prior art.** TribeV2 analysis in project memory `project_tribev2_analysis.md`. LiveKit integration (Phase 0 §15).

**Proposed API.**
```python
def observe_multimodal(
    self,
    text: str | None = None,
    audio_bytes: bytes | None = None,
    video_frames: list[np.ndarray] | None = None,
    assistant_output: str = "",
    source: str = "text",
) -> None: ...
```
Backend: Whisper for audio → text + audio embedding; DINOv2 for video frames → embedding per frame. Late-fusion router already in `multimodal/fusion/`.

**Data-model delta.** `MemoryItem.metadata["modality"]` and `embedding_metadata.modality_dimensions`.

**LangGraph integration.** Transparent.

**Test plan.** Unit with canned audio/video fixtures. Benchmark: synthetic multimodal QA test.

**Effort.** **L** (~4-6 weeks). Highest H3 effort because it touches multi-arch Docker (torch/whisper/ffmpeg) and benchmark harness.

**Risk / cost.** Dependency weight. Mitigations: gated behind `neuromem-sdk[multimodal]` extra.

---

### H3-B4 — RIF / interference-theory forgetting (research spike)

**Problem.** Phase 2 §6 prediction: retrieving memory A in category C should temporarily suppress retrievability of other C-memories (Anderson, Bjork, Bjork 1994). Field has never implemented this; unclear if it helps on real benchmarks.

**Cognitive grounding.** Phase 2 §6.

**Prior art.** None in AI-memory SDKs.

**Proposed API.** Experimental; likely `retrieval.rif.enabled: bool` with a decay-of-related-memories mechanism.

**Effort.** **L** (~3-4 weeks). **Publishable negative result is fine.**

**Risk / cost.** May hurt benchmarks. Mitigations: heavy A/B testing; ship only if measurable win.

---

### H3-B5 — Stable 1.0 release with deprecation policy

**Problem.** NeuroMem is 0.3.2. Mem0 v3 migration trauma (#4955) shows the cost of breaking APIs without deprecation. Phase 5 §6.

**Cognitive grounding.** Process, not cognition.

**Prior art.** Semantic versioning. Letta's disciplined release cadence (v0.16.x patch releases, no breaking changes at patch level).

**Proposed API.** No code. This is:
- A `DEPRECATION_POLICY.md` with a minimum of 2 minor versions between deprecation warning and removal.
- Version floor: require Python 3.10+ in v1.0 (drops 3.9).
- Freeze `NeuroMem` facade surface except for additive changes.
- Release v1.0 once H1 + H2-D1 + H2-D3 benchmarks stabilise.

**Effort.** **S** (~1 week of mostly docs and CI).

**Risk / cost.** Low. Mitigations: 1.0 only when benchmarks cleared.

---

## Cross-horizon dependencies

```
H1-R1 NeuroMemStore ────────────► H2-D4 ContextBudgetPlanner (D4 returns PlannedContext from asearch)
H1-R3 Persistent graph ─────────► H2-D1 PPR (PPR runs against the graph backend)
                                └► H2-D5 Community summaries (summaries persist with the graph)
H1-R5 forget() sweep ───────────► H2-D3 Reconsolidation (shared sweep surface)
H1-R9 bug debts ────────────────► H2-D2 Replay scheduler (days_threshold fix + new scheduler)
H2-D3 Reconsolidation ──────────► H2-D2 Replay (D2's update-in-place uses D3's LLM arbitration)
H2-D1 PPR + H2-D5 communities ──► H3-B1 RAPTOR (H3 composes all three indexing paths)
```

The critical path is **H1-R3 (persistent graph) → H2-D1 (PPR) → H2-D5 (communities) → H3-B1 (RAPTOR)**. Persistent graph cannot slip indefinitely or three H2+ items stall.

---

## Benchmarks as the merge gate

Every item lands behind two bars:
1. **Regression gate** — MemBench R@5 ≥ 97.0%, LongMemEval R@5 ≥ 98.0%, ConvoMem R@5 ≥ 81.3% (v0.3.2 baselines).
2. **Item-specific win bar** — named per item's "Test plan / Success criterion" above.

Items failing bar (1) do not merge; items meeting (1) but not (2) merge only with a `status: experimental` flag and off-by-default config.

---

## What this roadmap explicitly does not include

From Phase 5 §9:
- ColBERT reranker.
- True Hopfield CA3 attractor net.
- Procedural-as-implicit-skill memory.
- Titans-style surprise-triggered write (requires model-level access).
- Full async refactor of core (only async variants in adapters).

From Phase 2 §17:
- Claims of "brain-faithfulness" on items without cognitive grounding.

From Phase 3 §16.2 second-tier (deferred by mutual agreement):
- Letta LLM-mutates-own-memory pattern (L3 research bet, low priority).
- GraphRAG global / sensemaking mode (subsumed by H2-D5 + H3-B1).

---

## Release mapping

- **v0.4.0** (end of H1, ~4 weeks out): R1 + R2 + R4 + R5 + R6 + R7 + R8 + R9. R3 may spill; if so, `InProcessGraphBackend` is the default and `PostgresGraphBackend` ships in v0.4.1.
- **v0.5.0** (end of H2-D1 + H2-D3 + H2-D6, ~8 weeks out): PPR, prediction-error reconsolidation, Mem0-parity doc.
- **v0.6.0** (end of H2-D2 + H2-D4 + H2-D5, ~14 weeks out): replay scheduler, context budget planner, community summaries. This is the version where "NeuroMem ships CLS-slow consolidation" becomes a public claim.
- **v1.0.0** (H3-B5): once benchmarks from v0.6.0 hold stable. Likely 16-20 weeks out.
- **v1.x**: H3-B1 (RAPTOR), H3-B2 (retrieval gate), H3-B3 (multimodal real), H3-B4 (RIF research spike).

---

## Exit criterion for Phase 6

Every item in this document satisfies:
- **Traceable to Phase 0 §3 / §19 or Phase 5 §5 gap list.** If it isn't, it's cut (per Phase 0 §23).
- **Cited prior art** from Phase 1 (by arxiv ID) or Phase 3 (by GitHub issue) for non-engineering-catch-up items.
- **Cognitive grounding** from Phase 2 for items claiming brain-faithfulness. H1-R1/R2/R3/R4/R5/R6/R7/R8/R9 are engineering catch-up (no cognitive claim). H2-D1/D2/D3/D4/D5 all cite a Phase 2 subsection. H3-B1/B2/B3/B4 cite Phase 2 where relevant; B5 is process.
- **Concrete diff shape** — file paths, class signatures, schema changes, test plan named.
- **Measurable success criterion** — benchmark target, latency bound, or documented decision.

If any item above drifts from these five constraints during implementation, it must be re-evaluated (sic, "reassessed") before merging.
