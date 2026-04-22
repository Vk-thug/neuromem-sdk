"""
Memory controller - the "prefrontal cortex" of NeuroMem.

Orchestrates all memory operations and coordinates between different
memory systems.
"""

import uuid
from datetime import date as date_cls, datetime, timedelta, timezone
from neuromem.utils.time import ensure_utc
from typing import List, Optional, Dict, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from neuromem.core.types import MemoryItem, MemoryType, MemoryLink
from neuromem.core.retrieval import RetrievalEngine
from neuromem.core.consolidation import Consolidator
from neuromem.core.decay import DecayEngine
from neuromem.memory.episodic import EpisodicMemory
from neuromem.memory.semantic import SemanticMemory
from neuromem.memory.procedural import ProceduralMemory
from neuromem.memory.session import SessionMemory
from neuromem.utils.embeddings import get_embedding
from neuromem.utils.logging import get_logger
from neuromem.utils.validation import validate_user_id, validate_content
from neuromem import constants
from neuromem.core.task_scheduler import PriorityTaskScheduler
from neuromem.core.task_types import Task, TaskType, TaskPriority
from neuromem.core.observability.metrics import MetricsCollector
from neuromem.core.workers.ingest_worker import IngestWorker
from neuromem.core.workers.maintenance_worker import MaintenanceWorker
from neuromem.core.policies.reconsolidation import ReconsolidationPolicy
from neuromem.core.policies.conflict_resolution import ConflictResolver
from neuromem.core.graph import MemoryGraph

logger = get_logger(__name__)


