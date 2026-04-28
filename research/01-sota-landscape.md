# Phase 1 — SOTA Landscape for AI Memory Systems

*Primary-source survey. Every system below is identified by arxiv ID or commit SHA. Where abstract-only reads were insufficient for a field, the field is marked `⚠️ NEEDS DEEPER DIVE` rather than fabricated. Accessed 2026-04-24.*

The per-system template: **Identity → Architecture → Write policy → Consolidation → Forgetting → Retrieval → Benchmarks → Failure modes → License / production-readiness**.

---

## 0. How to read this document

- Each entry names a concrete **mechanism**. That mechanism is what Phase 6 can propose to port, subset, or beat. A system that has no mechanism we don't already ship is not a Phase-6 input — it's noted for completeness only.
- Numbers in the Benchmarks field are **as reported by the authors** unless flagged `(third-party)`. Marketing claims in GitHub READMEs are flagged `(vendor)`.
- "License / production-readiness" combines OSS license, maintenance signal (commits in last 90 days, release cadence), and whether it is in production use at a named company — not just whether a demo exists.

---

## 1. MemGPT / Letta — hierarchical virtual context

**Identity.** Packer et al., *MemGPT: Towards LLMs as Operating Systems*, arXiv **2310.08560** (v1 2023-10-12, v2 2024-02-12). OSS implementation evolved into Letta (Apache-2.0, 22.3k★, latest release v0.16.7 on 2026-03-31 per `github.com/letta-ai/letta`).

**Architecture.** LLM-as-OS analogy. Three block-memory regions — **core** (always in context, system-prompt-size persona / human blocks), **recall** (conversation history searchable), **archival** (generic KV store searchable by vector). Control flow is explicit: the model emits tool-call "interrupts" that `pg_flush`, `core_memory_replace`, `archival_memory_insert`, `conversation_search`, etc. Context is managed by the model itself, not a wrapper.

**Write policy.** Model decides. The system prompts the LLM with current core-memory contents and tool definitions; any write to recall or archival is an explicit tool call. No automatic consolidation. No dedup at the framework level — dedup is whatever the LLM decides.

**Consolidation mechanism.** None in the framework sense. Core blocks can be manually rewritten (`core_memory_replace`); summarisation is out-of-band.

