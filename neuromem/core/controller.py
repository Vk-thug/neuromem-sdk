"""
Memory controller - the "prefrontal cortex" of NeuroMem.

Orchestrates all memory operations and coordinates between different
memory systems.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.core.retrieval import RetrievalEngine
from neuromem.core.consolidation import Consolidator
from neuromem.core.decay import DecayEngine
from neuromem.memory.episodic import EpisodicMemory
from neuromem.memory.semantic import SemanticMemory
from neuromem.memory.procedural import ProceduralMemory
from neuromem.memory.session import SessionMemory
from neuromem.utils.embeddings import get_embedding


class MemoryController:
    """
    Central controller for all memory operations.
    
    This is the "executive function" that:
    - Decides what to remember
    - Retrieves relevant memories
    - Triggers consolidation
    - Manages decay
    - Provides explainability
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
        config: Optional[Any] = None
    ):
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.session = session
        self.retriever = retriever
        self.consolidator = consolidator
        self.decay_engine = decay_engine
        self.embedding_model = embedding_model
        self.config = config
        
        # Cache for explanations
        self._retrieval_cache: Dict[str, Dict[str, Any]] = {}
    
    def retrieve(
        self,
        embedding: List[float],
        task_type: str,
        k: int = 8
    ) -> List[MemoryItem]:
        """
        Retrieve relevant memories for a query.
        
        Args:
            embedding: Query embedding vector
            task_type: Type of task (chat, system_design, etc.)
            k: Number of memories to retrieve
        
        Returns:
            List of relevant memory items
        """
        # Retrieve from semantic and procedural (long-term memory)
        filters = {"memory_type": [MemoryType.SEMANTIC.value, MemoryType.PROCEDURAL.value]}
        
        semantic_items, semantic_sims = self.semantic.retrieve(embedding, filters, k * 2)
        procedural_items, procedural_sims = self.procedural.retrieve(embedding, {}, k)

        # Retrieve from episodic (recent interactions)
        episodic_filters = {"memory_type": MemoryType.EPISODIC.value}
        episodic_items, episodic_sims = self.episodic.retrieve(embedding, episodic_filters, k)
        
        # Combine and rank
        all_items = semantic_items + procedural_items + episodic_items
        all_sims = semantic_sims + procedural_sims + episodic_sims
        
        if not all_items:
            return []
        
        # Check if hybrid retrieval is enabled
        use_hybrid = self.config and self.config.retrieval().get("hybrid_enabled", False)
        
        if use_hybrid:
            # Use hybrid retrieval with multi-factor ranking
            try:
                from neuromem.memory.hybrid_retrieval import HybridRetrieval
                
                retrieval_config = self.config.retrieval()
                hybrid_retriever = HybridRetrieval(
                    recency_weight=retrieval_config.get("recency_weight", 0.2),
                    importance_weight=retrieval_config.get("importance_weight", 0.3),
                    similarity_weight=retrieval_config.get("similarity_weight", 0.5),
                    recency_half_life_days=retrieval_config.get("recency_half_life_days", 30)
                )
                
                top_items = hybrid_retriever.retrieve(embedding, all_items, all_sims, k=k)
            except Exception as e:
                print(f"Warning: Hybrid retrieval failed, falling back to basic: {e}")
                # Fallback to basic retrieval
                ranked = self.retriever.rank(all_items, all_sims)
                diverse = self.retriever.apply_inhibition(ranked)
                filtered = self.retriever.filter_by_confidence(diverse)
                top_items = [item for item, score in filtered[:k]]
        else:
            # Use basic retrieval
            ranked = self.retriever.rank(all_items, all_sims)
            diverse = self.retriever.apply_inhibition(ranked)
            filtered = self.retriever.filter_by_confidence(diverse)
            top_items = [item for item, score in filtered[:k]]
        
        # Reinforce accessed memories
        for item in top_items:
            self.decay_engine.reinforce(item)
            # Cache retrieval info for explainability
            item_idx = all_items.index(item) if item in all_items else 0
            self._retrieval_cache[item.id] = {
                "similarity": all_sims[item_idx] if item_idx < len(all_sims) else 0.0,
                "score": getattr(item, 'score', 0.0),
                "retrieved_at": datetime.utcnow()
            }
        
        return top_items
    
    def observe(self, user_input: str, assistant_output: str, user_id: str):
        """
        Observe and store a user-assistant interaction.
        
        Args:
            user_input: What the user said
            assistant_output: What the assistant responded
            user_id: User ID
        """
        # Create episodic memory for the interaction
        content = f"User: {user_input}\nAssistant: {assistant_output}"
        embedding = get_embedding(content, self.embedding_model)
        
        # Auto-tag the memory if enabled
        tags = []
        metadata = {}
        
        if self.config and self.config.tagging().get("auto_tag_enabled", False):
            try:
                from neuromem.utils.auto_tagger import AutoTagger
                
                tagger = AutoTagger(
                    llm_model=self.config.model().get("consolidation_llm", "gpt-4o-mini")
                )
                enrichment = tagger.enrich_memory(content)
                
                tags = enrichment.get('tags', [])
                metadata = {
                    'intent': enrichment.get('intent'),
                    'sentiment': enrichment.get('sentiment', {}).get('sentiment'),
                    'entities': enrichment.get('entities', [])
                }
            except Exception as e:
                print(f"Warning: Auto-tagging failed: {e}")
        
        memory_item = MemoryItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            embedding=embedding,
            memory_type=MemoryType.EPISODIC,
            salience=self._calculate_salience(user_input, assistant_output),
            confidence=0.9,  # Direct observations have high confidence
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            decay_rate=0.05,  # Episodic memories decay faster
            reinforcement=1,
            inferred=False,  # Direct observation
            editable=True,
            tags=tags,
            metadata=metadata
        )
        
        self.episodic.store(memory_item)
        
        # Also add to session memory
        self.session.add_turn(user_input, assistant_output)
    
    def consolidate(self):
        """
        Trigger memory consolidation.
        
        This promotes episodic memories to semantic/procedural based on patterns.
        """
        # Get episodic memories ready for consolidation
        episodic_items = self.episodic.get_all()
        candidates = self.decay_engine.schedule_consolidation(episodic_items)
        
        if not candidates:
            return
        
        # Get existing semantic and procedural memories
        semantic_items = self.semantic.get_all()
        procedural_items = self.procedural.get_all()
        
        # Perform consolidation
        result = self.consolidator.consolidate(
            candidates,
            semantic_items,
            procedural_items
        )
        
        # Store promoted memories
        for memory in result.new_semantic_memories:
            # Generate embedding if missing
            if not memory.embedding:
                try:
                    memory.embedding = get_embedding(memory.content, self.embedding_model)
                except Exception as e:
                    print(f"Warning: Failed to generate embedding for semantic memory: {e}")
                    continue
            
            # Ensure semantic type compliance
            if memory.memory_type != MemoryType.SEMANTIC:
                memory.memory_type = MemoryType.SEMANTIC
                
            self.semantic.store(memory)
        
        for memory in result.new_procedural_memories:
            # Generate embedding if missing
            if not memory.embedding:
                try:
                    memory.embedding = get_embedding(memory.content, self.embedding_model)
                except Exception as e:
                    print(f"Warning: Failed to generate embedding for procedural memory: {e}")
                    continue
            self.procedural.store(memory)
        
        # Apply decay to episodic memories
        active, forgotten = self.decay_engine.apply_decay(episodic_items)
        
        # Remove forgotten memories
        for item in forgotten:
            self.episodic.delete(item.id)
    
    def list_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 50
    ) -> List[MemoryItem]:
        """
        List memories for the user.
        
        Args:
            memory_type: Filter by type (episodic, semantic, procedural)
            limit: Maximum number to return
        
        Returns:
            List of memory items
        """
        all_memories = []
        
        if memory_type is None or memory_type == "episodic":
            all_memories.extend(self.episodic.get_all()[:limit])
        
        if memory_type is None or memory_type == "semantic":
            all_memories.extend(self.semantic.get_all()[:limit])
        
        if memory_type is None or memory_type == "procedural":
            all_memories.extend(self.procedural.get_all()[:limit])
        
        return all_memories[:limit]
    
    def explain(self, memory_id: str) -> Dict[str, Any]:
        """
        Explain why a memory was retrieved.
        
        Args:
            memory_id: ID of the memory
        
        Returns:
            Explanation dictionary
        """
        # Find the memory
        memory = None
        for mem_type in [self.episodic, self.semantic, self.procedural]:
            memory = mem_type.get_by_id(memory_id)
            if memory:
                break
        
        if not memory:
            return {"error": "Memory not found"}
        
        # Get retrieval info from cache
        retrieval_info = self._retrieval_cache.get(memory_id, {})
        
        return {
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "why_used": {
                "similarity": retrieval_info.get("similarity", "N/A"),
                "salience": memory.salience,
                "confidence": memory.confidence,
                "reinforcement": memory.reinforcement,
                "final_score": retrieval_info.get("score", "N/A")
            },
            "source": "inferred" if memory.inferred else "explicit",
            "created_at": memory.created_at.isoformat(),
            "last_accessed": memory.last_accessed.isoformat(),
            "retention_days": self.decay_engine.get_retention_period(memory)
        }
    
    def update_memory(self, memory_id: str, content: str):
        """
        Update a memory's content.
        
        Args:
            memory_id: ID of the memory
            content: New content
        """
        # Find and update the memory
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
        """
        Delete a memory.
        
        Args:
            memory_id: ID of the memory to delete
        """
        # Try to delete from each memory type
        for mem_type in [self.episodic, self.semantic, self.procedural]:
            if mem_type.delete(memory_id):
                return
        
        raise ValueError("Memory not found")
    
    def _calculate_salience(self, user_input: str, assistant_output: str) -> float:
        """
        Calculate how salient/important an interaction is.
        
        Heuristics:
        - Questions are more salient
        - Longer interactions are more salient
        - Emotional content is more salient
        """
        salience = 0.5  # Base salience
        
        # Check for questions
        if "?" in user_input:
            salience += 0.2
        
        # Check for length (more detail = more important)
        if len(user_input) > 100:
            salience += 0.1
        
        # Check for preference/style indicators
        preference_keywords = ["prefer", "like", "want", "need", "always", "never"]
        if any(keyword in user_input.lower() for keyword in preference_keywords):
            salience += 0.2
        
        return min(salience, 1.0)