class MemoryController:
    """
    Central controller for all memory operations.

    Orchestrates retrieval with conflict detection, reconsolidation,
    graph-based context expansion, and temporal queries.
    """

    def __init__(
        self,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        procedural: ProceduralMemory,
        session: SessionMemory,
        retriever: RetrievalEngine,
        consolidator: Consolidator,
        decay_engine: DecayEngine,
        embedding_model: str = "text-embedding-3-large",
        config: Optional[Any] = None,
        verbatim: Optional[Any] = None,
    ):
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.session = session
        self.retriever = retriever
        self.consolidator = consolidator
        self.decay_engine = decay_engine
        self.embedding_model = embedding_model
        self.config = config or {}
        self.verbatim = verbatim  # VerbatimStore or None
        self.auto_tagger = None
        self._retrieval_cache: Dict[str, Dict[str, Any]] = {}

        # Reusable thread pool for parallel retrieval — avoids per-call thread spawn overhead
        self._retrieval_pool = ThreadPoolExecutor(max_workers=3)

        # Memory relationship graph
        self.graph = MemoryGraph()

        # Conflict resolver -- always active
        self.conflict_resolver = ConflictResolver(self._get_dict_config("conflict_resolution"))

        # Reconsolidation policy -- always active
        self.reconsolidation_policy = ReconsolidationPolicy(self._get_dict_config("proactive"))

        # Async infrastructure
        self.async_enabled = self._get_dict_config("async").get("enabled", True)
        if self.async_enabled:
            async_cfg = self._get_dict_config("async")
            self.scheduler = PriorityTaskScheduler(async_cfg)
            self.metrics = MetricsCollector()
            self.ingest_worker = IngestWorker(self.scheduler, self.metrics, self, self.config)
            self.maintenance_worker = MaintenanceWorker(
                self.scheduler, self.metrics, self, self.config
            )
            self.ingest_worker.start()
            self.maintenance_worker.start()
        else:
            self.scheduler = None
            self.metrics = None
            self.ingest_worker = None
            self.maintenance_worker = None

        # Brain system (v0.3.0) — gated on config
        self.brain = None
        brain_cfg = self._get_dict_config("brain")
        if not brain_cfg and hasattr(self.config, "brain"):
            try:
                brain_cfg = self.config.brain()
            except Exception:
                brain_cfg = {}
        if brain_cfg.get("enabled", False):
            try:
                from neuromem.brain.system import BrainSystem

                # Use the episodic backend for BrainState persistence
                backend = self.episodic.backend if hasattr(self.episodic, "backend") else None
                if backend:
                    self.brain = BrainSystem(
                        user_id=getattr(self.episodic, "user_id", "default"),
                        backend=backend,
                        config=brain_cfg,
                    )
                    logger.info("BrainSystem initialized", extra={"user_id": self.brain.user_id})
            except Exception as e:
                logger.warning(
                    "Failed to initialize BrainSystem, continuing without brain",
                    exc_info=True,
                    extra={"error": str(e)},
                )
                self.brain = None

        # AutoTagger
        if self.config and hasattr(self.config, "tagging"):
            try:
                if self.config.tagging().get("auto_tag_enabled", False):
                    from neuromem.utils.auto_tagger import AutoTagger

                    self.auto_tagger = AutoTagger(
                        llm_model=self.config.model().get("consolidation_llm", "gpt-4o-mini")
                    )
            except Exception as e:
                logger.warning(
                    "Failed to initialize AutoTagger", exc_info=True, extra={"error": str(e)}
                )
                self.auto_tagger = None

    def _get_dict_config(self, key: str) -> dict:
        """Safely get a config dict section, handling both dict and object configs."""
        if isinstance(self.config, dict):
            return self.config.get(key, {})
        if hasattr(self.config, "get"):
            val = self.config.get(key, {})
            return val if isinstance(val, dict) else {}
        return {}

    def shutdown(self, timeout: float = 5.0):
        """Gracefully shutdown async workers and thread pool."""
        if self.async_enabled:
            if self.ingest_worker:
                self.ingest_worker.stop(timeout=timeout)
            if self.maintenance_worker:
                self.maintenance_worker.stop(timeout=timeout)
        if self._retrieval_pool:
            self._retrieval_pool.shutdown(wait=False)

    # ----------------------------------------------------------------
    # RETRIEVAL with conflict detection + reconsolidation
    # ----------------------------------------------------------------

    def retrieve(
        self,
        embedding: List[float],
        task_type: str,
        k: int = 8,
        parallel: bool = True,
        query_text: Optional[str] = None,
        expand_context: bool = False,
    ) -> List[MemoryItem]:
        """
        Retrieve relevant memories with conflict detection and reconsolidation.

        Args:
            embedding: Query embedding vector
            task_type: Type of task (chat, system_design, etc.)
            k: Number of memories to retrieve
            parallel: Use parallel retrieval (default: True)
            query_text: Original query text for reconsolidation context
            expand_context: Attach related memories via graph traversal
        """
        if parallel:
            sem_i, sem_s, proc_i, proc_s, epi_i, epi_s = self._retrieve_parallel(embedding, k)
        else:
            sem_i, sem_s, proc_i, proc_s, epi_i, epi_s = self._retrieve_sequential(embedding, k)

        all_items = sem_i + proc_i + epi_i
        all_sims = sem_s + proc_s + epi_s

        # Verbatim retrieval (v0.4.0) — merge raw chunks with cognitive results
        if self.verbatim is not None:
            try:
                verb_items, verb_sims = self.verbatim.query(embedding, k=k * 2)
                if verb_items:
                    all_items, all_sims = self._merge_verbatim_results(
                        cognitive_items=all_items,
                        cognitive_sims=all_sims,
                        verbatim_items=verb_items,
                        verbatim_sims=verb_sims,
                    )
            except Exception as e:
                logger.warning(
                    "Verbatim retrieval failed, using cognitive only",
                    extra={"error": str(e)},
                )

        if not all_items:
            return []

        # Rank
        use_hybrid = (
            self.config
            and hasattr(self.config, "retrieval")
            and self.config.retrieval().get("hybrid_enabled", False)
        )
        if use_hybrid:
            try:
                from neuromem.memory.hybrid_retrieval import HybridRetrieval

                rc = self.config.retrieval()
                hr = HybridRetrieval(
                    recency_weight=rc.get("recency_weight", 0.2),
                    importance_weight=rc.get("importance_weight", 0.3),
                    similarity_weight=rc.get("similarity_weight", 0.5),
                    recency_half_life_days=rc.get("recency_half_life_days", 30),
                )
                # Retrieve a larger pool so hybrid boosts have room to re-rank
                pool_k = max(k * 3, 30)
                top_items = hr.retrieve(embedding, all_items, all_sims, k=pool_k)
            except Exception as exc_hybrid:
                logger.warning(
                    "Hybrid retrieval failed",
                    exc_info=True,
                    extra={"error": str(exc_hybrid)},
                )
                top_items = self._basic_rank(all_items, all_sims, k, query_text)
        else:
            top_items = self._basic_rank(all_items, all_sims, k, query_text)

        # Apply hybrid signal boosts universally (v0.4.0)
        # Keyword overlap, quoted phrase, person name, and temporal boosts
        # fire AFTER ranking, regardless of which initial path was taken.
        # This fixes the bug where boosts were only applied in _basic_rank.
        if query_text and top_items:
            try:
                from neuromem.core.hybrid_boosts import apply_hybrid_boosts
                from neuromem.core.bm25_scorer import BM25Scorer

                item_sim_lookup: Dict[str, float] = {
                    item.id: all_sims[i] if i < len(all_sims) else 0.5
                    for i, item in enumerate(all_items)
                }
                scored = [(item, item_sim_lookup.get(item.id, 0.5)) for item in top_items]

                # Step 1: Apply heuristic boosts (keyword overlap, quoted phrases, etc.)
                scored = apply_hybrid_boosts(scored, query_text)

                # Step 2: BM25 re-ranking — proper IDF-weighted lexical scoring
                # mixed with the boosted similarity score. BM25 fixes the cases
                # where embeddings miss precise lexical matches (proper nouns,
                # IDs, dates, and rare-term queries).
                #
                # Clean cognitive wrapping ("User: X\nAssistant: Memory stored.")
                # before BM25 scoring. The wrapping tokens have high IDF
                # (appearing in ALL cognitive memories) which dilutes useful
                # term frequencies.
                if len(scored) >= 2:
                    documents = []
                    for item, _ in scored:
                        c = getattr(item, "content", "")
                        if "\nAssistant: Memory stored." in c:
                            c = c.split("\nAssistant: Memory stored.")[0]
                        if c.startswith("User: "):
                            c = c[6:]
                        documents.append(c)
                    bm25 = BM25Scorer(documents)
                    bm25_scores = bm25.normalized_score(query_text)
                    scored = [
                        (item, 0.50 * sim + 0.50 * bm25_scores[i])
                        for i, (item, sim) in enumerate(scored)
                    ]
                    scored.sort(key=lambda x: x[1], reverse=True)

                # Step 3: Cross-encoder re-ranking of top-30 (the precision step)
                # Cross-encoders take (query, doc) pairs as joint input and
                # produce a much more accurate relevance score than bi-encoders.
                # Used by Bing/Google as the final re-ranker.
                if len(scored) >= 2:
                    try:
                        from neuromem.core.cross_encoder_reranker import (
                            rerank_with_cross_encoder,
                        )

                        scored = rerank_with_cross_encoder(
                            query=query_text,
                            items_with_scores=scored,
                            top_k=min(30, len(scored)),
                            blend_weight=0.9,
                        )
                    except Exception:
                        logger.debug("Cross-encoder unavailable, skipping", exc_info=True)

                # Step 4: LLM batch re-rank of top-5 (optional, gated by config)
                # For queries requiring REASONING (implicit connections,
                # preferences, abstention), the cross-encoder is insufficient.
                # An LLM directly evaluates which top-5 candidate best matches
                # the query intent. Single batched LLM call per query, cached.
                use_llm_rerank = False
                if hasattr(self.config, "retrieval"):
                    use_llm_rerank = self.config.retrieval().get("llm_rerank_enabled", False)
                if use_llm_rerank and len(scored) >= 2:
                    try:
                        from neuromem.core.llm_reranker import llm_rerank

                        rc = self.config.retrieval()
                        scored = llm_rerank(
                            query=query_text,
                            items_with_scores=scored,
                            top_k=min(8, len(scored)),
                            model=rc.get("llm_rerank_model", "qwen2.5-coder:7b"),
                            provider=rc.get("llm_rerank_provider", "ollama"),
                            blend_weight=rc.get("llm_rerank_blend", 0.4),
                        )
                    except Exception:
                        logger.debug("LLM rerank unavailable, skipping", exc_info=True)

                top_items = [item for item, _ in scored[:k]]
            except Exception:
                logger.warning("Hybrid boosts/BM25/cross-encoder failed", exc_info=True)
                top_items = top_items[:k]
        else:
            top_items = top_items[:k]

        # Keyword fallback: only run when top vector similarity is weak.
        best_sim = max(all_sims) if all_sims else 0.0
        if query_text and best_sim < 0.7:
            top_items = self._keyword_fallback(top_items, query_text, k)

        # Conflict detection
        top_items = self._detect_and_resolve_conflicts(top_items)

        # Brain system re-ranking (v0.3.0) — CA1 value-based gating
        if self.brain is not None:
            try:
                ranked_with_scores = [
                    (item, all_sims[all_items.index(item)] if item in all_items else 0.5)
                    for item in top_items
                ]
                re_ranked = self.brain.on_retrieve(ranked_with_scores, task_type)
                top_items = [item for item, _ in re_ranked[:k]]
            except Exception:
                logger.warning("BrainSystem.on_retrieve failed in controller", exc_info=True)

        # Build O(1) lookup for similarity scores (replaces O(n) list.index per item)
        item_sim_map: Dict[str, float] = {
            item.id: all_sims[i] if i < len(all_sims) else 0.0 for i, item in enumerate(all_items)
        }

        # Reinforce + reconsolidate
        for item in top_items:
            self.decay_engine.reinforce(item)
            sim = item_sim_map.get(item.id, 0.0)
            self.reconsolidation_policy.update_memory_after_retrieval(item, sim)

            if self.reconsolidation_policy.should_reconsolidate(item, query_text):
                logger.info("Reconsolidation triggered", extra={"memory_id": item.id})

            self._retrieval_cache[item.id] = {
                "similarity": sim,
                "score": getattr(item, "score", 0.0),
                "retrieved_at": datetime.now(timezone.utc),
                "conflicts_detected": item.metadata.get("conflict_resolved", False),
            }

        # Context expansion via graph
        if expand_context:
            for item in top_items:
                related_ids = self.graph.get_related(item.id, depth=1)
                expanded = []
                for rel_id in related_ids[:3]:
                    rel = self._find_memory_by_id(rel_id)
                    if rel:
                        expanded.append(rel.content)
                if expanded:
                    item.metadata["expanded_context"] = expanded

        return top_items

    def retrieve_verbatim_only(
        self,
        embedding: List[float],
        query_text: str,
        k: int = 8,
        bm25_blend: float = 0.5,
        ce_blend: float = 0.9,
        ce_top_k: int = 30,
    ) -> List[MemoryItem]:
        """
        Deterministic 2-stage retrieval against verbatim chunks only.

        Pipeline: bi-encoder pool → BM25 blend → cross-encoder rerank → top-k.
        Skips the cognitive pipeline (semantic/procedural/episodic ranking,
        conflict detection, brain re-ranking, decay/reconsolidation). The
        verbatim store is already ground-truth (confidence=1.0), so the
        cognitive layers only add noise on MemBench-style exact-fact retrieval.

        See: feedback_pipeline_complexity_vs_simplicity.md and
        feedback_ce_dominance_trap.md for why 2-stage wins on MemBench.
        """
        if self.verbatim is None:
            logger.warning("retrieve_verbatim_only called but verbatim store disabled")
            return []

        pool_k = max(k * 4, 30)
        items, sims = self.verbatim.query(embedding, k=pool_k)
        if not items:
            return []

        scored: List[tuple] = list(zip(items, sims))

        # Stage 1: BM25 lexical blend — catches exact-term matches
        # (proper nouns, phone numbers, dates, rare tokens) that embeddings miss.
        if len(scored) >= 2 and bm25_blend > 0:
            try:
                from neuromem.core.bm25_scorer import BM25Scorer

                documents = [getattr(it, "content", "") for it, _ in scored]
                bm25 = BM25Scorer(documents)
                bm25_scores = bm25.normalized_score(query_text)
                scored = [
                    (it, (1 - bm25_blend) * sim + bm25_blend * bm25_scores[i])
                    for i, (it, sim) in enumerate(scored)
                ]
                scored.sort(key=lambda x: x[1], reverse=True)
            except Exception:
                logger.debug("BM25 stage failed in verbatim-only path", exc_info=True)

        # Stage 2: cross-encoder precision rerank on top-N
        if len(scored) >= 2 and ce_blend > 0:
            try:
                from neuromem.core.cross_encoder_reranker import (
                    rerank_with_cross_encoder,
                )

                scored = rerank_with_cross_encoder(
                    query=query_text,
                    items_with_scores=scored,
                    top_k=min(ce_top_k, len(scored)),
                    blend_weight=ce_blend,
                )
            except Exception:
                logger.debug("Cross-encoder unavailable in verbatim-only path", exc_info=True)

        return [it for it, _ in scored[:k]]

    def _basic_rank(
        self, items: List[MemoryItem], sims: List[float], k: int, query_text: str = None
    ) -> List[MemoryItem]:
        """Basic ranking path — hybrid boosts applied universally in retrieve()."""
        ranked = self.retriever.rank(items, sims)
        if query_text:
            ranked = self.retriever.boost_keyword_matches(ranked, query_text)
        diverse = self.retriever.apply_inhibition(ranked)
        filtered = self.retriever.filter_by_confidence(diverse)
        # Return a larger pool so the universal hybrid_boosts step has room to work
        pool_k = max(k * 3, 30)
        return [item for item, score in filtered[:pool_k]]

    def _merge_verbatim_results(
        self,
        cognitive_items: List[MemoryItem],
        cognitive_sims: List[float],
        verbatim_items: List[MemoryItem],
        verbatim_sims: List[float],
    ) -> tuple:
        """
        Merge cognitive and verbatim results, deduplicating by content.

        After the embed-from-user_input fix, cognitive memories and verbatim
        chunks for the same content produce nearly identical embeddings and
        similarity scores. Naive merging creates duplicates that halve the
        effective retrieval depth. This dedup keeps only the highest-similarity
        version of each unique content.

        Verbatim chunks are PREFERRED on ties because they have:
          - Cleaner content (no User:/Assistant: wrapping)
          - Higher base salience (0.85 vs cognitive ~0.65)
          - confidence=1.0 (ground truth)
        """

        def _content_key(content: str) -> str:
            """Normalize content for dedup: strip User:/Assistant: wrapping."""
            text = content or ""
            if text.startswith("User: "):
                text = text[6:]
            if "\nAssistant: Memory stored." in text:
                text = text.split("\nAssistant: Memory stored.")[0]
            # Use first 200 chars as fingerprint (full hash would also work)
            return text.strip()[:200].lower()

        # Build content-keyed dedup map (verbatim wins ties)
        content_map: Dict[str, tuple] = {}  # content_key -> (item, best_sim, source)

        # Add verbatim FIRST so they win ties (verbatim is preferred)
        for item, sim in zip(verbatim_items, verbatim_sims):
            key = _content_key(getattr(item, "content", ""))
            if key not in content_map or sim > content_map[key][1]:
                content_map[key] = (item, sim, "verbatim")

        # Add cognitive only if we don't already have this content
        for item, sim in zip(cognitive_items, cognitive_sims):
            key = _content_key(getattr(item, "content", ""))
            if key not in content_map:
                content_map[key] = (item, sim, "cognitive")
            elif sim > content_map[key][1] and content_map[key][2] == "cognitive":
                content_map[key] = (item, sim, "cognitive")

        # Sort by similarity descending
        sorted_entries = sorted(content_map.values(), key=lambda x: x[1], reverse=True)
        merged_items = [e[0] for e in sorted_entries]
        merged_sims = [e[1] for e in sorted_entries]

        return merged_items, merged_sims

    def _detect_and_resolve_conflicts(self, top_items: List[MemoryItem]) -> List[MemoryItem]:
        """Detect and resolve contradicting memories in results."""
        if len(top_items) < 2:
            return top_items

        deprecated_ids: set = set()

        for i in range(len(top_items)):
            if top_items[i].id in deprecated_ids:
                continue
            for j in range(i + 1, len(top_items)):
                if top_items[j].id in deprecated_ids:
                    continue
                if self.conflict_resolver.detect_conflict(top_items[i], top_items[j]):
                    preferred, deprecated = self.conflict_resolver.resolve(
                        top_items[i], top_items[j]
                    )
                    deprecated_ids.add(deprecated.id)
                    self.graph.add_link(
                        MemoryLink(
                            source_id=preferred.id,
                            target_id=deprecated.id,
                            link_type="contradicts",
                            strength=1.0,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                    logger.info(
                        "Conflict resolved",
                        extra={"preferred": preferred.id, "deprecated": deprecated.id},
                    )

        if deprecated_ids:
            top_items = [i for i in top_items if i.id not in deprecated_ids]
        return top_items

    # ----------------------------------------------------------------
    # OBSERVE
    # ----------------------------------------------------------------

    def observe(
        self,
        user_input: str,
        assistant_output: str,
        user_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
        max_content_length: int = 50000,
    ):
        """Observe and store a user-assistant interaction.

        `max_content_length` defaults to 50 KB to cap production inputs; benchmark
        adapters ingesting long-haystack docs (LongMemEval) should pass a larger
        value to avoid ValidationError on legitimately long sessions.
        """
        user_id = validate_user_id(user_id)
        user_input = validate_content(
            user_input, max_length=max_content_length, field_name="user_input"
        )
        assistant_output = validate_content(
            assistant_output, max_length=max_content_length, field_name="assistant_output"
        )

        if self.async_enabled:
            task = Task(
                task_type=TaskType.OBSERVE,
                priority=TaskPriority.CRITICAL,
                data={
                    "user_input": user_input,
                    "assistant_output": assistant_output,
                    "user_id": user_id,
                },
                created_at=datetime.now(timezone.utc),
                salience=self._calculate_salience(user_input, assistant_output),
                trace_id=None,
            )
            self.scheduler.enqueue(task)
            if self.metrics:
                self.metrics.increment("observe.queued")
        else:
            self._observe_sync(user_input, assistant_output, user_id, extra_metadata)

    def _observe_sync(
        self,
        user_input: str,
        assistant_output: str,
        user_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ):
        from neuromem.core.graph import extract_entities

        content = f"User: {user_input}\nAssistant: {assistant_output}"
        # Embed the USER input only (cleaner semantic signal for retrieval).
        # Wrapping content with "User:"/"Assistant:" prefixes used to pollute
        # the embedding — we still STORE the wrapped content for context
        # but compute the embedding from the clean user text.
        embedding_source = user_input if user_input.strip() else content
        embedding = get_embedding(embedding_source, self.embedding_model)
        tags = []
        metadata: Dict[str, Any] = dict(extra_metadata) if extra_metadata else {}

        if (
            self.config
            and hasattr(self.config, "tagging")
            and self.config.tagging().get("auto_tag_enabled", False)
        ):
            try:
                from neuromem.utils.auto_tagger import AutoTagger

                tagger = AutoTagger(
                    llm_model=self.config.model().get("consolidation_llm", "gpt-4o-mini")
                )
                enrichment = tagger.enrich_memory(content)
                tags = enrichment.get("tags", [])
                # Merge (don't overwrite) so extra_metadata from the caller
                # is preserved alongside auto-tagging enrichment.
                metadata.update(
                    {
                        "intent": enrichment.get("intent"),
                        "sentiment": enrichment.get("sentiment", {}).get("sentiment"),
                        "entities": enrichment.get("entities", []),
                    }
                )
            except Exception as e:
                logger.warning("Auto-tagging failed", exc_info=True, extra={"error": str(e)})

        memory_id = str(uuid.uuid4())

        # Extract entities and register in graph for graph-augmented retrieval.
        # Uses fast regex heuristics (<1ms), no LLM call.
        entities = extract_entities(content)
        if entities:
            self.graph.register_entities(memory_id, entities)
            metadata["entities"] = entities

        # Topic detection (v0.4.0) — auto-classify for metadata filtering
        try:
            from neuromem.core.topic_detector import detect_topic

            topic = detect_topic(user_input)
            metadata["topic"] = topic
        except Exception:
            pass

        memory_item = MemoryItem(
            id=memory_id,
            user_id=user_id,
            content=content,
            embedding=embedding,
            memory_type=MemoryType.EPISODIC,
            salience=self._calculate_salience(user_input, assistant_output),
            confidence=constants.DEFAULT_EPISODIC_CONFIDENCE,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=constants.DEFAULT_EPISODIC_DECAY_RATE,
            reinforcement=1,
            inferred=False,
            editable=True,
            tags=tags,
            metadata=metadata,
        )
        # Brain system enrichment (v0.3.0)
        if self.brain is not None:
            memory_item = self.brain.on_observe(memory_item)

        self.episodic.store(memory_item)

        # Verbatim storage (v0.4.0) — store raw text chunks for high-recall retrieval
        if self.verbatim is not None:
            try:
                # Propagate ALL metadata (including benchmark corpus_id, timestamp, etc.)
                verb_meta = {**metadata, "source": "user", "cognitive_id": memory_id}
                self.verbatim.store(content=user_input, metadata=verb_meta)
                # Also store assistant output if substantive (not just "Memory stored.")
                if assistant_output and len(assistant_output) > 20:
                    asst_meta = {**metadata, "source": "assistant", "cognitive_id": memory_id}
                    self.verbatim.store(content=assistant_output, metadata=asst_meta)
            except Exception as e:
                logger.warning(
                    "Verbatim storage failed, continuing with cognitive only",
                    extra={"error": str(e)},
                )

        self.session.add_turn(user_input, assistant_output)

    # ----------------------------------------------------------------
    # CONSOLIDATION
    # ----------------------------------------------------------------

    def consolidate(self):
        """Trigger memory consolidation (episodic -> semantic/procedural)."""
        from neuromem.utils.embeddings import batch_get_embeddings

        episodic_items = self.episodic.get_all()
        candidates = self.decay_engine.schedule_consolidation(episodic_items)
        if not candidates:
            return

        semantic_items = self.semantic.get_all()
        procedural_items = self.procedural.get_all()
        result = self.consolidator.consolidate(candidates, semantic_items, procedural_items)
        source_ids = [c.id for c in candidates]

        # Batch embed all new memories in a single API call instead of N individual calls.
        # For N new memories this saves (N-1) * ~400ms of API round-trip overhead.
        all_new = result.new_semantic_memories + result.new_procedural_memories
        needs_embedding = [m for m in all_new if not m.embedding]
        if needs_embedding:
            try:
                texts = [m.content for m in needs_embedding]
                embeddings = batch_get_embeddings(texts, self.embedding_model)
                for memory, emb in zip(needs_embedding, embeddings):
                    memory.embedding = emb
            except Exception as e:
                logger.error(
                    "Batch embedding failed for consolidation",
                    exc_info=True,
                    extra={"error": str(e)},
                )
                # Fall back to individual embedding
                for memory in needs_embedding:
                    try:
                        memory.embedding = get_embedding(memory.content, self.embedding_model)
                    except Exception:
                        pass

        for memory in result.new_semantic_memories:
            if not memory.embedding:
                continue
            if memory.memory_type != MemoryType.SEMANTIC:
                memory.memory_type = MemoryType.SEMANTIC
            self.semantic.store(memory)
            for src_id in source_ids:
                self.graph.add_link(
                    MemoryLink(
                        source_id=memory.id,
                        target_id=src_id,
                        link_type="derived_from",
                        strength=0.8,
                        created_at=datetime.now(timezone.utc),
                    )
                )

        for memory in result.new_procedural_memories:
            if not memory.embedding:
                continue
            self.procedural.store(memory)
            for src_id in source_ids:
                self.graph.add_link(
                    MemoryLink(
                        source_id=memory.id,
                        target_id=src_id,
                        link_type="derived_from",
                        strength=0.8,
                        created_at=datetime.now(timezone.utc),
                    )
                )

        active, forgotten = self.decay_engine.apply_decay(episodic_items)
        for item in forgotten:
            self.episodic.delete(item.id)

    # ----------------------------------------------------------------
    # MEMORY LISTING & MANAGEMENT
    # ----------------------------------------------------------------

    def list_memories(self, memory_type: Optional[str] = None, limit: int = 50) -> List[MemoryItem]:
        all_memories: List[MemoryItem] = []
        if memory_type is None or memory_type == "episodic":
            all_memories.extend(self.episodic.get_all()[:limit])
        if memory_type is None or memory_type == "semantic":
            all_memories.extend(self.semantic.get_all()[:limit])
        if memory_type is None or memory_type == "procedural":
            all_memories.extend(self.procedural.get_all()[:limit])
        return all_memories[:limit]

    def explain(self, memory_id: str) -> Dict[str, Any]:
        memory = self._find_memory_by_id(memory_id)
        if not memory:
            return {"error": "Memory not found"}
        ri = self._retrieval_cache.get(memory_id, {})
        links = self.graph.get_links(memory_id)
        return {
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "why_used": {
                "similarity": ri.get("similarity", "N/A"),
                "salience": memory.salience,
                "confidence": memory.confidence,
                "reinforcement": memory.reinforcement,
                "final_score": ri.get("score", "N/A"),
                "conflicts_detected": ri.get("conflicts_detected", False),
            },
            "source": "inferred" if memory.inferred else "explicit",
            "created_at": memory.created_at.isoformat(),
            "last_accessed": memory.last_accessed.isoformat(),
            "retention_days": self.decay_engine.get_retention_period(memory),
            "graph": {
                "link_count": len(links),
                "links": [
                    {"target": link.target_id, "type": link.link_type, "strength": link.strength}
                    for link in links[:10]
                ],
            },
            "retrieval_stats": {
                "count": memory.retrieval_stats.retrieval_count if memory.retrieval_stats else 0,
                "avg_similarity": (
                    memory.retrieval_stats.avg_similarity if memory.retrieval_stats else 0.0
                ),
            },
        }

    def update_memory(self, memory_id: str, content: str):
        for mem_type in [self.episodic, self.semantic, self.procedural]:
            memory = mem_type.get_by_id(memory_id)
            if memory:
                if not memory.editable:
                    raise ValueError("This memory is not editable")
                memory.content = content
                memory.embedding = get_embedding(content, self.embedding_model)
                mem_type.update(memory)
                return
        raise ValueError("Memory not found")

    def forget_memory(self, memory_id: str):
        for mem_type in [self.episodic, self.semantic, self.procedural]:
            if mem_type.delete(memory_id):
                self.graph.remove_all_links(memory_id)
                return
        raise ValueError("Memory not found")

    # ----------------------------------------------------------------
    # BRAIN SYSTEM (v0.3.0)
    # ----------------------------------------------------------------

    def reinforce(self, memory_id: str, reward: float = 1.0, task_type: str = "chat") -> None:
        """Update TD values based on retrieval feedback.

        Called when a user/agent marks a retrieved memory as helpful (+1) or unhelpful (-1).
        """
        if self.brain is None:
            return
        memory = self._find_memory_by_id(memory_id)
        if memory is None:
            return
        self.brain.reinforce(memory_id, memory.embedding, task_type, reward)

    def get_working_memory(self) -> List[MemoryItem]:
        """Return memories currently in the PFC working memory buffer."""
        if self.brain is None:
            return []
        wm_ids = self.brain.get_working_memory_ids()
        items = []
        for mid in wm_ids:
            mem = self._find_memory_by_id(mid)
            if mem:
                items.append(mem)
        return items

    # ----------------------------------------------------------------
    # TAG QUERIES
    # ----------------------------------------------------------------

    def find_by_tags(
        self, tag_prefix: str, memory_type: Optional[str] = None, limit: int = 50
    ) -> List[MemoryItem]:
        """Find memories matching a tag prefix (hierarchical)."""
        all_memories = self.list_memories(memory_type, limit=limit * 3)
        return [m for m in all_memories if any(t.startswith(tag_prefix) for t in m.tags)][:limit]

    def get_tag_tree(self) -> Dict[str, int]:
        """Get all tags with counts."""
        all_memories = self.list_memories(limit=1000)
        counts: Dict[str, int] = {}
        for mem in all_memories:
            for tag in mem.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))

    # ----------------------------------------------------------------
    # TEMPORAL QUERIES
    # ----------------------------------------------------------------

    @staticmethod
    def _coerce_date(value: object) -> date_cls:
        """Coerce a string, datetime, or date into a date object."""
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date_cls):
            return value
        raise TypeError(f"Expected str, date, or datetime — got {type(value).__name__}")

    def get_memories_by_date(
        self, date: object, memory_type: Optional[str] = None
    ) -> List[MemoryItem]:
        d = self._coerce_date(date)
        start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return self.get_memories_in_range(start, end, memory_type)

    def get_memories_in_range(
        self, start: object, end: object, memory_type: Optional[str] = None
    ) -> List[MemoryItem]:
        if isinstance(start, str):
            start = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if isinstance(end, str):
            end = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        all_memories = self.list_memories(memory_type, limit=1000)
        return [
            m
            for m in all_memories
            if ensure_utc(start) <= ensure_utc(m.created_at) < ensure_utc(end)
        ]

    # ----------------------------------------------------------------
    # MULTI-HOP QUERY DECOMPOSITION
    # ----------------------------------------------------------------

    def _is_multi_hop_query(self, query: str) -> bool:
        """
        Detect if a query requires information from multiple distinct entities
        or topics — i.e., a multi-hop question.

        Heuristics (no LLM call needed):
        - Contains "both", "and" connecting distinct subjects
        - Contains comparative markers ("compare", "difference", "similar")
        - Contains multiple proper nouns or named entities
        """
        query_lower = query.lower()

        # Pattern 1: explicit multi-entity markers
        multi_markers = [
            "both",
            "and also",
            "as well as",
            "compared to",
            "difference between",
            "similarities between",
            "in common",
            "versus",
            " vs ",
        ]
        if any(marker in query_lower for marker in multi_markers):
            return True

        # Pattern 2: compound temporal markers that require cross-referencing
        # Simple "when did X" queries are NOT multi-hop — they are direct lookups.
        # Only route to multi-hop when the temporal aspect requires combining info.
        compound_temporal_markers = [
            "what changed",
            "over time",
            "between session",
            "how long has",
            "how long have",
            "how long did",
            "since when",
            "timeline",
        ]
        if any(m in query_lower for m in compound_temporal_markers):
            return True

        # Pattern 3: "how do X and Y" / "what did X and Y"
        import re

        if re.search(
            r"\b(how|what|where|when|why|do|did|does|have|has)\b.+\band\b.+\?", query_lower
        ):
            # Check if "and" connects two capitalized words (proper nouns)
            words = query.split()
            and_indices = [i for i, w in enumerate(words) if w.lower() == "and"]
            for idx in and_indices:
                before = words[idx - 1] if idx > 0 else ""
                after = words[idx + 1] if idx < len(words) - 1 else ""
                if before and before[0].isupper() and after and after[0].isupper():
                    return True

        return False

    def _decompose_query(self, query: str) -> List[str]:
        """
        Decompose a multi-hop query into independent sub-queries using an LLM.

        Based on: Least-to-Most Prompting (Zhou et al., 2022) and
        MultiHop-RAG (Tang & Yang, 2024) — standard RAG is inadequate for
        multi-hop queries; decomposition enables targeted per-entity retrieval.

        Returns the original query if decomposition fails or is not applicable.
        """
        try:
            import openai

            client = openai.OpenAI()

            prompt = (
                "Break this question into independent sub-questions that can each be "
                "answered from a single piece of information. Return ONLY the sub-questions, "
                "one per line. If the question is already simple (single person/topic), "
                "return it unchanged.\n\n"
                f"Question: {query}\n"
                "Sub-questions:"
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            raw = response.choices[0].message.content.strip()
            sub_queries = [q.strip().lstrip("0123456789.-) ") for q in raw.split("\n") if q.strip()]
            # Only use decomposition if it produced multiple sub-queries
            if len(sub_queries) >= 2:
                logger.info(
                    "Query decomposed for multi-hop retrieval",
                    extra={"original": query, "sub_queries": sub_queries},
                )
                return sub_queries
            return [query]
        except Exception as e:
            logger.warning(
                "Query decomposition failed, using original query", extra={"error": str(e)}
            )
            return [query]

    def retrieve_multihop(
        self,
        query: str,
        embedding: List[float],
        task_type: str,
        k: int = 8,
        parallel: bool = True,
        expand_context: bool = False,
    ) -> List[MemoryItem]:
        """
        Multi-hop retrieval: decompose complex queries into sub-queries,
        retrieve independently for each, and merge results with deduplication.

        Falls back to standard retrieval for simple (single-hop) queries.

        Based on research:
        - Least-to-Most Prompting (Zhou et al., 2022): 99% vs 16% on compositional tasks
        - MultiHop-RAG (Tang & Yang, 2024): standard RAG inadequate for multi-hop
        - IRCoT (Trivedi et al., 2022): interleaved retrieval improves multi-hop recall
        """
        if not self._is_multi_hop_query(query):
            return self.retrieve(
                embedding,
                task_type,
                k,
                parallel=parallel,
                query_text=query,
                expand_context=expand_context,
            )

        sub_queries = self._decompose_query(query)

        if len(sub_queries) <= 1:
            return self.retrieve(
                embedding,
                task_type,
                k,
                parallel=parallel,
                query_text=query,
                expand_context=expand_context,
            )

        # Cap at 3 sub-queries to limit latency (each adds ~500ms for embedding + retrieval)
        sub_queries = sub_queries[:3]

        # Retrieve independently for each sub-query
        all_results: List[MemoryItem] = []
        seen_ids: Set[str] = set()
        per_query_k = max(k // len(sub_queries), 3)
        sub_query_results: Dict[str, List[MemoryItem]] = {}

        for sub_q in sub_queries:
            sub_embedding = get_embedding(sub_q, self.embedding_model)
            results = self.retrieve(
                sub_embedding,
                task_type,
                per_query_k,
                parallel=parallel,
                query_text=sub_q,
                expand_context=expand_context,
            )
            sub_query_results[sub_q] = results
            for item in results:
                if item.id not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item.id)

        # ── Graph-augmented retrieval for multi-hop queries ──
        # Use entity index + graph traversal to find memories connected to
        # query entities. Applied ONLY in multi-hop path (not single-hop)
        # because RRF re-ranking can hurt single-hop precision.
        if self.graph._entity_index:
            # IRCoT gap detection: for sub-queries with weak results, try graph
            for sub_q, results in sub_query_results.items():
                if len(results) < 2:  # Weak or empty results
                    graph_fallback = self._graph_retrieve(sub_q, k=per_query_k)
                    for item in graph_fallback:
                        if item.id not in seen_ids:
                            all_results.append(item)
                            seen_ids.add(item.id)

            # Also get graph results for the original composite query
            graph_for_original = self._graph_retrieve(query, k=per_query_k)
            for item in graph_for_original:
                if item.id not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item.id)

        # Only fetch original query results if sub-queries didn't fill k slots.
        if len(all_results) < k:
            original_results = self.retrieve(
                embedding,
                task_type,
                k - len(all_results),
                parallel=parallel,
                query_text=query,
                expand_context=expand_context,
            )
            for item in original_results:
                if item.id not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item.id)

        return all_results[:k]

    # ----------------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------------

    def _keyword_fallback(
        self, top_items: List[MemoryItem], query_text: str, k: int
    ) -> List[MemoryItem]:
        """
        Keyword fallback: scan all memories for exact keyword matches
        that embedding search missed. This handles proper nouns and
        named entities that embedding models struggle with.

        Like the human brain's "tip of the tongue" recall — when
        semantic similarity fails, direct association rescues it.
        """
        import string as _string

        keywords = [
            w.lower().strip(_string.punctuation)
            for w in query_text.split()
            if w.lower().strip(_string.punctuation) not in constants.RETRIEVAL_STOP_WORDS
            and len(w.strip(_string.punctuation)) > 2
        ]

        if not keywords:
            return top_items

        existing_ids = {item.id for item in top_items}
        all_memories = self.list_memories(limit=500)

        keyword_matches = []
        for mem in all_memories:
            if mem.id in existing_ids:
                continue
            content_lower = mem.content.lower()
            matched = [kw for kw in keywords if kw in content_lower]
            if matched:
                # Score by: fraction of keywords matched * salience
                match_score = (len(matched) / len(keywords)) * mem.salience
                keyword_matches.append((mem, match_score))

        if keyword_matches:
            keyword_matches.sort(key=lambda x: x[1], reverse=True)
            # Prepend keyword matches (best first) so they rank above items that missed keywords
            best_keyword = [mem for mem, score in keyword_matches[:3]]
            top_items = best_keyword + top_items
            top_items = top_items[:k]

        return top_items

    def _find_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        for mem_type in [self.episodic, self.semantic, self.procedural]:
            memory = mem_type.get_by_id(memory_id)
            if memory:
                return memory
        return None

    # ----------------------------------------------------------------
    # GRAPH-AUGMENTED RETRIEVAL (HippoRAG-style)
    # ----------------------------------------------------------------

    def _graph_retrieve(self, query_text: str, k: int = 5) -> List[MemoryItem]:
        """
        Retrieve memories via entity-graph traversal.

        Based on HippoRAG (Gutierrez et al., 2024): extract entities from the
        query, find memories mentioning those entities via the index, then
        expand via graph links to find connected context.

        This is complementary to vector search — it finds memories that share
        entities with the query even when their embeddings are dissimilar.
        """
        from neuromem.core.graph import extract_entities

        query_entities = extract_entities(query_text)
        if not query_entities:
            # Fall back to simple word matching against entity index
            words = [w.strip("?.,!") for w in query_text.split() if w[0:1].isupper() and len(w) > 2]
            query_entities = [
                w
                for w in words
                if w
                not in {
                    "What",
                    "Who",
                    "Where",
                    "When",
                    "How",
                    "Why",
                    "The",
                    "Did",
                    "Does",
                    "Do",
                    "Which",
                    "Has",
                    "Have",
                    "Is",
                    "Are",
                }
            ]

        if not query_entities:
            return []

        memory_ids = self.graph.get_entity_connected_memories(
            query_entities, depth=1, max_per_entity=k
        )

        results: List[MemoryItem] = []
        for mid in memory_ids:
            mem = self._find_memory_by_id(mid)
            if mem:
                results.append(mem)
            if len(results) >= k:
                break

        return results

    @staticmethod
    def _rrf_merge(
        *ranked_lists: List[MemoryItem],
        k_constant: int = 60,
        max_results: int = 10,
    ) -> List[MemoryItem]:
        """
        Reciprocal Rank Fusion: merge multiple ranked lists into one.

        Based on RAG-Fusion (Raudaschl, 2023). Each item's score is the sum
        of 1/(k + rank) across all lists it appears in. This naturally handles
        different score scales (vector similarity vs keyword match vs graph).

        Args:
            ranked_lists: Multiple lists of MemoryItems, each in relevance order
            k_constant: Smoothing constant (default 60, standard in literature)
            max_results: Maximum items to return
        """
        scores: Dict[str, float] = {}
        item_map: Dict[str, MemoryItem] = {}

        for ranked_list in ranked_lists:
            for rank, item in enumerate(ranked_list):
                scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (k_constant + rank + 1)
                item_map[item.id] = item

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [item_map[mid] for mid in sorted_ids[:max_results]]

    def _retrieve_parallel(self, embedding: List[float], k: int):
        sem_i, sem_s, proc_i, proc_s, epi_i, epi_s = [], [], [], [], [], []
        executor = self._retrieval_pool
        futures = {
            executor.submit(
                self.semantic.retrieve,
                embedding,
                {"memory_type": [MemoryType.SEMANTIC.value, MemoryType.PROCEDURAL.value]},
                k * 2,
            ): "semantic",
            executor.submit(self.procedural.retrieve, embedding, {}, k): "procedural",
            executor.submit(
                self.episodic.retrieve, embedding, {"memory_type": MemoryType.EPISODIC.value}, k
            ): "episodic",
        }
        for future in as_completed(futures):
            mt = futures[future]
            try:
                items, sims = future.result()
                if mt == "semantic":
                    sem_i, sem_s = items, sims
                elif mt == "procedural":
                    proc_i, proc_s = items, sims
                elif mt == "episodic":
                    epi_i, epi_s = items, sims
            except Exception as e:
                logger.error(
                    f"Parallel retrieval failed for {mt}", exc_info=True, extra={"error": str(e)}
                )
        return sem_i, sem_s, proc_i, proc_s, epi_i, epi_s

    def _retrieve_sequential(self, embedding: List[float], k: int):
        sem_i, sem_s = self.semantic.retrieve(
            embedding,
            {"memory_type": [MemoryType.SEMANTIC.value, MemoryType.PROCEDURAL.value]},
            k * 2,
        )
        proc_i, proc_s = self.procedural.retrieve(embedding, {}, k)
        epi_i, epi_s = self.episodic.retrieve(
            embedding, {"memory_type": MemoryType.EPISODIC.value}, k
        )
        return sem_i, sem_s, proc_i, proc_s, epi_i, epi_s

    def _calculate_salience(self, user_input: str, assistant_output: str) -> float:
        """
        Calculate salience with brain-inspired heuristics.

        First-person factual statements are the most valuable (like human
        declarative memory formation). Questions are less salient than
        statements. Junk responses ("I don't know") reduce salience.
        """
        input_lower = user_input.lower()
        output_lower = assistant_output.lower()

        salience = constants.DEFAULT_BASE_SALIENCE

        # ── Boost: First-person factual statements (highest value) ──
        first_person_markers = [
            "my name is",
            "i am",
            "i'm",
            "i work",
            "i live",
            "i use",
            "i prefer",
            "i like",
            "i built",
            "i'm building",
            "i code",
            "my team",
            "my colleague",
            "our team",
            "we use",
            "we chose",
            "we deploy",
            "we follow",
            "we run",
            "i have",
            "i started",
            "my favorite",
            "i strongly",
        ]
        if any(marker in input_lower for marker in first_person_markers):
            salience += constants.SALIENCE_BOOST_FIRST_PERSON

        # ── Boost: Preference/opinion indicators ──
        if any(kw in input_lower for kw in constants.PREFERENCE_KEYWORDS):
            salience += constants.SALIENCE_BOOST_PREFERENCE

        # ── Boost: Longer, more detailed statements ──
        if len(user_input) > 100:
            salience += constants.SALIENCE_BOOST_LENGTH

        # ── Mild boost: Questions (less important than statements) ──
        if "?" in user_input:
            salience += constants.SALIENCE_BOOST_QUESTION

        # ── Penalty: Junk responses where assistant has no info ──
        junk_markers = [
            "i don't have access to",
            "i don't have personal",
            "i'm not sure what",
            "could you provide more",
            "unless it has been shared",
            "i need more context",
        ]
        if any(marker in output_lower for marker in junk_markers):
            salience -= constants.SALIENCE_PENALTY_JUNK

        return max(0.1, min(salience, 1.0))