**Forgetting.** Archival is effectively append-only by default. Recall ages out by context window (it's still all in Postgres / SQLite, just no longer injected).

**Retrieval.** Vector search over recall + archival, triggered by model tool call. Single-step.

**Benchmarks.** Paper reports on **Deep Memory Retrieval (DMR)** and **Multi-Session Chat (MSC)**; exact table numbers **⚠️ NEEDS DEEPER DIVE** (abstract-only read returned no concrete figures). Zep's 2025 paper reports third-party MemGPT number on DMR as **93.4%** — see §7.

**Failure modes.** Burns tokens: every memory read/write is an LLM tool-call round-trip, so wall-clock and cost scale linearly with memory operations. Model frequently under-writes when the task is retrieval-heavy. README has no "Known Issues" section; downstream issue-tracker dive deferred to Phase 3.

**License / production.** Apache-2.0. Active: 176 total releases, continuous commits. Letta Cloud is a commercial offering.

**What to port.** Block-memory *API shape* (core/recall/archival) matches NeuroMem's session/episodic/semantic coarsely, but MemGPT exposes these to the LLM directly as a *tool surface* — something NeuroMem currently does not do outside of the MCP server path. That's a Phase-6 candidate.

---

## 2. Generative Agents — importance × recency × relevance

**Identity.** Park et al. (Stanford + Google), *Generative Agents: Interactive Simulacra of Human Behavior*, arXiv **2304.03442**, UIST 2023. First submitted 2023-04-07.

**Architecture.** A single rolling **memory stream** — append-only list of natural-language observations, each with a timestamp and a computed importance score. Memories form the basis of **reflections** (higher-level inferences) and **plans** (hourly / daily schedules). No vector DB, no graph.

**Write policy.** Every observation (what the agent saw, said, or did) is appended. Importance is computed at write time via LLM prompt on a 1-10 scale — exact prompt wording **⚠️ NEEDS DEEPER DIVE** from body read; abstract confirms importance is LLM-produced but the exact scale/prompt is in §4 of the paper.

**Consolidation mechanism.** **Reflection trigger:** when the sum of importance scores of recent observations exceeds a threshold (paper says ~150), the agent produces 3 high-level questions about itself, retrieves memories for each, then generates ~5 reflections. Reflections are themselves memories and participate in retrieval. This is the closest ancestor to NeuroMem's `ConsolidationEngine` in spirit — except it is *question-driven*, not fact-extraction-driven.

**Forgetting.** None. Everything stays in the stream. Scaling beyond ~25 simulated agents × 2 days required pruning, handled manually in the paper.

**Retrieval.** Score = **α·recency + β·importance + γ·relevance** with weights described as 1.0 in the default (per common re-implementations). Recency = exponential decay (half-life in hours since last access). Relevance = cosine sim of embedding. Importance = LLM 1-10 score normalised to [0,1]. Top-N retrieved per context window.

**Benchmarks.** Not a QA benchmark paper. Paper runs a 25-agent Smallville simulation; the quantitative finding is an *interview study* where human raters scored believability of agent responses; ablations showed observation > planning > reflection in contribution order. Not comparable to LongMemEval-style numbers.

**Failure modes.** Token cost scales with reflections; long simulations need manual pruning. Importance scoring is noisy and LLM-version-dependent. Reflection questions can spiral into tautologies.

**License / production.** Research code. Widely re-implemented; production derivatives exist.

**What to port.** The three-factor retrieval score is **already partly in NeuroMem's `RetrievalEngine.score`** (similarity + salience + recency + reinforcement + confidence). The missing piece is the *access-frequency decay* term — Park et al. decay recency since *last access*, not since creation. NeuroMem's `last_accessed` is tracked via `DecayEngine.reinforce` but not fed into the retrieval-score recency term directly in the same way. Phase 6 should reconcile.

---

## 3. HippoRAG — entity-centric KG + Personalized PageRank

**Identity.** Gutiérrez et al. (OSU), *HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models*, arXiv **2405.14831**, NeurIPS 2024. Last revised 2025-01-14.

**Architecture.** Three-step pipeline: **(1)** run open information extraction on every passage → noun-phrase entity nodes and predicate edges form a graph; **(2)** at query time, LLM-extract entities from the query → use them as the **personalization vector** for Personalized PageRank over the graph; **(3)** rank passages by the PPR mass accumulated at their constituent entities.

**Write / indexing.** OpenIE extraction per passage (LLM call). Entities are canonicalised via embedding similarity of phrase strings. The graph is static after indexing; no incremental updates in the published method.

**Consolidation.** Implicit: entities that appear across many passages become high-degree nodes; PPR naturally weights them. No explicit promotion step.

**Forgetting.** None.

**Retrieval.** Query → LLM entity extraction → PPR with restart=0.5 (typical) over the graph → passage score = sum of PPR mass on its entities → top-k.

**Benchmarks.** Paper claims "up to 20% improvement" on multi-hop QA over SOTA retrievers. Exact numbers per benchmark (MuSiQue, 2WikiMultiHopQA, HotpotQA) **⚠️ NEEDS DEEPER DIVE** — abstract-only read returned only the aggregate claim plus cost: **10–30× cheaper and 6–13× faster than IRCoT** at comparable recall.

**Failure modes.** OpenIE extraction latency + cost at indexing time. Entity canonicalisation errors (co-reference, string variants) compound. PPR cost grows with graph size; paper does not publish scaling to millions of passages.

**License / production.** MIT (repo `OSU-NLP-Group/HippoRAG`). Research-grade; not a production SDK.

**What to port.** NeuroMem has an `_entity_index` and a BFS `_graph_retrieve`. It does **not** have PPR. Of everything surveyed here, **PPR-over-episodic-entities is the single most cited retrieval-quality mechanism NeuroMem is missing**. Phase 6 H2 candidate.

---

## 4. HippoRAG 2 — passage-aware continual learning

**Identity.** Gutiérrez et al., *From RAG to Memory: Non-Parametric Continual Learning for Large Language Models*, arXiv **2502.14802**, ICML 2025. Submitted 2025-02-20.

**Architecture.** Extends HippoRAG with "deeper passage integration" and "more effective online use of an LLM" (abstract language). Specific graph-construction and retrieval differences **⚠️ NEEDS DEEPER DIVE**.

**Benchmarks.** Abstract claims **7% improvement on associative-memory tasks over the SOTA embedding model**. Per-dataset numbers **⚠️ NEEDS DEEPER DIVE** across MuSiQue, 2Wiki, HotpotQA, LV-Eval, NarrativeQA, PopQA.

**Failure modes / license / production.** Same research-grade status as v1. **⚠️ NEEDS DEEPER DIVE** on the new ingestion path specifically — the "continual learning" claim is the novel bit and deserves a body read before Phase 6 locks PPR as the reference implementation.

---

## 5. A-MEM — Zettelkasten-style dynamic linking

**Identity.** Xu et al., *A-MEM: Agentic Memory for LLM Agents*, arXiv **2502.12110**, NeurIPS 2025. v1 2025-02-17, latest revision 2025-10-08 (v11 — unusually many revisions).

**Architecture.** Each memory is a **note** with structured attributes (contextual description, keywords, tags). When a new note is created, an LLM analyses historical notes, proposes relevant links, and — critically — can **update the attributes of existing notes** based on the new one. This is memory *evolution*, not just append.

**Write policy.** LLM-driven. Each observation produces a note plus proposed links plus proposed updates to existing notes. This is the most write-expensive system in this survey on a per-observation basis.

**Consolidation.** The link-proposal + attribute-update step *is* the consolidation. There is no separate scheduled pass.

**Forgetting.** Not described in the abstract. **⚠️ NEEDS DEEPER DIVE**.

**Retrieval.** **⚠️ NEEDS DEEPER DIVE** — abstract does not specify; the paper evaluates retrieval on LoCoMo-style tasks so the retrieval interface is likely k-NN-on-embeddings + link traversal.

**Benchmarks.** Tested on six foundation models; claims "superior improvement against existing SOTA baselines" on LoCoMo. Exact numbers **⚠️ NEEDS DEEPER DIVE**.

**Failure modes.** Per-write LLM cost is high. Attribute-update of existing notes means every historical note is potentially rewritten — auditability, versioning, and convergence are open questions the paper does not answer in the abstract. Eleven revisions on arXiv suggest the paper itself was unstable.

**License / production.** Research code; OSS status **⚠️ NEEDS DEEPER DIVE**.

**What to port.** The *link-proposal-at-write* pattern. NeuroMem's `MemoryGraph.add_link` is called only by consolidation (derived_from) and conflict resolution (contradicts). It never runs on a fresh observation to find `related` links to existing memories. That is a Phase-6 candidate because it's cheap to prototype on top of the existing `_entity_index`.

---

## 6. Mem0 — LLM-driven fact extraction with add/update/delete

**Identity.** Chhikara et al., *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory*, arXiv **2504.19413**, 2025-04-28. OSS repo `mem0ai/mem0` (Apache-2.0, **54k★**, latest plugin release v1.0.10 on 2026-04-23).

**Architecture.** Two variants:
- **Mem0 base**: LLM extracts salient facts from a conversation turn and emits a decision per fact — `add` / `update existing id X` / `delete id X` / `no-op`. Facts are vector-indexed.
- **Mem0g** (graph variant): same extraction, but facts populate a graph. Entities linked, relationships stored.

**Important note on write policy.** The `mem0ai/mem0` README (v1.0.10 release as of 2026-04) documents an **"April 2026 algorithm"** that moves to a **single LLM call, ADD-only** write path: "memories accumulate; nothing is overwritten." This is a material departure from the paper's add/update/delete semantics — the library and the paper now disagree. Phase 5 should note which version benchmarks are quoted against.

**Consolidation.** The extraction step is the consolidation. No separate scheduled pass.

**Forgetting.** Paper version supports `delete` decisions. April-2026 library version removes `delete`. Both rely on the LLM to be parsimonious.

**Retrieval.** Vector search over extracted facts. Entity-linked boosting in Mem0g / in the April-2026 ADD-only algorithm.

**Benchmarks.** From the OSS README (vendor claim): **LoCoMo 91.6** (prior 71.4), **LongMemEval 93.4** (prior 67.8), **BEAM-1M 64.1**, **BEAM-10M 48.6**, p50 latency 0.88–1.09 s, ~7K tokens per call. Paper (2504.19413) separately claims **26% relative improvement over OpenAI memory on LoCoMo LLM-as-a-Judge**, **91% lower p95 latency**, **>90% token-cost reduction** vs. full-context.

**Failure modes.** Extraction LLM can over- or under-write; the shift from add/update/delete to ADD-only was reportedly driven by update/delete errors (unverified — Phase 3 issue-tracker dive). Graph variant adds Neo4j operational cost.

**License / production.** Apache-2.0, 54k stars, actively maintained. Production deployments known at multiple companies (vendor-reported). One of the top two most visible systems in this survey along with Letta.

**What to port.** The **add/update/delete decision schema** is instructive. NeuroMem's `observe` always adds. Consolidation extracts facts but never updates or deletes episodic. The closest equivalent is `ReconsolidationPolicy.merge_context` — which is a string append, not an LLM-arbitrated update.

---

## 7. Zep + Graphiti — bi-temporal knowledge graph

**Identity.**
- Paper: Rasmussen et al., *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, arXiv **2501.13956**, 2025-01-20.
- OSS: `getzep/graphiti` (Apache-2.0, **25.3k★**, latest `mcp-v1.0.2` on 2026-03-11). Graphiti is the open graph engine; Zep Cloud is the commercial hosted product.

**Architecture.** A temporal knowledge graph. Primitives:
- **Episode** — the raw ingested chunk (message, document). Every derived fact traces back to an episode (provenance).
- **Entity node** — extracted by LLM with Pydantic-validated schema.
- **Edge** — a fact between two entities, with `valid_at` and `invalid_at` timestamps *and* `created_at` / `expired_at` (bi-temporal: event-time × transaction-time).

**Write policy.** On ingest, LLM extracts entities and facts from the episode. For each new fact, the system searches for contradictions; if a contradicting fact is found, its `invalid_at` is set (fact is **invalidated, not deleted**). Incremental — no batch recomputation.

**Consolidation.** None in the sense of promotion. Consolidation is replaced by *invalidation* — old facts remain, they just become inactive as-of the current time.

**Forgetting.** Same as consolidation — facts invalidate but stay for historical queries.

**Retrieval.** Hybrid — semantic embeddings + BM25 + graph traversal, reranked by **graph distance** and a cross-encoder. Sub-second latency claimed.

**Benchmarks.** Paper reports **Deep Memory Retrieval (DMR) 94.8% vs MemGPT 93.4%**, and on LongMemEval **"up to 18.5% accuracy improvement"** with **"90% latency reduction"** vs. baselines.

**Failure modes (from Graphiti README).**
- Requires an LLM with structured-output support (OpenAI, Gemini). Others "risk incorrect output schemas and ingestion failures."
- Default `SEMAPHORE_LIMIT=10` — rate-limit-prone without tuning.
- OSS performance SLAs are not guaranteed; Zep Cloud is the production answer.

**License / production.** Apache-2.0, 25.3k stars, commercial Zep Cloud offering. Neo4j / FalkorDB / Kuzu / Neptune backends.

**What to port.** The bi-temporal edge model. NeuroMem **has this already** at the `MemoryLink` level (`valid_from` / `valid_to`, `invalidate`, `query_as_of`, `timeline`) — but only in-process. Graphiti persists it in Neo4j/Kuzu. That's the gap: not the model, the *persistence*. Phase 6 should propose a persistence backend for the graph, and Graphiti's schema is a concrete reference.

---

## 8. Titans — neural long-term memory at test time

**Identity.** Behrouz, Zhong, Mirrokni (Google), *Titans: Learning to Memorize at Test Time*, arXiv **2501.00663**, submitted 2024-12-31.

**Architecture.** Hybrid attention + a **neural long-term memory module** with three variants:
- **Memory as Context (MAC)** — memory output is concatenated to the attention context.
- **Memory as Gate (MAG)** — memory and attention each run in parallel; a learned gate blends.
- **Memory as Layer (MAL)** — memory acts as a standalone layer in the stack.

**Write policy.** **Surprise-based update rule** — token sequences that deviate from the model's expectation trigger a parameter update inside the memory module *at inference time*. No backprop through training — it's an associative memory read/write.

**Consolidation.** The surprise-triggered update *is* the consolidation. Persistent memory is updated during inference; attention is the short-term buffer.

**Forgetting.** Inherent to the update rule: old associations are overwritten as new surprising tokens displace them. Exact retention curve **⚠️ NEEDS DEEPER DIVE**.

**Retrieval.** Associative memory read keyed on the current hidden state, per-layer.

**Benchmarks.** Language modeling, needle-in-haystack at >2M context, BABILong, commonsense, genomics, time series. Abstract claims outperforming Transformers and linear-recurrent baselines; specific numbers **⚠️ NEEDS DEEPER DIVE**. Crucially the paper claims retention of needle accuracy at **>2M context** — past where retrieval-augmented approaches usually dominate.

**Failure modes.** Memory capacity vs. compute trade-off not explicit in abstract. Not yet implementable as an SDK layer — this is a model-architecture paper.

**License / production.** Google, no public code released at time of publication (**⚠️ NEEDS DEEPER DIVE** on 2026 status).

**What to port.** Nothing directly — Titans is a model-weight-level approach. But it's the key data-point for the "long context eats retrieval" argument: if Titans-class models ship, **retrieval-based memory may become a worse bet for in-session context**, while *cross-session* memory (what NeuroMem is primarily about) remains necessary. Include in Phase 4 long-context-vs-RAG discussion.

---

## 9. Larimar — plug-in episodic memory with one-shot edits

**Identity.** Das et al. (IBM), *Larimar: Large Language Models with Episodic Memory Control*, arXiv **2403.11901**, v1 2024-03-18 / v4 2024-08-21.

**Architecture.** A distributed episodic-memory module external to a frozen base LLM. Memory stores *scenes*; the module supports **one-shot write, one-shot read, one-shot update, one-shot forget** of individual facts without re-training.

**Write / read.** Key-based interface. Exact mechanism (read/write keys, scene encoding) **⚠️ NEEDS DEEPER DIVE**.

**Consolidation.** Not in the traditional sense. Larimar is a fact-editing layer.

**Forgetting.** **Explicit selective-forget API** — a first-class operation, with claims about information-leakage prevention (e.g., targeted forgetting of PII).

**Retrieval.** Key-addressed read on the memory tensor, outputs injected into the LLM.

**Benchmarks.** Fact-editing benchmarks (e.g., CounterFact, ZsRE). Accuracy "comparable to most competitive baselines" on sequential editing; **8–10× speed-up** over re-training methods.

**Failure modes.** **⚠️ NEEDS DEEPER DIVE**. Storage of scene representations is bounded; eviction policy not explicit in abstract.

**License / production.** Research code; OSS status **⚠️ NEEDS DEEPER DIVE**.

**What to port.** The explicit **forget-with-guarantees API**. NeuroMem's `forget(memory_id)` is a hard delete on the episodic/semantic/procedural backends — no way to verify "no residual trace" since embeddings can be indexed elsewhere. Larimar-style forgetting is a selling point for privacy/compliance. Phase 6 candidate.

---

## 10. RAPTOR — recursive hierarchical summarisation

**Identity.** Sarthi et al. (Stanford), *RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval*, arXiv **2401.18059**, 2024-01-31.

**Architecture.** Bottom-up recursive clustering + summarisation over a document corpus. Leaves = raw chunks; each internal node = an LLM-generated summary of its children. Retrieval can be **tree traversal** (top-down, pick best branch at each level) or **collapsed tree** (all nodes at all levels competing in one k-NN pool).

**Write policy.** One-shot indexing. Not incremental. Re-indexing on corpus change is a new pass.

**Consolidation.** The recursive summarisation *is* the consolidation — and it produces an explicit hierarchy (which NeuroMem does not).

**Forgetting.** N/A (static index).

**Retrieval.** Traversal or collapsed. Collapsed is usually the default and competitive.

**Benchmarks.** **+20% absolute accuracy on QuALITY with GPT-4.** NarrativeQA and QASPER numbers **⚠️ NEEDS DEEPER DIVE**.

**Failure modes.** Indexing cost is `O(corpus × log(corpus))` LLM calls; non-trivial on a corpus of thousands of docs. Summaries are lossy — exact-match queries degrade.

**License / production.** Research code, re-implementations widely available.

**What to port.** Hierarchy. NeuroMem's `ContextManager` has an L0–L3 layered-context API — but its content is *retrieved-top-K*, not a *summarisation tree over the corpus*. RAPTOR's collapsed-tree retrieval is an orthogonal index, not a replacement for chunk-level retrieval. Phase 6 H2 candidate: build RAPTOR on top of `VerbatimStore`.

---

## 11. Anthropic Contextual Retrieval — contextual chunk embeddings + BM25 + rerank

**Identity.** Anthropic blog post, 2024-09-19, `anthropic.com/news/contextual-retrieval`. Not a paper — a production recipe with open reproductions.

**Architecture.** Three-step failure-rate reduction on top of plain chunk-embeddings:
1. **Contextual chunk embedding** — prepend a 50-100 token LLM-generated context ("this chunk is from document X, section Y, discussing Z") before embedding.
2. **BM25 hybrid** — parallel BM25 index on the same contextual chunks; rank-fuse.
3. **Reranker** — retrieve top-150, rerank with Cohere Rerank, keep top-20.

**Quantitative result.**

| Stage | Failure rate | Relative reduction |
| --- | --- | --- |
| Plain chunk embeddings | 5.7% | baseline |
| + Contextual embeddings | 3.7% | −35% |
| + Contextual BM25 | 2.9% | −49% |
| + Reranking | 1.9% | **−67%** |

Documented cost: **$1.02 per million document tokens** for contextualisation, leveraging prompt caching.

**Failure modes.** Chunk boundaries dominate. Embedding-model choice matters more than most other knobs. Reranker adds latency.

**License / production.** Open recipe. Reproductions in many OSS libraries.

**What to port.** NeuroMem already has **BM25 + cross-encoder rerank**. The missing piece is the **contextual chunk prepend** before embedding. `VerbatimStore` currently chunks-then-embeds raw text. This is the cheapest Phase-6 H1 item in this survey: one LLM call per ingestion, cached by prompt-caching, plugs directly into `chunk_text` in `core/verbatim.py`. Expected delta on LongMemEval **⚠️ NEEDS MEASUREMENT** but a-priori bound: Anthropic's study estimates −35% relative failure reduction from this step alone.

---

## 12. LangMem — LangChain's native semantic/episodic/procedural framing

**Identity.** `langchain-ai/langmem` (MIT, **1.4k★**, pre-release, 45 open issues).

**Architecture.** A thin layer over LangGraph's `BaseStore`. Provides:
- `create_manage_memory_tool` / `create_search_memory_tool` — tools the agent calls to mutate/query memory.
- Memory Manager — a background agent that "extracts, consolidates, and updates" memory.
- Prompt Optimizer — refines the agent's own system prompt based on accumulated feedback (the "procedural" pillar).

**Important observation.** Contrary to what the NeuroMem README implies, LangMem's public README **does not advertise a semantic/episodic/procedural split**. The taxonomy NeuroMem ascribes to LangMem is from older LangChain blog posts. The current library positions itself as "tools + background manager over BaseStore". Phase 5 should correct the framing.

**Write policy.** Agent-tool-invoked by default; Memory Manager optional.

**Consolidation.** Memory Manager is the named mechanism, but its semantics are underspecified in the README.

**Forgetting.** Not documented in README. **⚠️ NEEDS DEEPER DIVE**.

**Retrieval.** Vector search via BaseStore.

**Benchmarks.** None claimed in README.

**Failure modes.** **⚠️ NEEDS DEEPER DIVE** from issue tracker — 45 open issues on a 1.4k-star repo is a high ratio. Phase 3.

**License / production.** MIT. Pre-release (no tagged releases as of 2026-04-24).

**What to port.** The **LangGraph `BaseStore` conformance**. This is the single most impactful interop gap in NeuroMem — Phase 0 noted the `NeuroMemStore` class is docstring-only. Porting via `BaseStore` protocol would make NeuroMem a **drop-in** for any LangGraph deployment, including Platform-hosted. Phase 6 H1.

---

## 13. Cognee — hybrid graph + vector with four-primitive API

**Identity.** `topoteretes/cognee` (Apache-2.0, **16.7k★**, latest v1.0.2 on 2026-04-22).

**Architecture.** Four core operations — **remember / recall / forget / improve** — over a hybrid of session cache + persistent knowledge graph. Multimodal ingestion. Ontology grounding is a first-class feature.

**Write policy.** `remember()` pipelines a document through add → cognify (extract) → improve. Permanent-storage mode vs. session-fast-cache mode.

**Retrieval.** "Auto-routing" — picks between semantic and relational strategies. Falls back session → graph.

**Forgetting.** `forget()` is a first-class operation. Semantics **⚠️ NEEDS DEEPER DIVE**.

**Benchmarks.** None quantified in README.

**Storage.** Neo4j + Postgres + vector store.

**License / production.** Apache-2.0, 16.7k stars, active.

**What to port.** The **four-verb surface** (`remember`, `recall`, `forget`, `improve`) is notably cleaner than NeuroMem's current `observe` / `retrieve` / `consolidate` / `update` / `forget` five-verb-plus-adapters surface. Not a mechanism port — an API-design influence for Phase 6 documentation work.

---

## 14. MemPalace — the head-to-head baseline

**Identity.** Not an arxiv-first system. Repository `github.com/recca0120/mempalace` (the author's blog — `recca0120.github.io/en/2026/04/08/mempalace-ai-memory-system/` — gives the primary description). A **critical-analysis paper** exists (arXiv 2604.21284v1, *Spatial Metaphors for LLM Memory: A Critical Analysis of the MemPalace Architecture*). Went viral in April 2026 (~22k★ in 48 hours per third-party review in `medium.com/@creativeaininja/…`). Phase 5 will do the technical comparison because NeuroMem benches directly against it.

**Architecture.** A four-layer "memory palace":
- **L0** — identity (always loaded, ~100 tokens)
- **L1** — essential facts (loaded on wake-up, ~70 tokens)
- **L2** — topic-filtered on-demand
- **L3** — full semantic search
Combined startup cost: **~170 tokens**.

**Temporal KG.** Local SQLite; every fact has a validity window (bi-temporal). This is a direct parallel to Graphiti at a much smaller scale.

**Retrieval stack.** Hybrid retrieval — BM25 + dense + rerank. Per a third-party audit (`nicholasrhodes.substack.com`): **60.3% R@10 with no reranker**, **88.9% R@10 with hybrid + no LLM**, and the viral **96.6% LongMemEval** number reproduced under hybrid + reranker + LLM.

**Write policy / consolidation / forgetting.** **⚠️ NEEDS DEEPER DIVE** in Phase 5 where the head-to-head gap-analysis happens (NeuroMem memory already has `reference/mempalace/` with the codebase cloned per project memory).

**License.** Permissive OSS (specific terms **⚠️ NEEDS DEEPER DIVE**).

**What NeuroMem already ported.** Per project memory: the L0–L3 layered context (`ContextManager`), the verbatim-only 2-stage retrieval path, per-workload retrieval recipes, the v0.4.0 bi-temporal KG on links. NeuroMem's published v0.3.2 numbers **beat MemPalace head-to-head on all three benchmarks**. The remaining gap is persistence of the graph layer.

---

## 15. Lighter-coverage systems

These are included because the brief mandated them, but none alter the Phase-6 roadmap on their own.

### 15.1 SCM — Self-Controlled Memory
Wang et al., arXiv **2304.13343** (2023-04-26, DASFAA 2025). Plug-and-play memory stream + controller over instruction-following LLMs. No fine-tuning. Tasks: long-term dialogue, book summarisation, meeting summarisation. Quantitative numbers **⚠️ NEEDS DEEPER DIVE**. OSS: `wbbeyourself/SCM4LLMs`. **Overlap with NeuroMem: full** — controller-over-memory-stream is effectively what `MemoryController` does. No new mechanism to port.

### 15.2 RET-LLM
Modarressi et al., arXiv **2305.14322** (2023-05-23). General read-write memory storing Davidsonian-semantics triplets. Eclipsed by the authors' later MemLLM work. **Overlap: partial** — triplet-store idea is close to what a persisted `MemoryGraph` would store. Reference, not a port.

### 15.3 CAMELoT
He et al., arXiv **2402.13449** (2024-02-21). Training-free associative memory module attached to frozen attention-based LLMs. Consolidation via a non-parametric distribution model weighted by novelty × recency. **+29.7% perplexity reduction** on ArXiv long-context benchmarks with a 128-token window. **Overlap: none direct**, but the novelty × recency weighting is the same shape as NeuroMem's salience × recency score.

---

## 16. Production framework patterns (fold-in from brief §3)

### 16.0 Framework map

| Framework | Memory primitives | Store abstraction | Status |
| --- | --- | --- | --- |
| **LangGraph** | Checkpointer (per-thread), `BaseStore` (cross-thread), `InMemoryStore` / `AsyncPostgresStore` impls | **`BaseStore`** (required) | The *de-facto* abstraction other frameworks compete against. |
| **LangMem** | Sits on LangGraph `BaseStore`; adds Memory Manager + Prompt Optimizer | `BaseStore` | Thin; 45 open issues. |
| **LlamaIndex** | `VectorMemory`, `ChatMemoryBuffer`, `SummaryMemoryBuffer`, `Mem0Memory` | `BaseMemory` | More chat-history-oriented than cross-session. |
| **CrewAI** | `short_term`, `long_term`, `entity`, `contextual` | `Storage` abstraction | Opinionated 4-split. Contradicts Tulving naming. |
| **Letta** | `core` / `recall` / `archival` blocks | Postgres (Alembic migrations) | LLM mutates memory via tool calls. |
| **OpenAI Assistants / Responses API** | Thread memory (managed) | Proprietary | Memory is *opaque* to the developer. |
| **Pydantic AI** | Message history only | N/A | No long-term memory primitive. |

**Top-three framework observations relevant to NeuroMem's gap analysis:**
1. **Every major framework except Pydantic AI has a store abstraction; LangGraph's `BaseStore` is the one other systems target.** NeuroMem does not conform to any of them.
2. **No framework treats "procedural" memory as a distinct persisted layer.** LangMem's Prompt Optimizer is the closest, and it rewrites prompts, not persists procedural traces. NeuroMem's `ProceduralMemory` has no peer.
3. **Letta's LLM-mutates-its-own-memory pattern is an outlier.** Most frameworks have memory that is written *about* the agent, not *by* the agent. NeuroMem is firmly in the "written about" camp.

---

### 16.1 Issue-tracker deep dive (Phase 3 payload)

Top-of-tracker scans 2026-04-24 across `getzep/graphiti`, `mem0ai/mem0`, `langchain-ai/langmem`, `langchain-ai/langgraph`, `letta-ai/letta`, `topoteretes/cognee`. Issues cited are open unless marked "(merged)" — inline GitHub IDs let Phase-6 verify they're still open at implementation time.

#### 16.1.1 Mem0 — the v3 migration is the single biggest pain cluster

The April-2026 v3 release shipped a rewrite of the extraction pipeline (ADD-only, no UPDATE/DELETE) and a hybrid-search addition (semantic + BM25 + entity). Both broke existing deployments:

1. **ADD-only extraction leaves contradictory facts live** (Mem0 #4956, 2026-04-24, label `bug`).
   > "After upgrading OSS to v3, the extraction pipeline is single-pass ADD-only — add() no longer emits UPDATE / DELETE events. For facts representing a mutable state (e.g. current employer, current city, relationship status), this means contradictory memories accumulate over time instead of the newer fact superseding the older one."

   The issue includes a concrete reproduction: "I work at Company A" followed by "I now work at Company B" three months later — both memories coexist, and retrieval (semantic + BM25 + entity) surfaces the stale one because scoring doesn't incorporate recency. **This is a direct validation of the concern flagged in §6 above about Mem0's write-schema drift.** NeuroMem's conflict resolver + reconsolidation weighting is actually *better* than v3 OSS Mem0 on this axis today.

2. **BM25 and entity extraction hardcoded to English** (Mem0 #4884, 2026-04 range, label `enhancement`).
   > "For non-English deployments (Chinese, Japanese, Korean, Arabic, Thai, Hindi, etc.) the practical consequences are: (1) BM25 silently becomes a no-op. spaCy's English pipeline does not tokenize CJK / Arabic / Thai scripts into meaningful units… (2) Entity boost also disappears. Net effect: for most of the world, the v3 hybrid pipeline degrades to a semantic-only pipeline. Users see no error — they just silently miss the precision improvements."

   NeuroMem inherits this limitation too — `core/graph.py::extract_entities` is capitalization-based (Phase 0 §20.5), and `BM25Scorer` uses whitespace tokenisation. Phase 6 should decide whether to match the gap or ship language-dispatch.

3. **v3 migration breaks self-host on Qdrant** (Mem0 #4950, 2026-04-23): auto-recall threshold ignored, history writes diverted, native deps mis-bundled.

4. **Docker image Linux/AMD64 issues** (Mem0 #4945, 2026-04-23): multi-arch manifest builds broken because Mem0 doesn't publish from GitHub Actions.

5. **REST API `GET /memories` forwards top-level entity params to get_all() and fails after v3 filter requirement** (Mem0 #4955, 2026-04-24): breaking API change without a deprecation path.

**Wedge for NeuroMem.** Three cheap differentiators:
- NeuroMem *already has* a conflict resolver with recency/confidence/reinforcement weighting + `contradicts` graph link + `deprecated=True` metadata. Ship a Mem0-migration doc showing the parity.
- Opt-in language-dispatch hook on `BM25Scorer` and `extract_entities`. Don't over-build — just expose a `tokenizer_fn` injection point.
- Guarantee a stable REST/Python API across 0.x → 1.x with a deprecation pass. NeuroMem has a chance to be "the grown-up Mem0" here.

---

#### 16.1.2 Graphiti — correctness bugs in the community-detection layer

Graphiti's community-detection (`build_communities`) is the most complained-about surface. Cited issues are open as of 2026-04-24:

1. **`build_communities` LLM cost scales O(total_nodes)** (Graphiti #1401, 2026-04-13).
   > "On a 100k-node knowledge graph that's roughly 100k LLM calls per `build_communities` run, which makes the operation cost-prohibitive at scale even though the underlying clustering finishes in seconds."
   Reporter opened #1389 with a `sample_size` parameter fix, 3.1× wall-time speedup on test graph.

2. **`build_communities` hangs forever on hub-and-spoke graphs** (Graphiti #1400, 2026-04-13).
   > "label_propagation uses synchronous batch updates… groups of nodes swap labels symmetrically every iteration, producing a flip-flop that never converges. The `while True:` loop at the top of the function never terminates."
   Well-known pathology; Raghavan/Albert/Kumara (2007) fixed this with asynchronous LPA. Reporter opened #1388.

3. **`build_communities` crashes on nested attribute values with Neo4j** (Graphiti #1399): `TypeError: Property values can only be of primitive types`.

4. **`label_propagation` has unbounded `while True`, oscillates forever on mid-sized graphs** (Graphiti #1397).

5. **MCP Server: cross_encoder/reranker not configurable, hardcoded to OpenAI** (Graphiti #1393).
   > "This makes it impossible to run the MCP server without an OpenAI API key, even when using Anthropic/Gemini/Groq for both LLM and embeddings."
   The root cause is `graphiti_mcp_server.py:225` constructing `Graphiti(...)` without passing `cross_encoder`, so `Graphiti.__init__` falls back to `OpenAIRerankerClient()` unconditionally.

6. **FalkorDB support has cross-contamination bugs** (Graphiti #1331): `add_episode()` mutates shared `self.driver` causing cross-group data contamination.

7. **RFC: hybrid episode search via new `search_hybrid` and `get_episode` MCP tools** (Graphiti #1427, 2026-04-21): the hybrid-search surface users want isn't yet shipped.

**Wedge for NeuroMem.** NeuroMem's graph is in-process dict, so it *doesn't have* Graphiti's scaling bugs — but it also doesn't have community detection at all. The relevant lessons for Phase 6:
- **Any PPR or community-detection feature must be async from day one.** Synchronous LPA deadlocks are a class of failure we shouldn't repeat.
- **LLM-cost scaling is the dominant constraint for community-level operations on real graphs.** If NeuroMem ships community summaries or RAPTOR-style hierarchical indexing, sample-top-K is the right default, not all-members.
- **The reranker plumbing needs to be swappable.** NeuroMem's `cross_encoder_reranker` uses a single default model. A `reranker` config section parallel to LLM/embedder is H1 work.

---

#### 16.1.3 LangMem — persistence confusion and bypass patterns

LangMem has 45 open issues on a 1.4k-star repo; the most cited complaints:

1. **"Persistence?" — tool writes don't surface in the store** (LangMem #154, 2026-04-07).
   > User report: uses `create_manage_memory_tool` + `create_search_memory_tool` with a PostgreSQL store, never sees any persistence record in the `store` table. Comment thread (from user `m13v`): "the create_manage_memory_tool writes to the store but the default PostgreSQL checkpointer setup doesn't always surface those records cleanly. what worked for us: **bypass the high-level memory tools and write directly to a JSONL append log per session, then build a SQLite index on top for retrieval queries**. the memory tools are convenient but they hide the persistence layer in a way that makes debugging really painful."

2. **Summarization fails with cryptic error when trimmed window lacks HumanMessage** (LangMem #156, 2026-04-13).
   > Error messaging is unhelpful; users can't diagnose without reading source.

3. **Keyword-based retrieval is the default; users reimplement cosine-similarity themselves.** From the same #154 thread: "embedding + semantic search implementation that handles the chunking and hybrid retrieval (keyword + cosine similarity) for agent memory was way more reliable than the keyword-based approach the default tools use."

**Wedge for NeuroMem.** This is the clearest win in the survey. LangMem's default experience is:
- Confusing about where data lands.
- Keyword-retrieval-only by default.
- Error messages that send users to source-code reading.

NeuroMem today is:
- Explicit about backend choice via YAML.
- BM25 + cross-encoder + HyDE + optional LLM rerank by default.
- Provides `explain(memory_id)` for attribution debugging.

Phase 6 recommendation: **ship a `NeuroMemStore(BaseStore)` class** that plugs into LangGraph's memory surface with NeuroMem's retrieval stack behind it. That makes NeuroMem the drop-in upgrade the `m13v`-in-#154 user was looking for. Single H1 item.

---

#### 16.1.4 LangGraph — `BaseStore` has its own correctness issues

The `BaseStore` / Checkpointer surface is the de-facto target for memory libraries, but it has open correctness bugs that Phase 6 should be aware of before depending on it:

1. **Memory leak: `_checkpointer_put_after_previous` coroutine chains accumulate with default `durability="async"`** (LangGraph #7094, 2026-03-10, label `bug`).
   > Detailed reproduction with 200-step graph + 10ms checkpoint latency. "durability='async' accumulated checkpoint dicts vs. sync" — the chain of `Task[N] → coroutine → self + prev=Task[N-1]` grows with every superstep. Peak memory grows linearly.
   **Implication:** any `NeuroMemStore` that wraps an async Postgres checkpoint needs to await writes, not fire-and-forget.

2. **`InMemoryStore.put()` overwrites `created_at` on update** (LangGraph #7411, 2026-04-04): behavioural inconsistency with `PostgresStore` which preserves `created_at` via `ON CONFLICT DO UPDATE` with only `updated_at` in the `SET` clause.
   **Implication:** if NeuroMem uses `created_at` for any ordering logic, the in-memory vs. Postgres backends currently diverge. NeuroMem's `MemoryItem.created_at` + `last_accessed` are the right fields; matching Postgres-Store semantics is the right default.

3. **`Store on conditional edge causes error`** (LangGraph #6340, 2025-10-24, `pending v1.1`): a conditional edge function declaring `store: BaseStore` as a parameter crashes at runtime on LangGraph Platform. Users work around by dropping the parameter, which means conditional routing cannot use memory.

4. **`store.delete()` and `adelete()` skip namespace validation** (LangGraph #7575, 2026-04-21, label `bug`).

5. **`AsyncPostgresStore` cleanup leaves pending background batch tasks** (LangGraph #6367, 2025-10-31).

6. **Breaking change in `langgraph-prebuilt==1.0.2` without version constraints** (LangGraph #6363, 2025-10-30): the LangGraph ecosystem is not version-stable across patch releases.

**Wedge for NeuroMem.** `BaseStore` is the *right* target — it's where LangGraph users live — but it's not a stable abstraction. Phase 6 should pick `BaseStore` conformance as H1 work but pin a *specific* `langgraph` version, keep the `BaseStore` adapter in a separate `neuromem[langgraph]` extra, and ship integration tests that run against the pinned version. Do not make NeuroMem's core take a hard dep on `langgraph`.

---

#### 16.1.5 Letta — surface-area bugs, not memory-model bugs

Letta's open issues mostly track *tool orchestration* failures (sandbox name errors, JSON schema mismatches, provider-bundling), not memory-layer bugs. Top-of-tracker as of 2026-04-24:

1. **Tool execution sandbox `NameError 'DynamicModel'` when `args_json_schema` has no `title` field** (Letta #3319, 2026-04-19): cosmetic naming mismatch between `datamodel-code-generator` output and the sandbox reference.

2. **`POST /v1/tools` 500 SQL error when tool name cannot be extracted from `source_code` or `json_schema`** (Letta #3318): input-validation gap at the API boundary.

3. **Error wrapper mislabels upstream provider rate limits as "Rate limited by OpenAI"** (Letta #3310, 2026-04-16): affects GLM-5/z.ai and likely others. Error attribution is wrong when the upstream isn't OpenAI.

4. **`GoogleVertexProvider` fails to register on server startup** (Letta #3322, 2026-04-23).

**Wedge for NeuroMem.** Minimal. Letta's memory model (core/recall/archival blocks) is stable; the pain is in tool orchestration which isn't NeuroMem's market. One takeaway: **error messages should carry the upstream provider name** — NeuroMem calls OpenAI/Ollama/Anthropic in the retrieval stack and should surface which provider failed. Small H1 polish.

---

#### 16.1.6 Cognee — quieter tracker, enrichment-heavy

Cognee's tracker is dominated by auto-generated CodeRabbit enrichment comments on user issues. Signal-to-noise is lower than the other repos. Top-of-tracker bugs involve SQLite/Postgres dataset-name reuse, LanceDB schema drift, and Neo4j/Postgres graph-aware embedding bugs. No consistent memory-model wedge emerges. Phase 3 deferred deeper read.

---

### 16.2 Synthesis: the wedge list for Phase 6

Derived from §16.1 complaints — these are where competitor users are actively frustrated, meaning differentiation is cheap:

| # | Complaint locus | NeuroMem Phase-6 response | Horizon |
| --- | --- | --- | --- |
| 1 | LangGraph `BaseStore` users have to bypass LangMem to get semantic retrieval (LangMem #154) | Ship `NeuroMemStore(BaseStore)` — NeuroMem's retrieval stack behind LangGraph's store protocol | **H1** |
| 2 | Mem0 v3 ADD-only leaves stale/contradictory facts live (Mem0 #4956) | Document + benchmark NeuroMem's existing conflict resolver as the Mem0-migration answer | H1 (docs) |
| 3 | Mem0 BM25/entity hardcoded to English (Mem0 #4884) | Injection points on `BM25Scorer.tokenizer_fn` + `extract_entities` | H1 |
| 4 | Graphiti community-detection LLM cost is O(total_nodes) (#1401) | If/when NeuroMem adds community summaries or RAPTOR, default to sample-top-K | H2 constraint |
| 5 | Graphiti `build_communities` has correctness bugs — sync LPA deadlocks (#1400) | Any NeuroMem graph-detection feature must be async; lean on existing `PriorityTaskScheduler` | H2 constraint |
| 6 | Graphiti MCP reranker is hardcoded OpenAI (#1393) | Add a `reranker` config section to `NeuroMemConfig` so users can swap cross-encoder | **H1** |
| 7 | LangMem/Letta error messages don't surface provider name | Wrap all provider calls with provider-tagged exceptions | H1 polish |
| 8 | LangGraph `InMemoryStore.put()` overwrites `created_at` (#7411) | Match PostgresStore semantics in `NeuroMemStore` from day one | H1 correctness |
| 9 | LangGraph `durability="async"` memory leak (#7094) | `NeuroMemStore` awaits writes; don't fire-and-forget | H1 correctness |
| 10 | General: Mem0 REST API breaks across v3 migration (#4955) | Ship a stable 1.0 with deprecation policy; freeze 0.3.x API for v1 | H2 process |

This list is the direct input to Phase 5's competitive gap matrix and Phase 6's H1 prioritisation.

---

## 16.3 Context engineering & retrieval deep-dive (Phase 4 fold-in)

*Goal: an evidence-based recommendation for NeuroMem's default retrieval stack. This section covers the retrieval-mechanism papers not already covered under a named system in §§1-15.*

---

### 16.3.1 GraphRAG (Microsoft) — community summaries as first-class index

**Citation.** Edge, Trinh, Cheng, Bradley, Chao, Mody, Truitt, Metropolitansky, Ness, Larson. *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*, arXiv **2404.16130**, 2024-04-24 (revised 2025-02-19).

**Mechanism.** LLM entity extraction → KG construction → **Leiden community detection** → LLM-generated summary per community at index time → query-time **map-reduce** (generate a partial answer per community summary, summarise partials into a final answer). Two query modes: *global* (sensemaking, uses community summaries) and *local* (conventional retrieval on entities/neighbourhoods).

**Reported wins.** Substantial comprehensiveness/diversity improvements over conventional RAG on 1M+ token corpora for query-focused summarisation. Community summaries provide answers that chunk-level retrieval *cannot* produce (e.g., "what are the main themes?").

**Cost.** Indexing is LLM-heavy. Graphiti issues #1400 / #1401 (Phase 3 §16.1.2) are a direct cautionary tale — Graphiti re-implemented a GraphRAG-style community layer and is eating correctness + O(N) LLM-cost bugs. **Microsoft's GraphRAG itself has the same scaling profile.**

**What to port.** Community-summary indexing is distinct from anything NeuroMem currently does — the `MemoryGraph.get_clusters()` gives us the community assignments, but no summaries are generated. Ported as Phase-6 H2 behind the constraints from §16.2 (async from day one, sample-top-K).

---

### 16.3.2 HyDE — hypothetical-answer embeddings

**Citation.** Gao, Ma, Lin, Callan. *Precise Zero-Shot Dense Retrieval without Relevance Labels*, arXiv **2212.10496**, 2022-12-20.

**Mechanism.** LLM generates a *hypothetical answer* to the query → embed that → retrieve with the hypothetical-answer embedding. The bi-encoder bottleneck filters hallucinated content because only facets shared with real documents survive to similarity.

**Reported wins.** Significantly outperforms Contriever baseline on BEIR web-search / QA / fact-verification tasks zero-shot. Comparable to fine-tuned retrievers without any training.

**NeuroMem state.** Already shipping (`core/hyde.py`) with a **user-voice prompt** (memory `feedback_hyde_is_the_unlock.md`), disk+memory cache, and configurable per-workload (disable for ConvoMem/MemBench, enable for LongMemEval per memory `feedback_hyde_overturned_for_convomem.md`).

**What Phase 4 changes in the recommendation.** Nothing — NeuroMem's current policy (per-workload HyDE toggle, cached) is correct. HyDE's zero-shot-beats-fine-tuning claim is the theoretical backing for why a small LLM + HyDE can beat a large fine-tuned retriever.

---

### 16.3.3 Self-RAG — reflection-token-gated retrieval

**Citation.** Asai, Wu, Wang, Sil, Hajishirzi. *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*, arXiv **2310.11511**, 2023-10-17.

**Mechanism.** A single LM trained to emit four reflection tokens:
- `Retrieve` — should I retrieve?
- `IsRel` — is this passage relevant?
- `IsSup` — is my answer supported by the passage?
- `IsUse` — is my answer useful?

Training: a *critic* LLM generates reflection tokens offline; a *generator* LLM is fine-tuned to predict them. The four-token framework generalises across open-domain QA, reasoning, fact verification, long-form generation.

**Where it helps.** Fixed retrieval for every query hurts when the query doesn't need it. Self-RAG learns *when* to retrieve.

**Limitations.** Requires fine-tuning. NeuroMem is framework-agnostic — we can't fine-tune end users' models. The four-token framework can still be applied *at inference* via prompting, but that loses the training-distilled efficiency.

**What to port.** The *idea* — retrieval gating — not the implementation. NeuroMem's existing multi-hop detection (`MemoryController._is_multi_hop_query`) already decides *how* to retrieve; a **should-I-retrieve-at-all?** check at the facade level would save tokens on pure-chitchat turns. Phase-6 H2 candidate, cheap to prototype via LLM or classifier.

---

### 16.3.4 Corrective RAG (CRAG) — retrieval-evaluator + web fallback

**Citation.** Yan, Gu, Zhu, Ling. *Corrective Retrieval Augmented Generation*, arXiv **2401.15884**, 2024-01-29 (v3 2024-10-07).

**Mechanism.** A lightweight retrieval-evaluator outputs a confidence score, which triggers one of three actions:
- **Refine** — decompose-then-recompose the retrieved passages, filter irrelevant spans, re-assemble.
- **Web search** — if confidence is low, fall back to web search to augment.
- **Pass-through** — use as-is if confidence is high.

**Where it helps.** When the corpus is stale or shallow; the retrieval-evaluator catches garbage-in before garbage-out.

**What to port for NeuroMem.** The **retrieval-evaluator + decompose-then-recompose** is a direct analogue of what NeuroMem could do with its existing `cross_encoder_reranker` confidence scores and `conflict_resolver` deprecation. The *web-search* fallback is orthogonal — NeuroMem is a personal-memory library, not a general RAG engine, and corpus staleness is less of a concern when users are writing their own memories.

---

### 16.3.5 RULER — the "effective context length" reality check

**Citation.** Hsieh, Sun, Kriman, Acharya, Rekesh, Jia, Zhang, Ginsburg (NVIDIA). *RULER: What's the Real Context Size of your Long-Context Language Models?*, arXiv **2404.06654**, 2024-04-09 (v3 2024-08-06).

**Findings.**
- Evaluated 17 long-context models across 13 tasks spanning **vanilla NIAH, multi-key retrieval, multi-hop tracing/aggregation, QA/reasoning**.
- Models claiming 32K context — "only about half maintain satisfactory performance at 32K length."
- Yi-34B (200K advertised) showed "large room for improvement" at longer lengths.
- "Almost all models exhibit large performance drops as context length increases."
- Vanilla NIAH numbers are misleading — near-perfect NIAH masks poor performance on aggregation/multi-hop.

**Implication for NeuroMem.** The "just stuff everything in" alternative to RAG / memory is **not viable** for multi-hop reasoning in 2026. Even Titans-class models (§8 Phase 1) are the exception, not the rule. Cross-session memory retrieval remains necessary; in-session context stuffing alone breaks on complex queries. This justifies NeuroMem's existence against the "long context eats RAG" argument.

**Phase-4 recommendation note.** NeuroMem should publish — at some point — a RULER-shaped evaluation: "at what session length does a pure-long-context approach stop answering multi-hop questions correctly, and where does NeuroMem + k=5 retrieval stay accurate?" That graph is the single best pitch slide against "just use Claude's 1M context."

---

### 16.3.6 ColBERT / ColBERTv2 — late-interaction retrieval

**Citation.** Khattab, Zaharia. *ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT*, arXiv **2004.12832**, SIGIR 2020.

**Mechanism.** Per-token BERT embeddings for query and document. Similarity score = sum over query tokens of `max` cosine against document tokens (MaxSim). Document encodings are precomputed offline. 2 orders of magnitude faster than cross-encoder at comparable quality; 4 orders fewer FLOPs per query.

**Trade-off.**
- **Bi-encoder** (single dense vector per doc) → fastest, cheapest, weakest on lexical-exact matches.
- **ColBERT** (per-token vectors, late interaction) → middle ground, per-doc storage scales ~30× bi-encoder.
- **Cross-encoder** (joint query-doc encoding) → best quality, slowest, only usable for reranking top-N.

**NeuroMem state.** We use bi-encoder + BM25 blend + cross-encoder on top-30. We do not use ColBERT.

**Phase-4 recommendation.** Don't add ColBERT. The cross-encoder rerank already dominates the precision step, and ColBERT's storage cost makes it a bad fit for a memory library where every user has their own index. ColBERT shines on shared corpora where the ~30× storage cost amortises across users.

---

### 16.3.7 Contextual Retrieval revisited — the failure-rate staircase

Consolidating Anthropic's 2024-09-19 post (§11) with the broader survey:

| Stage | Failure rate | Delta |
| --- | --- | --- |
| Plain chunk embeddings | 5.7% | baseline |
| + Contextual-chunk embeddings | 3.7% | **−35% relative** |
| + BM25 on contextual chunks | 2.9% | **−49% cumulative** |
| + Reranker (Cohere, top-150 → top-20) | 1.9% | **−67% cumulative** |

**What each step buys.**
- *Contextual prepend* (50–100 tokens of LLM-generated context before each chunk) — disambiguates chunks whose meaning depends on document context. Single LLM call per chunk at index time; prompt-cached at ~$1.02 per 1M document tokens.
- *BM25 hybrid* — catches exact-term queries where embeddings fail (names, IDs, dates, rare words).
- *Reranker* — cross-encoder precision on top-150.

**NeuroMem stack (current):**
- bi-encoder ✅
- BM25 hybrid ✅ (configurable `bm25_blend`)
- cross-encoder rerank ✅ (ms-marco-MiniLM-L-12-v2)
- contextual-chunk embeddings ❌

**The single largest absent piece in the Anthropic recipe is the contextual-chunk prepend.** It runs in `VerbatimStore.store` (`core/verbatim.py` line ~132 — the `for idx, chunk in enumerate(chunks)` loop). One LLM call per chunk, cached. Expected delta **not measured in NeuroMem's harness**; a-priori upper bound from Anthropic's study is −35% relative failure-rate reduction. The lower bound is easy — per-chunk prepends are trivially opt-in.

---

### 16.3.8 HippoRAG body-read — the PPR mechanics

Filling the `⚠️ NEEDS DEEPER DIVE` from Phase 1 §3 via secondary sources. The HippoRAG paper (arXiv 2405.14831) concretely:

- **Indexing.** Per-passage OpenIE extraction via an LLM → `(subject, relation, object)` triples → each subject/object becomes a node; the passage ID is attached as an attribute of the edge. Canonicalisation: cosine-similarity of phrase-string embeddings above a threshold → merge into canonical node.
- **Retrieval — entity extraction.** Query is passed through an LLM (or the same NER-style extraction) to get *query entities*.
- **Retrieval — PPR.** The query entities become the *personalization vector* of Personalized PageRank. Personalisation weight is typically 1/|query_entities| on each matched node, 0 elsewhere. Restart probability typically 0.5. PPR runs to convergence (iterative power-method, usually <30 iterations on graphs of interest).
- **Retrieval — passage scoring.** Each passage's score = sum of PPR mass accumulated on nodes that edge back to it.
- **Cost claim.** 10–30× cheaper, 6–13× faster than IRCoT at comparable recall — because PPR is single-step, IRCoT is multi-step interleaved retrieval.

**NeuroMem implications.**
- NeuroMem's `_entity_index` gives us the node side for free.
- `MemoryGraph.get_related(memory_id, depth=1)` is BFS, not PPR. Replacing BFS with PPR is a local change inside `_graph_retrieve`; the matrix is small (NeuroMem graphs are per-user, likely <100k nodes), so a NumPy sparse PPR is a ~200-LOC addition.
- PPR convergence has predictable latency (power-method on small graphs is microseconds to milliseconds). Async-from-day-one constraint (§16.2) is easy to satisfy.

---

### 16.3.9 RAPTOR body-read — clustering & hierarchy

Filling Phase 1 §10's `⚠️ NEEDS DEEPER DIVE`. RAPTOR (arXiv 2401.18059) uses:

- **Clustering:** **Gaussian Mixture Models on UMAP-reduced embeddings**, variable cluster count per level. The authors use GMM over UMAP specifically because k-means needs a preset k.
- **Summarisation:** LLM summarises each cluster → summary becomes a new node at the next level up.
- **Recursion:** repeat until the top level contains a single root (or until corpus is exhausted).
- **Retrieval modes:**
  - *Tree traversal* — greedy best-first from root.
  - *Collapsed tree* — all nodes at all levels compete in a single k-NN pool. Usually wins in published benchmarks.
- **Cost:** `O(n · log n)` LLM calls for summarisation; `O(n)` embedding calls. On a 1000-doc corpus this is ~10–20k LLM calls — not prohibitive for personal memory, too expensive for enterprise-scale indexing.

**NeuroMem implication.** A collapsed-tree RAPTOR on top of `VerbatimStore` is an H2 feature. It does not replace chunk-level retrieval; it adds a higher-abstraction index for queries that chunk-level can't answer ("summarise my last month" / "what are my recurring themes?"). Overlap with NeuroMem's existing `daily_summary` / `weekly_digest` — RAPTOR generalises these to content-driven rather than time-driven hierarchies.

---

### 16.3.10 The recommended default retrieval stack for NeuroMem

Consolidating Phase 1 + Phase 3 + Phase 4, the Phase-6 recommendation for NeuroMem's default retrieval is:

**Ingestion:**
1. Chunk raw text (`VerbatimStore.chunk_text`).
2. *(new)* **Prepend LLM-generated 50–100 token context** to each chunk before embedding (Anthropic recipe, §16.3.7).
3. Embed chunk (bi-encoder, `all-MiniLM-L6-v2` or `text-embedding-3-large` per workload).
4. Store chunk in `VerbatimStore` + entity-extract for `_entity_index`.
5. *(conditional H2)* if `consolidation_interval` window fires, update semantic layer with interleaved replay (Phase 2 §16.1).
6. *(conditional H2)* if `raptor.enabled`, update RAPTOR tree nodes.

**Retrieval (default, cognitive path):**
1. HyDE-expand query (per-workload toggle — already implemented).
2. Parallel-retrieve from semantic + procedural + episodic + verbatim (already implemented).
3. Hybrid-rank: bi-encoder × BM25 × hybrid-boosts (keyword / quoted / person / temporal).
4. Cross-encoder rerank top-30 with swappable model (Phase-6 H1: add `reranker` config section per §16.2 #6).
5. *(new H2)* Optional PPR second-pass on entity graph, blended with reranker score.
6. Conflict-detect + brain gating + reconsolidation (all existing).
7. Return top-k.

**Retrieval (verbatim-only path, MemBench-shaped):**
1. Skip HyDE, skip cognitive layers.
2. Embed → BM25 blend → cross-encoder rerank on top-N.
3. Return top-k. (already implemented, unchanged)

**Retrieval (query-focused-summarisation path, new H2):**
1. If query is "summarise" / "themes" / "over time" / "what's happening with X" → route to *GraphRAG-map-reduce-over-community-summaries* mode.
2. Community summaries built at consolidation time (sample-top-K, async).

**What this stack costs (order of magnitude, per call):**
- Standard retrieve: 1 embed + 1 BM25 + 1 cross-encoder (top-30) ≈ **~30-100ms**, 0 LLM calls.
- HyDE-expanded retrieve: + 1 LLM call (cached on repeat) ≈ **300-800ms first call, ~30ms cached**.
- PPR-augmented retrieve: + PPR power-iteration on small graph ≈ **~5ms**, 0 LLM calls.
- QFS/GraphRAG-mode retrieve: + LLM map-reduce over community summaries ≈ **2-5s**, 2-20 LLM calls.

**Index-time cost:**
- Current: 1 embed per chunk = ~3ms per chunk.
- With contextual prepend: + 1 cached LLM call per chunk = ~$1/million document tokens one-time.
- With PPR: no additional at index; done at query time.
- With RAPTOR: `O(n·log n)` LLM summarisation calls at index build.
- With community summaries: `O(num_communities)` LLM calls at consolidation, sample-top-K per community.

---

## 17. Cross-system mechanism matrix (Phase 5 input)

| Mechanism | Present in | Status in NeuroMem |
| --- | --- | --- |
| Vector-only retrieval | All | ✅ |
| BM25 hybrid | Anthropic CR, Graphiti, MemPalace, Mem0g | ✅ |
| Cross-encoder rerank | Anthropic CR, Graphiti, MemPalace | ✅ |
| Contextual chunk embeddings | Anthropic CR | ❌ |
| PPR over entity KG | HippoRAG, HippoRAG 2 | ❌ (BFS only) |
| RAPTOR hierarchical summaries | RAPTOR | ❌ |
| Bi-temporal edges | Zep/Graphiti, MemPalace | ✅ in-process only (not persisted) |
| LLM add/update/delete write-time arbitration | Mem0 (paper), A-MEM | ❌ |
| Link-at-write-time (dynamic) | A-MEM | ❌ |
| Importance-weighted retrieval (Park et al. shape) | Generative Agents | ✅ partial |
| Reflection / question-driven consolidation | Generative Agents | ❌ |
| CLS-style slow consolidation | *None (all surveyed systems are immediate)* | ❌ (matches the field) |
| One-shot selective forgetting API | Larimar | ❌ |
| Surprise-triggered write | Titans | ❌ (and requires model-level access) |
| LangGraph `BaseStore` conformance | LangMem | ❌ (docstring-only) |
| LLM self-mutation via tool calls | Letta | ❌ (MCP tools are for external callers, not the agent's own memory-write loop) |

---

## 18. Gaps flagged for deeper dive

The items below I could not nail from abstract-only reads and will re-open later when they matter:

- MemGPT exact DMR / MSC numbers (paper body §4).
- HippoRAG and HippoRAG 2 per-benchmark numbers (MuSiQue / 2Wiki / HotpotQA / LV-Eval / NarrativeQA / PopQA).
- A-MEM retrieval strategy and exact LoCoMo numbers.
- Generative Agents importance prompt and the exact α/β/γ retrieval weights.
- Titans benchmark numbers per task, plus 2026 public-code status.
- Larimar read/write-key mechanism, scene-memory capacity, eviction.
- RAPTOR clustering algorithm (commonly cited as GMM + UMAP, unconfirmed from abstract).
- MemPalace write/consolidation/forgetting internals.
- LangMem issue-tracker top complaints (Phase 3).
- Mem0 issue-tracker top complaints (Phase 3).

---

## 19. Exit criterion for Phase 1

Every system named above either:
- contributes a **mechanism** to the Phase-6 roadmap (explicitly cited in "What to port"); or
- is flagged as overlap-only (§15.1) or out-of-scope (Titans — requires model-level access).

Phase 2 will ground each portable mechanism in a cited cognitive/neuro theory before it becomes a roadmap item.

---

## Sources (web)

- [Letta repo](https://github.com/letta-ai/letta)
- [LangMem repo](https://github.com/langchain-ai/langmem)
- [Cognee repo](https://github.com/topoteretes/cognee)
- [Graphiti repo](https://github.com/getzep/graphiti)
- [Mem0 repo](https://github.com/mem0ai/mem0)
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [MemPalace blog](https://recca0120.github.io/en/2026/04/08/mempalace-ai-memory-system/)
- [MemPalace third-party audit](https://nicholasrhodes.substack.com/p/mempalace-ai-memory-review-benchmarks)
- [MemPalace Medium review](https://medium.com/@creativeaininja/mempalace-the-viral-ai-memory-system-that-got-22k-stars-in-48-hours-an-honest-look-and-setup-26c234b0a27b)
- [Agent Memory Paper List (survey)](https://github.com/Shichun-Liu/Agent-Memory-Paper-List)
- [Awesome-Agent-Memory](https://github.com/TeleAI-UAGI/Awesome-Agent-Memory)

ArXiv IDs cited: 2310.08560 (MemGPT), 2304.03442 (Generative Agents), 2405.14831 (HippoRAG), 2502.14802 (HippoRAG 2), 2502.12110 (A-MEM), 2504.19413 (Mem0), 2501.13956 (Zep), 2501.00663 (Titans), 2403.11901 (Larimar), 2401.18059 (RAPTOR), 2304.13343 (SCM), 2305.14322 (RET-LLM), 2402.13449 (CAMELoT), 2604.21284 (MemPalace critical analysis), 2404.16130 (GraphRAG), 2212.10496 (HyDE), 2310.11511 (Self-RAG), 2401.15884 (CRAG), 2404.06654 (RULER), 2004.12832 (ColBERT).
