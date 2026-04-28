# Phase 5 — Competitive Gap Analysis

*Synthesis over Phases 0-4. The feature matrix is grounded in specific file paths / arxiv IDs / open GitHub issues so every claim can be audited. Severity and effort tags are calibrated for a single engineer working part-time on this codebase.*

*Snapshot date: 2026-04-24.*

---

## 1. Scope

The comparison set is the one the mission brief names — **Mem0, Zep, Letta, LangMem, A-MEM, MemGPT** — plus **MemPalace** because NeuroMem benches against it head-to-head and **Graphiti** because it is the open graph engine used under Zep and a standalone OSS product in its own right.

The brief's severity/effort tags:
- **Severity**: **H**igh (NeuroMem loses a real user here), **M**edium (fixable with a doc change or minor feature), **L**ow (cosmetic / nomenclature).
- **Effort**: **S**mall (<1 week), **M**edium (1-4 weeks), **L**arge (>1 month).

A cell showing `✅` means NeuroMem matches or beats the named competitor on that row. `—` means N/A. `❌ {H/M/L, S/M/L}` is the gap tag.

---

## 2. The master feature matrix

Rows group by capability area. Columns are the seven comparison systems. Source for each row is cited in §3.

### 2.1 Memory-layer taxonomy

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Episodic layer | ✅ | ✅ | ✅ (episodes as first-class) | ✅ (recall block) | ✅ (via BaseStore) | ✅ (notes) | ✅ (recall) | ✅ |
| Semantic layer | ✅ | ✅ (fact extraction) | ✅ (entities/edges) | ✅ (archival) | ✅ | ✅ | ✅ (archival) | ✅ (temporal KG) |
| Procedural layer (preferences) | ✅ | partial (facts only) | partial (facts only) | ✅ (core block = persona) | partial (Prompt Optimizer) | partial | — | partial |
| Working memory as persisted layer | ❌ {M, M} — JSON sidecar only, not a `MemoryType` | — | — | ✅ (core block always in context) | — | — | ✅ (core block) | ✅ (L0 identity always loaded) |
| Verbatim store (raw chunks) | ✅ (v0.4.0, `VerbatimStore`) | — (extraction-only) | — (extraction-only) | — | — | — | — | ✅ (raw-first design) |
| RAM session / short-term | ✅ (`SessionMemory` deque) | ✅ (history) | ✅ (conversational thread) | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.2 Write policy

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add/Update/Delete write-time arbitration | partial (add always; `ReconsolidationPolicy` is heuristic) | **paper: yes; v3 OSS: ADD-only (#4956)** | ✅ (invalidation, bi-temporal) | — (LLM-driven tool calls) | partial (Memory Manager) | ✅ (dynamic linking + attribute update) | — | ✅ (temporal invalidation) |
| LLM self-mutation pattern | ❌ {L, M} | — | — | ✅ | — | — | ✅ | — |
| Link-at-write (dynamic) | ❌ {M, S} — graph only links via consolidation | partial (entity linking in v3) | ✅ | — | — | ✅ | — | ✅ |
| Content hashing / dedup | ✅ (`VerbatimStore._seen_hashes`) | partial | ✅ | — | — | — | — | ✅ |
| Conflict detection | ✅ (`ConflictResolver` + `contradicts` graph link) | **❌ in v3 OSS (#4956)** | ✅ (temporal invalidation) | — | — | — | — | ✅ |
| Prediction-error-gated reconsolidation | ❌ {M, M} — heuristic only | — | — | — | — | — | — | — |

### 2.3 Forgetting

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ebbinghaus decay | ✅ (`DecayEngine`) | — | — | — | — | — | — | — |
| Flashbulb override | ✅ | — | — | — | — | — | — | — |
| Forget-with-guarantees (Larimar-style) | ❌ {H, S} — hard delete only | — | ✅ (invalidation preserves history) | — | — | — | — | — |
| RIF / interference theory | ❌ {L, L} | — | — | — | — | — | — | — |

### 2.4 Retrieval stack

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vector search | ✅ | ✅ | ✅ | ✅ | ✅ (keyword-default) | ✅ | ✅ | ✅ |
| BM25 hybrid | ✅ (`bm25_blend`) | ✅ (v3 — EN only, #4884) | ✅ | — | ❌ | — | — | ✅ |
| Cross-encoder reranker | ✅ (ms-marco-MiniLM-L-12-v2, but **hardcoded**) | — | ✅ (Graphiti: **hardcoded OpenAI**, #1393) | — | — | — | — | ✅ |
| Reranker config section (swappable) | ❌ {H, S} | — | ❌ (#1393) | — | — | — | — | partial |
| HyDE | ✅ (user-voice, cached, per-workload) | — | — | — | — | — | — | partial |
| LLM rerank on top-5 | ✅ (opt-in) | — | — | — | — | — | — | — |
| Multi-hop query decomposition | ✅ (`retrieve_multihop`) | — | — | — | — | — | — | ✅ |
| Graph-augmented retrieval | partial (BFS only) | partial (Mem0g Neo4j) | ✅ (hybrid + graph distance) | — | — | ✅ | — | ✅ |
| Personalized PageRank | ❌ {H, M} | — | — | — | — | — | — | — |
| RAPTOR hierarchical summaries | ❌ {M, M} | — | — | — | — | — | — | — |
| GraphRAG community summaries | ❌ {M, L} | — | partial (#1401 cost issues) | — | — | — | — | partial |
| Contextual-chunk embeddings (Anthropic) | ❌ {H, S} | — | — | — | — | — | — | — |
| Non-English tokenisation | partial (stopword-only) | ❌ (#4884) | ✅ | — | — | — | — | partial |
| Per-workload retrieval recipes | ✅ (`bm25_blend`/`ce_blend` tunable) | — | — | — | — | — | — | — |

### 2.5 Consolidation

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Immediate fact-extraction | ✅ (`Consolidator`) | ✅ | — (bi-temporal invalidation replaces) | — | ✅ (Memory Manager) | ✅ | — | — |
| CLS-slow / offline replay consolidation | ❌ {H, M} — config stubs only, no consumer | — | — | — | — | — | — | — |
| Interleaving existing semantic in consolidation | ❌ {M, S} | — | — | — | — | — | — | — |
| Schema-congruence gate | ◐ (`SchemaIntegrator` exists, not wired as gate) | — | — | — | — | — | — | — |
| Scheduled offline trigger | partial (`MaintenanceWorker`, Inngest `cron`) | — | — | — | — | — | — | — |

### 2.6 Graph / temporal

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| In-process graph | ✅ | — | — | — | — | ✅ | — | — |
| Persisted graph (Neo4j/AGE/etc.) | ❌ {H, L} | ✅ (Mem0g) | ✅ (Neo4j/FalkorDB/Kuzu/Neptune) | — | — | — | — | ✅ (SQLite) |
| Bi-temporal edges (valid_from/valid_to) | ✅ (in-process) | — | ✅ (persisted) | — | — | — | — | ✅ (persisted) |
| Temporal queries (`query_as_of`, `timeline`) | ✅ (in-process) | — | ✅ | — | — | — | — | ✅ |
| Community detection | ◐ (`get_clusters` Union-Find; no summaries) | — | ✅ (Leiden, with open bugs) | — | — | — | — | — |
| Bridge-memory detection | ✅ (`get_bridge_memories`) | — | — | — | — | — | — | — |

### 2.7 Framework interop

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LangGraph `BaseStore` impl | ❌ {H, S-M} — docstring-only | partial | partial | — | ✅ (native) | — | — | — |
| LangChain integration | ✅ (Runnable + ChatMessageHistory) | ✅ | ✅ | — | ✅ | — | — | — |
| CrewAI | ✅ | — | — | — | — | — | — | — |
| AutoGen | ✅ | — | — | — | — | — | — | — |
| DSPy | ✅ | — | — | — | — | — | — | — |
| Haystack | ✅ | — | — | — | — | — | — | — |
| Semantic Kernel | ✅ | — | — | — | — | — | — | — |
| LiteLLM | ✅ | — | — | — | — | — | — | — |
| MCP server | ✅ (12 tools, stdio+HTTP) | ✅ (OpenMemory) | ✅ (MCP v1.0.2) | — | — | — | — | ✅ |
| LiveKit bridge | ✅ | — | — | — | — | — | — | — |

### 2.8 Runtime / architecture

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Async Python (asyncio native) | ❌ {M, L} — threading | ✅ | ✅ | ✅ | ✅ | — | — | partial |
| Pydantic v2 types (core) | ❌ {L, M} — stdlib dataclass | ✅ | ✅ | ✅ | ✅ | — | — | — |
| Priority task scheduler (5-queue) | ✅ | — | — | — | — | — | — | — |
| Durable workflows (Inngest) | ✅ (optional) | — | — | — | — | — | — | — |
| Multi-backend vector store | ✅ (mem / pg / qdrant / sqlite) | ✅ | partial (graph-first) | ✅ (pg) | ✅ | — | ✅ (pg/sqlite) | ✅ (sqlite-first) |
| Cloud Run / Docker manifests | ❌ {M, S} — not in repo | ❌ (#4945) | ✅ (Zep Cloud image) | ✅ (compose.yaml) | — | — | — | — |
| Python version support | 3.9+ (tested 3.9–3.12) | 3.10+ | 3.10+ | 3.10+ | 3.10+ | — | 3.10+ | 3.10+ |
| OSS license | MIT | Apache-2.0 | Apache-2.0 | Apache-2.0 | MIT | ? | Apache-2.0 (via Letta) | ? |

### 2.9 Brain / cognitive

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pattern separation (DG-like) | ✅ (Achlioptas sparse RP) | — | — | — | — | — | — | — |
| Pattern completion (CA3 nominal) | ◐ (re-weighting, not Hopfield) | — | — | — | — | — | — | — |
| CA1 value-based gating | ✅ | — | — | — | — | — | — | — |
| Working memory Cowan-4 | ✅ (`WorkingMemoryBuffer`) | — | — | — | — | — | — | — |
| Amygdala / flashbulb tagging | ✅ (`EmotionalTagger`) | — | — | — | — | — | — | — |
| Basal ganglia TD(0) | ✅ (`TDLearner`) | — | — | — | — | — | — | — |
| Schema integration | ✅ (`SchemaIntegrator`) | — | — | — | — | — | — | — |
| Replay / sleep consolidation | ❌ {H, M} | — | — | — | — | — | — | — |

### 2.10 Developer ergonomics

| Capability | NeuroMem | Mem0 | Zep/Graphiti | Letta | LangMem | A-MEM | MemGPT | MemPalace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `explain(memory_id)` retrieval attribution | ✅ | — | — | — | — | — | — | — |
| Structured query syntax | ✅ (`type:`, `tag:`, `after:`, `sentiment:`, `intent:`, `"phrase"`) | — | — | — | — | — | — | — |
| Daily/weekly temporal summaries | ✅ | — | — | — | — | — | — | — |
| L0-L3 layered context | ✅ (`ContextManager`) | — | — | — | — | — | — | ✅ (the inventor of this idea) |
| YAML config | ✅ | partial | ✅ | — | — | — | — | ✅ |
| Provider-tagged exceptions | ❌ {L, S} | — | — | ❌ (#3310) | — | — | — | — |
| Stable 1.0 with deprecation policy | ❌ {M, S} — currently 0.3.x | ❌ (#4955 v3 breakage) | ✅ (v0.28.2, managed Zep Cloud) | ✅ (v0.16.7) | ❌ (pre-release) | — | ✅ | — |

### 2.11 Benchmarks (head-to-head numbers)

| Benchmark | NeuroMem v0.3.2 | Mem0 | Zep | MemPalace | Others |
| --- | --- | --- | --- | --- | --- |
| **MemBench R@5** (330 items) | **97.0%** (verbatim-only) | — | — | 87.9% | — |
| **LongMemEval R@5** (100 items) | **98.0%** | 93.4% (vendor) | +18.5% vs MemGPT (vendor) | 94.0% (MemPalace-reported) / 96.6% (viral) | — |
| **ConvoMem R@5** (150 items) | **81.3%** | — | — | 80.7% | — |
| **LoCoMo F1** (v0.2.0 ref) | 39.4 | 91.6 v3 (vendor); 30.6 older reimpl (benchmarks/) | — | — | LangMem 32.7 (benchmarks/) |
| **Deep Memory Retrieval (DMR)** | — | — | 94.8% | — | MemGPT 93.4% |

**Honest reading.** NeuroMem beats MemPalace head-to-head on all three benchmarks it publishes for. Mem0's published LoCoMo number (91.6) is *from its own harness* using the v3 hybrid pipeline and LLM-judge metric; NeuroMem's 39.4 is on Categories 1+4 using reference F1. These are not directly comparable — Phase 6 should either rerun Mem0 under NeuroMem's harness or vice-versa before claiming leadership on LoCoMo.

---

## 3. Row-source citations

Each numbered row below names the authoritative source. Rows not cited here are derived from files under `neuromem/` and are self-evident on re-read.

1. `MemoryType.WORKING` enum exists without a persisted layer → Phase 0 §4.
2. `NeuroMemStore` BaseStore docstring present, class absent → Phase 0 §13 table; verified grep 2026-04-24.
3. Mem0 v3 ADD-only → Mem0 issue #4956, 2026-04-24 (Phase 3 §16.1.1).
4. Mem0 BM25 hardcoded English → Mem0 issue #4884, 2026-04 (Phase 3 §16.1.1).
5. Graphiti hardcoded OpenAI reranker → Graphiti issue #1393, 2026-04-10 (Phase 3 §16.1.2).
6. Graphiti `build_communities` O(N) LLM cost → Graphiti issue #1401, 2026-04-13 (Phase 3 §16.1.2).
7. LangMem persistence confusion / bypass pattern → LangMem issue #154, 2026-04-07 (Phase 3 §16.1.3).
8. LangGraph `InMemoryStore.put()` overwrites `created_at` → LangGraph issue #7411 (Phase 3 §16.1.4).
9. LangGraph async-durability memory leak → LangGraph issue #7094 (Phase 3 §16.1.4).
10. Letta provider-tagged errors gap → Letta issue #3310 (Phase 3 §16.1.5).
11. HippoRAG PPR mechanics → arXiv 2405.14831 + §16.3.8.
12. Contextual-chunk recipe → Anthropic 2024-09-19 + §16.3.7.
13. RULER effective-context findings → arXiv 2404.06654 + §16.3.5.
14. Generative-Agents retrieval-score formula → arXiv 2304.03442 + §2 of Phase 1.
15. CLS-slow consolidation absence across all systems → Phase 1 §16 cross-system matrix.
16. Benchmark numbers — NeuroMem from `README.md`; MemPalace from benchmarks/ + third-party audits; Mem0 from `mem0ai/mem0` README vendor claims.

---

## 4. Where NeuroMem already wins

The gap list is heavier than the wins list only because gaps drive a roadmap. The wins are real and should be *preserved* by Phase 6:

1. **Retrieval-stack depth.** Bi-encoder + BM25 + cross-encoder + HyDE + LLM rerank + per-workload blends + multi-hop decomposition + keyword fallback + verbatim-only path. No other system in the set matches this stack out-of-the-box. This is *why* benchmarks beat MemPalace.
2. **Brain-faithful optional layer.** Pattern separation, CA1 gating, working memory, flashbulb, TD learning, schema integration — optional (`brain.enabled`), try/except-guarded, persisted via JSON sidecar. Nobody else has this.
3. **8 framework adapters + MCP server** shipped and individually tested.
4. **`explain(memory_id)`** retrieval-attribution debug API — no other system in the set surfaces this.
5. **Structured query syntax** with `type:`, `tag:`, date ranges, quoted phrases.
6. **`ConflictResolver` + `contradicts` graph link + `deprecated=True` metadata** is already better than Mem0 v3 OSS, which has an active open issue (#4956) about stale-fact accumulation.
7. **Verbatim-only deterministic retrieval path** — the MemBench-beating config is a deliberate design, not a hack.
8. **Priority task scheduler + Inngest workflows** — production-grade async orchestration for consolidation/decay/optimisation.
9. **Ebbinghaus decay + flashbulb override + reinforcement-adjusted curves** — the only decay implementation in the comparison set.
10. **`extract_entities` inline at `observe()`** with <1ms claim — most other systems do entity extraction out-of-band via LLM.

**Rule for Phase 6:** do not sacrifice these to chase a gap. Any roadmap item that measurably degrades benchmark R@5 is out.

---

## 5. Ranked top-10 gap list (Phase 6 input)

Gaps scored by `severity × (1/effort)` and cross-checked against §16.2's wedge list (where actual user complaints exist). In rank order:

### Gap 1 — `NeuroMemStore(BaseStore)` for LangGraph
**Severity H, effort S-M.**
Docstring-only in `adapters/langgraph.py`. LangMem users actively bypass tools (LangMem #154) because default retrieval is keyword-only; NeuroMem's retrieval stack is the answer they're rebuilding by hand. Biggest single distribution win.
**Target:** new `NeuroMemStore` class implementing `langchain_core.stores.BaseStore` + `asearch` + `aput` + `aget` + `adelete`. Integration test against pinned `langgraph==1.0.x`. Packaged in `neuromem-sdk[langgraph]` extra.

### Gap 2 — Contextual-chunk embeddings before ingestion
**Severity H, effort S.**
Anthropic's recipe documents −35% relative failure rate reduction from this step alone. Plugs into `VerbatimStore.store` with one cached LLM call per chunk at ~$1/M tokens. Phase-4 §16.3.7 has the shape.
**Target:** opt-in config `verbatim.contextual_prepend.enabled` + cache-aware prompt. Benchmark on LongMemEval.

### Gap 3 — Persistent graph (Postgres/Neo4j/KuzuDB)
**Severity H, effort L.**
In-process dict graph dies on every restart, blocks multi-worker deployments, prevents any production SLA. Graphiti's Neo4j+FalkorDB+Kuzu+Neptune support is the reference — a `GraphBackend` Protocol alongside `MemoryBackend` is the clean shape. Schema is already defined by `MemoryLink` dataclass.
**Target:** `GraphBackend` Protocol, `InProcessGraphBackend` (current behaviour), `PostgresGraphBackend` (AGE or JSONB tables). `MemoryGraph` becomes a thin orchestrator over the backend.

### Gap 4 — Personalized PageRank on entity graph
**Severity H, effort M.**
HippoRAG's core mechanism. `_graph_retrieve` currently uses BFS; replace with NumPy sparse PPR. Per-user graphs are small (<100k nodes), so power-method is microseconds. Blends into existing reranker score.
**Target:** `_graph_retrieve` accepts mode `bfs|ppr`; `ppr` convergence caps iterations at 30; blend weight configurable. Measure on multi-hop sub-set of LongMemEval.

### Gap 5 — Replay / CLS-slow consolidation scheduler
**Severity H, effort M.**
Config stubs (`brain.hippocampus.ripple_interval_minutes`, `ripple_batch_size`) exist; no consumer. CLS-slow consolidation is absent from *every* Phase-1 system, so this is a differentiator, not catch-up. Sample (recent episodic ∪ old semantic) → interleaved LLM fact-extraction → update semantic in place.
**Target:** new `core/workers/replay_worker.py` on `MaintenanceWorker` base; triggers on `ripple_interval_minutes`; samples N episodic + M semantic; runs interleaved extraction; updates not-always-adds.

### Gap 6 — Reranker config section (swappable)
**Severity H, effort S.**
Graphiti #1393 documents the exact failure mode when reranker is hardcoded to one provider. NeuroMem's `cross_encoder_reranker` uses a single default model. Expose via `retrieval.reranker.{provider, model}`.
**Target:** config section + provider dispatch (sentence-transformers, Cohere, BGE, OpenAI rerank-N, Gemini reranker).

### Gap 7 — `forget()` sweep across all surfaces
**Severity H, effort S.**
Current `NeuroMem.forget(memory_id)` hard-deletes on episodic/semantic/procedural and removes graph links. It does NOT sweep: verbatim chunks sharing `cognitive_id`, `_entity_index` entries, brain state's sparse codes, `WorkingMemoryBuffer` slots, `RetrievalStats` cache, `ReconsolidationPolicy` state, auto-tagger outputs. Privacy/compliance table stakes.
**Target:** `forget(memory_id, scope="all")` + a verification pass that greps all surfaces and returns `{cleaned: [...], residual: [...]}`.

### Gap 8 — Docker + Cloud Run deployment manifests
**Severity M, effort S.**
Every enterprise user's first question. Currently not in repo. Dockerfile + compose.yaml + Cloud Run manifest + env-var documentation.
**Target:** `deploy/` directory with Dockerfile, docker-compose for dev, Cloud Run service.yaml, and a README section.

### Gap 9 — Provider-tagged exceptions
**Severity M, effort S.**
Letta #3310 shows the specific failure: rate-limit errors from non-OpenAI providers get mislabeled "Rate limited by OpenAI". NeuroMem's embedding / LLM-rerank / HyDE paths all call providers without wrapping. Wrap with a `ProviderError(provider, upstream)` exception family.
**Target:** `utils/providers.py` with a decorator that tags exceptions by provider name; applied at every provider-call site.

### Gap 10 — Tokenizer injection for non-English languages
**Severity M, effort S.**
Mem0 #4884 is the cautionary tale. NeuroMem's `BM25Scorer` uses whitespace tokenisation + English stopwords; `extract_entities` uses capitalization heuristics that fail on CJK/Arabic/Thai/Devanagari. Expose `tokenizer_fn` and `entity_extractor_fn` injection points.
**Target:** `BM25Scorer(tokenizer_fn=...)` + `graph.extract_entities(fn=...)`; ship a `tokenizers/` module with spaCy multi-language + character-n-gram fallback.

---

## 6. Second-tier gaps (not top-10 but on the radar)

Phase 6 should not promise all of these; they are candidates for future horizons.

- **Prediction-error-gated reconsolidation** — cognitive grounding from Phase 2 §7 is solid; current `ReconsolidationPolicy` is a heuristic. Medium severity, medium effort. Overlaps with Gap 1 Mem0-migration doc (positioning NeuroMem's existing conflict resolver as the Mem0 answer).
- **Async Python refactor** — full asyncio. High effort (L). Unlocks co-deployment with all the async-native frameworks, but the threading approach currently works. Defer until a concrete user asks.
- **Pydantic v2 core types** — clean but breaking. Medium effort (M). Pair with Gap 1 since `BaseStore` expects Pydantic types anyway.
- **Schema-congruence gate in consolidation** — cognitive grounding from Phase 2 §9 (Tse et al. 2007). Medium severity. Depends on Gap 5.
- **RAPTOR collapsed-tree on VerbatimStore** — Phase 4 §16.3.9. H2 horizon. Overlaps with `daily_summary`/`weekly_digest`; generalises content-themes queries.
- **GraphRAG community summaries** — Phase 4 §16.3.1. H2. Must be sample-top-K and async from day one (§16.2 constraint derived from Graphiti's scaling bugs).
- **Should-I-retrieve-at-all gate** (Self-RAG-ish) — Phase 4 §16.3.3. H2. Saves tokens on chitchat turns.
- **Stable 1.0 release with deprecation policy** — process gap. Mem0 #4955 (v3 breakage) is the warning shot. NeuroMem is currently 0.3.2.
- **Provider-swappable everything** — embedder + LLM + reranker + tokenizer all via config dispatch. Partially covered by Gaps 6 + 10.
- **Letta-style LLM-mutates-own-memory pattern** — a tool-surfaced memory-write API for the agent to self-manage. L3 research bet, not near-term.

---

## 7. Gap × cognitive-grounding cross-reference

Each top-10 gap must name a Phase-2 subsection (or explicitly "engineering catch-up"):

| Gap | Cognitive grounding | Phase-2 section |
| --- | --- | --- |
| 1 `NeuroMemStore(BaseStore)` | Engineering catch-up — no cognitive claim | — |
| 2 Contextual-chunk embeddings | Engineering catch-up (Anthropic recipe) | — (Phase 4) |
| 3 Persistent graph | Engineering catch-up | — |
| 4 Personalized PageRank | Hippocampal indexing + spreading activation over schema graph | §3, §9 |
| 5 Replay / CLS-slow consolidation | Complementary Learning Systems + sharp-wave ripple replay | §2, §5 |
| 6 Swappable reranker config | Engineering catch-up | — |
| 7 `forget()` sweep across surfaces | Larimar one-shot forgetting API | §6 Phase-1 ref + Phase-2 §6 |
| 8 Docker / Cloud Run | Engineering catch-up | — |
| 9 Provider-tagged exceptions | Engineering catch-up | — |
| 10 Tokenizer injection | Engineering catch-up (but is a *fairness* concern for non-English speakers — treat as table stakes) | — |

Gaps 4, 5, 7 carry cognitive grounding — these are the headline "brain-faithful" Phase-6 items. The rest are engineering catch-up, which is fine — not everything needs a neuroscience paper behind it.

---

## 8. Gap × user-pain cross-reference

Each gap either resolves a documented user complaint or is preemptive:

| Gap | Resolves (issue) | Or: preemptive |
| --- | --- | --- |
| 1 | LangMem #154 (users bypass to roll their own) | — |
| 2 | — | Anthropic recipe is public; users will ask |
| 3 | LangGraph #7094 (store scalability under load) | — |
| 4 | — | HippoRAG 6-13× speed claim drives adoption |
| 5 | — | Differentiator, no existing complaint |
| 6 | Graphiti #1393 (hardcoded OpenAI reranker) | — |
| 7 | — | Enterprise compliance RFP item |
| 8 | — | Enterprise RFP item |
| 9 | Letta #3310 (mislabeled provider errors) | — |
| 10 | Mem0 #4884 (English-only BM25) | — |

6 of 10 gaps close documented pain points in competitor trackers; 4 are preemptive. This is a healthy mix — pure pain-chasing misses differentiation, pure preemption risks building the wrong thing.

---

## 9. What the gap list does NOT include

Explicit no-goes for Phase 6, from Phase 2 §17 and Phase 4:

- **ColBERT reranker.** NeuroMem's trade-off band is already covered by cross-encoder; ColBERT's storage cost makes it a bad fit for per-user memory.
- **True Hopfield / CA3 attractor implementation.** The existing cross-encoder + HyDE pipeline handles partial-cue completion pragmatically. Either rename `PatternCompleter` to drop the claim or leave alone — do not build a real attractor net.
- **"Procedural memory" as implicit skill caching.** NeuroMem's procedural layer is semantic-about-preferences. Do not build features on the premise it's Tulvingian procedural.
- **Surprise-triggered write (Titans-style).** Requires model-level access. Out of SDK scope.
- **RIF / interference-theory forgetting.** Requires category/cluster definitions at the forgetting layer; low severity; deferred.
- **Async refactor driven by nothing.** Threading works; no concrete user has asked. Refactor *only* if Gap 1 BaseStore integration forces async on the facade — in which case do the async variant in the adapter, not the core.

---

## 10. Exit criterion for Phase 5

Phase 6 must:
- Sequence the top-10 gap list into horizons (H1 / H2 / H3).
- For each roadmap item, satisfy the mission-brief §6 template: Problem, Cognitive grounding, Prior art, Proposed API (with type hints), Data-model delta, LangGraph integration, Test plan, Effort, Risk.
- Not add roadmap items outside §5 + §6 of this document unless they satisfy both exit criteria of Phases 0 and 2.
- Not remove items from §4 wins without an explicit reason.
