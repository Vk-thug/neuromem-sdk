"""
NeuroMem SDK - Brain-Inspired Memory System for LangChain & LangGraph Agents

A human-inspired, multi-layer memory system that enables LLM agents to:
- Remember experiences (episodic)
- Learn stable facts (semantic)
- Adapt to user thinking style (procedural)
- Forget and correct over time
- Retrieve memories based on goal, salience, and context
"""

from datetime import datetime, timezone

from neuromem.config import NeuroMemConfig
from neuromem.user import User, UserManager
from neuromem.core.controller import MemoryController
from neuromem.core.retrieval import RetrievalEngine
from neuromem.core.consolidation import Consolidator
from neuromem.core.decay import DecayEngine
from neuromem.core.types import BeliefState, MemoryItem, MemoryType, RetrievalResult
from neuromem.memory.episodic import EpisodicMemory
from neuromem.memory.semantic import SemanticMemory
from neuromem.memory.procedural import ProceduralMemory
from neuromem.memory.session import SessionMemory
from neuromem.storage.base import MemoryBackend
from neuromem.utils.embeddings import get_embedding
from neuromem.utils.logging import get_logger

_logger = get_logger(__name__)


def _try_qdrant_or_fallback(vs_params: dict):
    """Attempt to initialize Qdrant; fall back to InMemoryBackend on failure.

    v0.4.0 default. Failure modes:
    * ``qdrant-client`` extra not installed (ImportError).
    * Qdrant service not reachable at ``host:port`` (ConnectionError).
    * Collection mismatch / Qdrant API error (any RuntimeError).

    All three log a warning naming the cause + the install/start command,
    then return an in-memory backend so the SDK still boots.
    """
    from neuromem.storage.memory import InMemoryBackend

    try:
        from neuromem.storage.qdrant import QdrantStorage
    except ImportError as exc:
        _logger.warning(
            "Qdrant is the v0.4.0 default but qdrant-client is not installed; "
            "falling back to in-memory backend. Install with "
            "`pip install neuromem-sdk[qdrant]` to enable persistent vector "
            "storage. Cause: %s",
            exc,
        )
        return InMemoryBackend()

    try:
        backend = QdrantStorage(
            host=vs_params.get("host", "localhost"),
            port=vs_params.get("port", 6333),
            collection_name=vs_params.get("collection_name", "neuromem"),
            vector_size=vs_params.get("vector_size", 768),
            api_key=vs_params.get("api_key"),
            path=vs_params.get("path"),
            url=vs_params.get("url"),
        )
    except Exception as exc:
        host = vs_params.get("host", "localhost")
        port = vs_params.get("port", 6333)
        _logger.warning(
            "Qdrant unreachable at %s:%s; falling back to in-memory backend. "
            "Start Qdrant locally with: `docker run -p 6333:6333 qdrant/qdrant`. "
            "Cause: %s",
            host,
            port,
            exc,
        )
        return InMemoryBackend()

    return backend


