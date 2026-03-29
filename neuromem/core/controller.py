"""
Memory controller - the "prefrontal cortex" of NeuroMem.

Orchestrates all memory operations and coordinates between different
memory systems.
"""

import uuid
from datetime import datetime, timedelta, timezone
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
        self.auto_tagger = None
        self._retrieval_cache: Dict[str, Dict[str, Any]] = {}

        # Reusable thread pool for parallel retrieval — avoids per-call thread spawn overhead
        self._retrieval_pool = ThreadPoolExecutor(max_workers=3)

        # Memory relationship graph
        self.graph = MemoryGraph()

        # Conflict resolver -- always active
        self.conflict_resolver = ConflictResolver(
            self._get_dict_config("conflict_resolution")
        )

        # Reconsolidation policy -- always active
        self.reconsolidation_policy = ReconsolidationPolicy(
            self._get_dict_config("proactive")
        )

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

        # AutoTagger
        if self.config and hasattr(self.config, "tagging"):
            try:
                if self.config.tagging().get("auto_tag_enabled", False):
                    from neuromem.utils.auto_tagger import AutoTagger
                    self.auto_tagger = AutoTagger(
                        llm_model=self.config.model().get("consolidation_llm", "gpt-4o-mini")
                    )
            except Exception as e:
                logger.warning("Failed to initialize AutoTagger", exc_info=True, extra={"error": str(e)})
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
                top_items = hr.retrieve(embedding, all_items, all_sims, k=k)
            except Exception as e:
                logger.warning("Hybrid retrieval failed", exc_info=True, extra={"error": str(e)})
                top_items = self._basic_rank(all_items, all_sims, k, query_text)
        else:
            top_items = self._basic_rank(all_items, all_sims, k, query_text)

        # Keyword fallback: only run when top vector similarity is weak.
        best_sim = max(all_sims) if all_sims else 0.0
        if query_text and best_sim < 0.7:
            top_items = self._keyword_fallback(top_items, query_text, k)

        # Conflict detection
        top_items = self._detect_and_resolve_conflicts(top_items)

        # Build O(1) lookup for similarity scores (replaces O(n) list.index per item)
        item_sim_map: Dict[str, float] = {
            item.id: all_sims[i] if i < len(all_sims) else 0.0
            for i, item in enumerate(all_items)
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

    def _basic_rank(
        self, items: List[MemoryItem], sims: List[float], k: int, query_text: str = None
    ) -> List[MemoryItem]:
        ranked = self.retriever.rank(items, sims)
        if query_text:
            ranked = self.retriever.boost_keyword_matches(ranked, query_text)
        diverse = self.retriever.apply_inhibition(ranked)
        filtered = self.retriever.filter_by_confidence(diverse)
        return [item for item, score in filtered[:k]]

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
                    self.graph.add_link(MemoryLink(
                        source_id=preferred.id,
                        target_id=deprecated.id,
                        link_type="contradicts",
                        strength=1.0,
                        created_at=datetime.now(timezone.utc),
                    ))
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

    def observe(self, user_input: str, assistant_output: str, user_id: str):
        """Observe and store a user-assistant interaction."""
        user_id = validate_user_id(user_id)
        user_input = validate_content(user_input, max_length=50000, field_name="user_input")
        assistant_output = validate_content(assistant_output, max_length=50000, field_name="assistant_output")

        if self.async_enabled:
            task = Task(
                task_type=TaskType.OBSERVE,
                priority=TaskPriority.CRITICAL,
                data={"user_input": user_input, "assistant_output": assistant_output, "user_id": user_id},
                created_at=datetime.now(timezone.utc),
                salience=self._calculate_salience(user_input, assistant_output),
                trace_id=None,
            )
            self.scheduler.enqueue(task)
            if self.metrics:
                self.metrics.increment("observe.queued")
        else:
            self._observe_sync(user_input, assistant_output, user_id)

    def _observe_sync(self, user_input: str, assistant_output: str, user_id: str):
        from neuromem.core.graph import extract_entities

        content = f"User: {user_input}\nAssistant: {assistant_output}"
        embedding = get_embedding(content, self.embedding_model)
        tags = []
        metadata = {}

        if self.config and hasattr(self.config, "tagging") and self.config.tagging().get("auto_tag_enabled", False):
            try:
                from neuromem.utils.auto_tagger import AutoTagger
                tagger = AutoTagger(llm_model=self.config.model().get("consolidation_llm", "gpt-4o-mini"))
                enrichment = tagger.enrich_memory(content)
                tags = enrichment.get("tags", [])
                metadata = {
                    "intent": enrichment.get("intent"),
                    "sentiment": enrichment.get("sentiment", {}).get("sentiment"),
                    "entities": enrichment.get("entities", []),
                }
            except Exception as e:
                logger.warning("Auto-tagging failed", exc_info=True, extra={"error": str(e)})

        memory_id = str(uuid.uuid4())

        # Extract entities and register in graph for graph-augmented retrieval.
        # Uses fast regex heuristics (<1ms), no LLM call.
        entities = extract_entities(content)
        if entities:
            self.graph.register_entities(memory_id, entities)
            metadata["entities"] = entities

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
        self.episodic.store(memory_item)
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
                logger.error("Batch embedding failed for consolidation", exc_info=True, extra={"error": str(e)})
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
                self.graph.add_link(MemoryLink(
                    source_id=memory.id, target_id=src_id,
                    link_type="derived_from", strength=0.8, created_at=datetime.now(timezone.utc),
                ))

        for memory in result.new_procedural_memories:
            if not memory.embedding:
                continue
            self.procedural.store(memory)
            for src_id in source_ids:
                self.graph.add_link(MemoryLink(
                    source_id=memory.id, target_id=src_id,
                    link_type="derived_from", strength=0.8, created_at=datetime.now(timezone.utc),
                ))

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
                "links": [{"target": link.target_id, "type": link.link_type, "strength": link.strength} for link in links[:10]],
            },
            "retrieval_stats": {
                "count": memory.retrieval_stats.retrieval_count if memory.retrieval_stats else 0,
                "avg_similarity": memory.retrieval_stats.avg_similarity if memory.retrieval_stats else 0.0,
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
    # TAG QUERIES
    # ----------------------------------------------------------------

    def find_by_tags(self, tag_prefix: str, memory_type: Optional[str] = None, limit: int = 50) -> List[MemoryItem]:
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

    def get_memories_by_date(self, date: datetime, memory_type: Optional[str] = None) -> List[MemoryItem]:
        start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return self.get_memories_in_range(start, end, memory_type)

    def get_memories_in_range(self, start: datetime, end: datetime, memory_type: Optional[str] = None) -> List[MemoryItem]:
        all_memories = self.list_memories(memory_type, limit=1000)
        return [m for m in all_memories if ensure_utc(start) <= ensure_utc(m.created_at) < ensure_utc(end)]

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
        multi_markers = ["both", "and also", "as well as", "compared to", "difference between",
                         "similarities between", "in common", "versus", " vs "]
        if any(marker in query_lower for marker in multi_markers):
            return True

        # Pattern 2: compound temporal markers that require cross-referencing
        # Simple "when did X" queries are NOT multi-hop — they are direct lookups.
        # Only route to multi-hop when the temporal aspect requires combining info.
        compound_temporal_markers = [
            "what changed", "over time", "between session",
            "how long has", "how long have", "how long did",
            "since when", "timeline",
        ]
        if any(m in query_lower for m in compound_temporal_markers):
            return True

        # Pattern 3: "how do X and Y" / "what did X and Y"
        import re
        if re.search(r"\b(how|what|where|when|why|do|did|does|have|has)\b.+\band\b.+\?", query_lower):
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
            logger.warning("Query decomposition failed, using original query", extra={"error": str(e)})
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
                embedding, task_type, k, parallel=parallel,
                query_text=query, expand_context=expand_context,
            )

        sub_queries = self._decompose_query(query)

        if len(sub_queries) <= 1:
            return self.retrieve(
                embedding, task_type, k, parallel=parallel,
                query_text=query, expand_context=expand_context,
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
                sub_embedding, task_type, per_query_k,
                parallel=parallel, query_text=sub_q,
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
                embedding, task_type, k - len(all_results),
                parallel=parallel, query_text=query,
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
            w.lower().strip(_string.punctuation) for w in query_text.split()
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
            query_entities = [w for w in words if w not in {"What", "Who", "Where", "When", "How", "Why", "The", "Did", "Does", "Do", "Which", "Has", "Have", "Is", "Are"}]

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
            executor.submit(self.semantic.retrieve, embedding, {"memory_type": [MemoryType.SEMANTIC.value, MemoryType.PROCEDURAL.value]}, k * 2): "semantic",
            executor.submit(self.procedural.retrieve, embedding, {}, k): "procedural",
            executor.submit(self.episodic.retrieve, embedding, {"memory_type": MemoryType.EPISODIC.value}, k): "episodic",
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
                logger.error(f"Parallel retrieval failed for {mt}", exc_info=True, extra={"error": str(e)})
        return sem_i, sem_s, proc_i, proc_s, epi_i, epi_s

    def _retrieve_sequential(self, embedding: List[float], k: int):
        sem_i, sem_s = self.semantic.retrieve(embedding, {"memory_type": [MemoryType.SEMANTIC.value, MemoryType.PROCEDURAL.value]}, k * 2)
        proc_i, proc_s = self.procedural.retrieve(embedding, {}, k)
        epi_i, epi_s = self.episodic.retrieve(embedding, {"memory_type": MemoryType.EPISODIC.value}, k)
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
            "my name is", "i am", "i'm", "i work", "i live", "i use",
            "i prefer", "i like", "i built", "i'm building", "i code",
            "my team", "my colleague", "our team", "we use", "we chose",
            "we deploy", "we follow", "we run", "i have", "i started",
            "my favorite", "i strongly",
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
