"""
NeuroMem SDK - Brain-Inspired Memory System for LangChain & LangGraph Agents

A human-inspired, multi-layer memory system that enables LLM agents to:
- Remember experiences (episodic)
- Learn stable facts (semantic)
- Adapt to user thinking style (procedural)
- Forget and correct over time
- Retrieve memories based on goal, salience, and context
"""

from neuromem.config import NeuroMemConfig
from neuromem.user import User, UserManager
from neuromem.core.controller import MemoryController
from neuromem.core.retrieval import RetrievalEngine
from neuromem.core.consolidation import Consolidator
from neuromem.core.decay import DecayEngine
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.memory.episodic import EpisodicMemory
from neuromem.memory.semantic import SemanticMemory
from neuromem.memory.procedural import ProceduralMemory
from neuromem.memory.session import SessionMemory
from neuromem.storage.base import MemoryBackend
from neuromem.utils.embeddings import get_embedding


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
        from neuromem.storage.postgres import PostgresBackend
        from neuromem.storage.sqlite import SQLiteBackend
        from neuromem.storage.memory import InMemoryBackend
        
        config = NeuroMemConfig(config_path)
        
        # Initialize storage backend
        storage_config = config.storage()
        db_type = storage_config.get("database", {}).get("type", "memory")
        
        if db_type == "postgres":
            backend = PostgresBackend(storage_config["database"]["url"])
        elif db_type == "sqlite":
            backend = SQLiteBackend(storage_config["database"]["url"])
        else:
            backend = InMemoryBackend()
        
        # Initialize memory layers
        episodic = EpisodicMemory(backend, user_id)
        semantic = SemanticMemory(backend, user_id)
        procedural = ProceduralMemory(backend, user_id)
        session = SessionMemory()
        
        # Initialize cognitive engines
        retriever = RetrievalEngine()
        consolidator = Consolidator(config.model().get("consolidation_llm"))
        decay_engine = DecayEngine(enabled=config.memory().get("decay_enabled", True))
        
        # Initialize controller
        controller = MemoryController(
            episodic=episodic,
            semantic=semantic,
            procedural=procedural,
            session=session,
            retriever=retriever,
            consolidator=consolidator,
            decay_engine=decay_engine
        )
        
        return cls(user_id=user_id, controller=controller, config=config)
    
    def retrieve(self, query: str, task_type: str = "chat", k: int = 8):
        """
        Retrieve relevant memories for a given query.
        
        Args:
            query: The query string
            task_type: Type of task (chat, system_design, code_review, etc.)
            k: Number of memories to retrieve
        
        Returns:
            List of MemoryItem objects
        """
        embedding = get_embedding(query, self.config.model().get("embedding", "text-embedding-3-large"))
        return self.controller.retrieve(embedding, task_type, k)
    
    def observe(self, user_input: str, assistant_output: str):
        """
        Observe a user-assistant interaction and store it in memory.
        
        Args:
            user_input: What the user said
            assistant_output: What the assistant responded
        """
        self.controller.observe(user_input, assistant_output, self.user_id)
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
    
    def close(self):
        """
        Close the memory system and release resources (e.g., database connections).
        """
        if hasattr(self.controller, 'episodic') and hasattr(self.controller.episodic, 'backend'):
            if hasattr(self.controller.episodic.backend, 'close'):
                self.controller.episodic.backend.close()
    
    @classmethod
    def for_langchain(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Create a NeuroMem instance optimized for LangChain integration.
        
        Args:
            user_id: User ID
            config_path: Path to configuration file
        
        Returns:
            NeuroMem instance with LangChain adapter
        """
        from neuromem.adapters.langchain import LangChainMemoryAdapter
        
        memory = cls.from_config(config_path, user_id)
        return LangChainMemoryAdapter(memory)
    
    @classmethod
    def for_langgraph(cls, user_id: str, config_path: str = "neuromem.yaml"):
        """
        Create a NeuroMem instance optimized for LangGraph integration.
        
        Args:
            user_id: User ID
            config_path: Path to configuration file
        
        Returns:
            NeuroMem instance
        """
        return cls.from_config(config_path, user_id)


__all__ = [
    "NeuroMem",
    "NeuroMemConfig",
    "User",
    "UserManager",
    "MemoryItem",
    "MemoryType",
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

__version__ = "0.1.0"