class NeuroMem:
    """
    Main entry point for the NeuroMem SDK.

    Example:
        >>> memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
        >>> context = memory.retrieve(query="Design a database agent", task_type="system_design")
        >>> memory.observe(user_input="I prefer concise answers", assistant_output="Got it!")
    """

    def __init__(self, user_id: str, controller: MemoryController, config: NeuroMemConfig):
        self.user_id = user_id
        self.controller = controller
        self.config = config
        self._turn_count = 0

    def __del__(self):
        """Gracefully shutdown async workers on cleanup"""
        if hasattr(self, "controller") and self.controller:
            self.controller.shutdown()

    @classmethod
    def from_config(cls, config_path: str, user_id: str):
        """
        Initialize NeuroMem from a configuration file.

        Args:
            config_path: Path to neuromem.yaml configuration file
            user_id: User ID (must be created via UserManager first)

        Returns:
            NeuroMem instance
        """
        from neuromem.storage.memory import InMemoryBackend

        config = NeuroMemConfig(config_path)
        storage_config = config.storage()

        # 1. Determine Vector Store Backend (Primary Storage)
        vector_store_config = storage_config.get("vector_store", {})
        vs_type = vector_store_config.get("type")

        # Backward compatibility / fallback to 'database' key
        if not vs_type:
            db_config = storage_config.get("database", {})
            vs_type = db_config.get("type", "memory")
            vs_params = db_config  # Use the whole dict as params if needed, or specific subkeys
            # Normalize params for old style
            if vs_type == "postgres":
                vs_params = {"url": db_config.get("url")}
            elif vs_type == "sqlite":
                vs_params = {"url": db_config.get("url")}
        else:
            # Use the vector_store config directly as params, or check for a nested 'config' key
            vs_params = vector_store_config.get("config", vector_store_config)

        # Initialize Backend
        if vs_type == "qdrant":
            # v0.4.0: Qdrant is the default. Health-check on startup; on
            # connection failure (service not running, wrong host/port, missing
            # qdrant-client extra), log a clear warning and fall back to the
            # in-memory backend so single-machine "just works" stays true.
            backend = _try_qdrant_or_fallback(vs_params)
        elif vs_type == "postgres":
            from neuromem.storage.postgres import PostgresBackend

            url = vs_params.get("url")
            backend = PostgresBackend(url)
        elif vs_type == "sqlite":
            from neuromem.storage.sqlite import SQLiteBackend

            url = vs_params.get("url")
            backend = SQLiteBackend(url)
        else:
            backend = InMemoryBackend()

        # Initialize memory layers
        episodic = EpisodicMemory(backend, user_id)
        semantic = SemanticMemory(backend, user_id)
        procedural = ProceduralMemory(backend, user_id)

        # Initialize session (RAM only for now as history tracking is disabled)
        session = SessionMemory(backend=None, user_id=user_id)

        # Initialize cognitive engines
        retriever = RetrievalEngine()
        consolidator = Consolidator(
            llm_model=config.model().get("consolidation_llm"), config=config.get("neuromem", {})
        )
        decay_engine = DecayEngine(enabled=config.memory().get("decay_enabled", True))

        # Initialize verbatim store (v0.4.0) — raw text chunks for high-recall retrieval
        verbatim = None
        verbatim_cfg = config.verbatim()
        if verbatim_cfg.get("enabled", True):
            from neuromem.core.verbatim import VerbatimStore

            embedding_model = config.model().get("embedding", "text-embedding-3-large")
            verbatim = VerbatimStore(
                backend=backend,
                user_id=user_id,
                embedding_model=embedding_model,
                chunk_size=verbatim_cfg.get("chunk_size", 800),
                chunk_overlap=verbatim_cfg.get("chunk_overlap", 100),
            )

        # Initialize controller
        controller = MemoryController(
            episodic=episodic,
            semantic=semantic,
            procedural=procedural,
            session=session,
            retriever=retriever,
            consolidator=consolidator,
            decay_engine=decay_engine,
            embedding_model=config.model().get("embedding", "text-embedding-3-large"),
            config=config,
            verbatim=verbatim,
        )

        return cls(user_id=user_id, controller=controller, config=config)

    @classmethod
    def for_langchain(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for LangChain integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance optimized for LangChain

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.langchain import add_memory

            memory = NeuroMem.for_langchain(user_id="user_123")
            chain_with_memory = add_memory(chain, memory)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_langgraph(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for LangGraph integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance optimized for LangGraph

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.langgraph import with_memory

            memory = NeuroMem.for_langgraph(user_id="user_123")
            app = with_memory(graph.compile(), memory)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_mcp(cls, user_id: str = "default", config_path: str = "neuromem.yaml"):
        """
        Quick initialization for MCP server integration.

        Args:
            user_id: User ID (default: "default")
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for MCP server

        Usage:
            python -m neuromem.mcp
            # Or: neuromem-mcp
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_crewai(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for CrewAI integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for CrewAI

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.crewai import create_neuromem_tools

            memory = NeuroMem.for_crewai(user_id="user_123")
            tools = create_neuromem_tools(memory)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_autogen(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for AutoGen (AG2) integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for AutoGen

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.autogen import register_neuromem_tools

            memory = NeuroMem.for_autogen(user_id="user_123")
            register_neuromem_tools(memory, assistant, user_proxy)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_dspy(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for DSPy integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for DSPy

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.dspy import NeuroMemRetriever

            memory = NeuroMem.for_dspy(user_id="user_123")
            retriever = NeuroMemRetriever(memory, k=5)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_haystack(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for Haystack integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for Haystack

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.haystack import NeuroMemRetriever

            memory = NeuroMem.for_haystack(user_id="user_123")
            retriever = NeuroMemRetriever(memory, top_k=5)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_semantic_kernel(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for Semantic Kernel integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for Semantic Kernel

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.semantic_kernel import create_neuromem_plugin

            memory = NeuroMem.for_semantic_kernel(user_id="user_123")
            plugin = create_neuromem_plugin(memory)
        """
        return cls.from_config(config_path, user_id)

    @classmethod
    def for_litellm(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Quick initialization for LiteLLM integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance optimized for LiteLLM

        Usage:
            from neuromem import NeuroMem
            from neuromem.adapters.litellm import completion_with_memory

            memory = NeuroMem.for_litellm(user_id="user_123")
            response = completion_with_memory(
                model="gpt-4",
                messages=[...],
                memory=memory
            )
        """
        return cls.from_config(config_path, user_id)

    # ----------------------------------------------------------------
    # BRAIN SYSTEM (v0.3.0)
    # ----------------------------------------------------------------

    def reinforce(self, memory_id: str, reward: float = 1.0, task_type: str = "chat") -> None:
        """Provide reward feedback for a retrieved memory (TD learning).

        Positive reward (+1.0) increases future retrieval priority for
        similar memories. Negative reward (-1.0) decreases it.
        Requires ``brain.enabled: true`` in config.

        Args:
            memory_id: ID of the memory to reinforce
            reward: Reward signal (-1.0 to 1.0, default: 1.0 = helpful)
            task_type: Task context (e.g., "chat", "code", "planning")
        """
        self.controller.reinforce(memory_id, reward, task_type)

    def get_working_memory(self) -> list:
        """Get memories currently in the prefrontal working memory buffer.

        Returns up to 4 items (Cowan's number) that are in the current
        attention window. Requires ``brain.enabled: true`` in config.

        Returns:
            List of MemoryItem objects in working memory
        """
        return self.controller.get_working_memory()

    def observe_multimodal(
        self,
        text: str = None,
        audio_bytes: bytes = None,
        video_frames: list = None,
        assistant_output: str = "",
        source: str = "text",
    ) -> None:
        """Observe a multimodal interaction and store it in memory.

        Requires ``multimodal.enabled: true`` in config plus optional deps.
        Falls back to text-only observe if multimodal is not available.

        Args:
            text: Text content (always available)
            audio_bytes: Raw audio bytes (PCM/WAV)
            video_frames: List of video frames as numpy arrays
            assistant_output: What the assistant responded
            source: Origin of input ("text", "livekit", "file")
        """
        # For now, fall back to text-only if text is available
        if text:
            self.observe(text, assistant_output)
        else:
            self.observe(
                f"[{source} input: audio={audio_bytes is not None}, video={video_frames is not None}]",
                assistant_output,
            )

    @classmethod
    def for_livekit(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """Quick initialization for LiveKit real-time integration.

        Args:
            user_id: User ID
            config_path: Path to neuromem.yaml

        Returns:
            NeuroMem instance for LiveKit

        Usage:
            from neuromem import NeuroMem
            memory = NeuroMem.for_livekit(user_id="user_123")
            bridge = await memory.connect_livekit(session)
        """
        return cls.from_config(config_path, user_id)

    # ----------------------------------------------------------------
    # RETRIEVAL
    # ----------------------------------------------------------------

    def retrieve(
        self, query: str, task_type: str = "chat", k: int = 8, parallel: bool = True
    ) -> RetrievalResult:
        """
        Retrieve relevant memories for a given query.

        Automatically detects multi-hop queries (e.g., "How do X and Y both...?")
        and decomposes them into sub-queries for targeted retrieval per entity.

        Args:
            query: The query string
            task_type: Type of task (chat, system_design, code_review, etc.)
            k: Number of memories to retrieve
            parallel: Use parallel retrieval (default: True)

        Returns:
            ``RetrievalResult`` wrapping the items list. Iterates as the
            underlying ``list[MemoryItem]`` so existing callers using ``for
            item in memory.retrieve(...)`` and ``list(memory.retrieve(...))``
            continue to work unchanged. v0.4.0+: introduced this wrapper so
            v0.5.0's calibrated abstention (H2-D7) can populate
            ``confidence`` and ``abstained`` without a second breaking
            change.
        """
        embedding = get_embedding(
            query, self.config.model().get("embedding", "text-embedding-3-large")
        )
        items = self.controller.retrieve_multihop(
            query=query,
            embedding=embedding,
            task_type=task_type,
            k=k,
            parallel=parallel,
        )
        return RetrievalResult(items=list(items))

    def retrieve_verbatim_only(
        self,
        query: str,
        k: int = 8,
        bm25_blend: float = 0.5,
        ce_blend: float = 0.9,
        ce_top_k: int = 30,
    ) -> RetrievalResult:
        """
        Deterministic 2-stage retrieval against verbatim chunks only.

        Bypasses the cognitive pipeline (semantic/procedural/episodic, conflict
        detection, brain re-ranking) and returns BM25 + cross-encoder reranked
        results from the verbatim store. Designed for exact-fact retrieval
        benchmarks (MemBench) where cognitive-layer noise hurts precision.

        Requires verbatim.enabled=true in the YAML config.

        Returns ``RetrievalResult`` (v0.4.0+); iterates as the underlying
        items list for backward compatibility.
        """
        embedding = get_embedding(
            query, self.config.model().get("embedding", "text-embedding-3-large")
        )
        items = self.controller.retrieve_verbatim_only(
            embedding=embedding,
            query_text=query,
            k=k,
            bm25_blend=bm25_blend,
            ce_blend=ce_blend,
            ce_top_k=ce_top_k,
        )
        return RetrievalResult(items=list(items))

    def retrieve_with_context(self, query: str, task_type: str = "chat", k: int = 8):
        """
        Retrieve memories with automatic context expansion via graph.

        Like Obsidian's ![[embed]] transclusion — when you retrieve a memory,
        related memories are automatically attached as expanded context.

        Args:
            query: The query string
            task_type: Type of task
            k: Number of memories to retrieve

        Returns:
            List of MemoryItem objects with expanded_context in metadata
        """
        embedding = get_embedding(
            query, self.config.model().get("embedding", "text-embedding-3-large")
        )
        return self.controller.retrieve(
            embedding, task_type, k, expand_context=True, query_text=query
        )

    def observe(
        self,
        user_input: str,
        assistant_output: str,
        template: str = None,
        metadata: dict = None,
        max_content_length: int = 50000,
    ):
        """
        Observe a user-assistant interaction and store it in memory.

        Args:
            user_input: What the user said
            assistant_output: What the assistant responded
            template: Optional template name (decision, preference, fact, goal, feedback).
                      If None, auto-detects from content.
            metadata: Optional extra metadata to store with the memory
                      (e.g., session_id, corpus_id, timestamp).
            max_content_length: Per-field character cap. Defaults to 50 KB. Benchmark
                      adapters ingesting long-haystack docs should raise this.
        """
        # Apply template if specified or auto-detected
        if template or True:  # Always try template detection
            from neuromem.memory.templates import apply_template, detect_template

            if template is None:
                template = detect_template(user_input)

            if template != "general":
                apply_template(template, user_input, assistant_output)
                # Template modifies content format and adds metadata
                # But we still call observe with original inputs for validation
                # Template tags/metadata will be handled in the next consolidation
                pass  # Template detection runs but doesn't block core observe

        self.controller.observe(
            user_input,
            assistant_output,
            self.user_id,
            extra_metadata=metadata,
            max_content_length=max_content_length,
        )
        self._turn_count += 1

        # Trigger consolidation if needed
        consolidation_interval = self.config.memory().get("consolidation_interval", 10)
        if self._turn_count % consolidation_interval == 0:
            self.consolidate()

    def consolidate(self):
        """
        Trigger memory consolidation (episodic → semantic/procedural).
        This is typically called automatically but can be triggered manually.
        """
        self.controller.consolidate()

    def list(self, memory_type: str = None, limit: int = 50):
        """
        List all memories for the user.

        Args:
            memory_type: Filter by memory type (episodic, semantic, procedural)
            limit: Maximum number of memories to return

        Returns:
            List of MemoryItem objects
        """
        return self.controller.list_memories(memory_type, limit)

    def explain(self, memory_id: str):
        """
        Explain why a memory was retrieved and how it's being used.

        Args:
            memory_id: ID of the memory to explain

        Returns:
            Dictionary with explanation details
        """
        return self.controller.explain(memory_id)

    def update(self, memory_id: str, content: str):
        """
        Update a memory's content.

        Args:
            memory_id: ID of the memory to update
            content: New content
        """
        self.controller.update_memory(memory_id, content)

    def forget(self, memory_id: str):
        """
        Delete a memory.

        Args:
            memory_id: ID of the memory to delete
        """
        self.controller.forget_memory(memory_id)

    def search(self, query_string: str, k: int = 10) -> list:
        """
        Search memories with Obsidian-like query syntax.

        Syntax:
            type:semantic tag:preference confidence:>0.8 python frameworks
            after:2024-01-01 before:2024-12-31 "exact phrase"
            intent:question sentiment:positive

        Args:
            query_string: Structured query string
            k: Max results

        Returns:
            List of matching MemoryItem objects
        """
        from neuromem.core.query import MemoryQuery

        query = MemoryQuery(query_string)

        if query.text_query:
            # Embedding search + filter
            embedding = get_embedding(
                query.text_query,
                self.config.model().get("embedding", "text-embedding-3-large"),
            )
            candidates = self.controller.retrieve(
                embedding, "search", k * 3, query_text=query.text_query
            )
        else:
            # Filter-only search
            candidates = self.controller.list_memories(
                memory_type=query.filters.get("memory_type"), limit=k * 3
            )

        # Apply structured filters
        results = [m for m in candidates if query.matches_memory(m)]
        return results[:k]

    def daily_summary(self, date=None) -> dict:
        """Get daily memory summary (defaults to today). Accepts str ('YYYY-MM-DD'), date, or datetime."""
        from neuromem.memory.summaries import TemporalSummarizer

        if date is None:
            date = datetime.now(timezone.utc)
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        memories = self.controller.get_memories_by_date(date)
        return TemporalSummarizer().daily_summary(memories, date)

    def weekly_digest(self, week_start=None) -> dict:
        """Get weekly memory digest. Accepts str ('YYYY-MM-DD'), date, or datetime."""
        from neuromem.memory.summaries import TemporalSummarizer
        from datetime import timedelta

        if week_start is None:
            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=now.weekday())
        elif isinstance(week_start, str):
            week_start = datetime.strptime(week_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        week_end = week_start + timedelta(days=7)
        memories = self.controller.get_memories_in_range(week_start, week_end)
        return TemporalSummarizer().weekly_digest(memories, week_start)

    def find_by_tags(self, tag_prefix: str, limit: int = 50) -> list:
        """
        Find memories matching a tag prefix (hierarchical).

        Like Obsidian's tag search:
          'topic:' -> all topic-tagged memories
          'topic:ai' -> topic:ai, topic:ai/memory

        Args:
            tag_prefix: Tag prefix to match
            limit: Maximum results
        """
        return self.controller.find_by_tags(tag_prefix, limit=limit)

    def get_tag_tree(self) -> dict:
        """Get all tags as a hierarchy with counts."""
        return self.controller.get_tag_tree()

    def get_memories_by_date(self, date=None) -> list:
        """Get all memories from a specific date (defaults to today)."""
        if date is None:
            date = datetime.now(timezone.utc)
        return self.controller.get_memories_by_date(date)

    def get_memories_in_range(self, start, end, memory_type: str = None) -> list:
        """Get memories within a date range."""
        return self.controller.get_memories_in_range(start, end, memory_type)

    def get_graph(self) -> dict:
        """Export the memory relationship graph as {nodes, edges}."""
        return self.controller.graph.export()

    def get_context(
        self,
        max_level: int = 1,
        topic: str = "",
        query: str = "",
    ) -> dict:
        """
        Load layered context for efficient memory retrieval.

        Levels:
            0 — Identity (~100 tokens, always loaded)
            1 — Essential facts (~500-800 tokens, top-15 by salience)
            2 — On-demand topic-filtered retrieval
            3 — Deep semantic search (full pipeline)

        Args:
            max_level: Maximum context level to load (0-3)
            topic: Topic filter for L2 (e.g., "career", "health")
            query: Query string for L3 deep search

        Returns:
            Dict with 'text', 'token_estimate', and 'layers' list
        """
        from neuromem.core.context_layers import ContextManager

        ctx_mgr = ContextManager(self.controller, self.user_id)
        context = ctx_mgr.load(max_level=max_level, topic=topic, query=query)
        return {
            "text": context.full_text,
            "token_estimate": context.total_tokens,
            "layers": [
                {
                    "level": layer.level,
                    "name": layer.name,
                    "token_estimate": layer.token_estimate,
                }
                for layer in context.layers
            ],
        }

    def close(self):
        """Close the memory system and release resources."""
        if hasattr(self.controller, "episodic") and hasattr(self.controller.episodic, "backend"):
            if hasattr(self.controller.episodic.backend, "close"):
                self.controller.episodic.backend.close()


__all__ = [
    "NeuroMem",
    "NeuroMemConfig",
    "User",
    "UserManager",
    "MemoryItem",
    "MemoryType",
    "BeliefState",
    "RetrievalResult",
    "MemoryController",
    "RetrievalEngine",
    "Consolidator",
    "DecayEngine",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "SessionMemory",
    "MemoryBackend",
]

__version__ = "0.4.6"
