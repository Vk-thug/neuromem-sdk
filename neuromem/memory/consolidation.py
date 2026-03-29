"""
Memory consolidation engine for NeuroMem.

Implements brain-inspired memory consolidation:
- Extract semantic facts from episodic memories
- Summarize conversations to reduce storage
- Merge duplicate/similar facts
- Apply temporal decay and forgetting
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from neuromem.core.types import MemoryItem
from neuromem.utils.time import ensure_utc

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None  # type: ignore
    OPENAI_AVAILABLE = False


class ConsolidationEngine:
    """
    Brain-inspired memory consolidation engine.
    
    Mimics how the human brain consolidates memories during sleep:
    - Extracts important facts from episodic memories
    - Creates summaries instead of storing full conversations
    - Merges similar memories
    - Applies forgetting curves to low-importance items
    """
    
    def __init__(self, llm_model: str = "gpt-4o-mini", min_confidence: float = 0.7):
        """
        Initialize consolidation engine.
        
        Args:
            llm_model: LLM model to use for fact extraction and summarization
            min_confidence: Minimum confidence threshold for extracted facts
        """
        self.llm_model = llm_model
        self.min_confidence = min_confidence
    
    def extract_facts(self, memories: List[MemoryItem]) -> List[Dict[str, Any]]:
        """
        Extract semantic facts from episodic memories.
        
        Args:
            memories: List of episodic memory items
        
        Returns:
            List of extracted facts with metadata
        """
        if not memories:
            return []
        
        # Combine memory content for batch processing
        conversation_text = "\n\n".join([
            f"[{mem.created_at}] {mem.content}" 
            for mem in memories
        ])
        
        # Use LLM to extract facts
        prompt = f"""Analyze the following conversation and extract key semantic facts about the user.

Focus on:
- User preferences (what they like/dislike)
- User knowledge (what they know)
- User skills (what they can do)
- User goals (what they want to achieve)
- Important attributes or characteristics

Conversation:
{conversation_text}

Extract facts in JSON format:
[
  {{
    "fact_type": "preference|knowledge|skill|goal|attribute",
    "fact": "concise statement of the fact",
    "confidence": 0.0-1.0,
    "tags": ["relevant", "tags"]
  }}
]

Only include facts with confidence >= {self.min_confidence}.
Return ONLY the JSON array, no other text."""

        if not OPENAI_AVAILABLE:
            return []

        try:
            response = openai.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a memory consolidation system that extracts semantic facts from conversations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            facts_json = response.choices[0].message.content.strip()
            # Remove markdown code blocks if present
            if facts_json.startswith("```"):
                facts_json = facts_json.split("```")[1]
                if facts_json.startswith("json"):
                    facts_json = facts_json[4:]

            facts = json.loads(facts_json)

            # Add metadata
            source_ids = [str(mem.id) for mem in memories]
            for fact in facts:
                fact['source_memory_ids'] = source_ids
                fact['created_at'] = datetime.now(timezone.utc)
                fact['last_reinforced'] = datetime.now(timezone.utc)
                fact['reinforcement_count'] = 1

            return facts

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error extracting facts: {e}")
            return []
    
    def summarize_conversation(
        self, 
        memories: List[MemoryItem],
        max_summary_length: int = 200
    ) -> Optional[Dict[str, Any]]:
        """
        Create a concise summary of a conversation.
        
        Args:
            memories: List of memory items from a conversation
            max_summary_length: Maximum length of summary
        
        Returns:
            Summary dict with key points and metadata
        """
        if not memories:
            return None
        
        conversation_text = "\n\n".join([mem.content for mem in memories])
        
        prompt = f"""Summarize the following conversation in {max_summary_length} characters or less.

Also extract:
- 3-5 topic tags
- 3-5 key points (bullet points)
- Salience score (0.0-1.0) indicating importance

Conversation:
{conversation_text}

Return JSON:
{{
  "summary": "concise summary",
  "topic_tags": ["tag1", "tag2"],
  "key_points": ["point1", "point2"],
  "salience": 0.0-1.0
}}"""

        if not OPENAI_AVAILABLE:
            return None

        try:
            response = openai.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a memory consolidation system that creates concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            summary_json = response.choices[0].message.content.strip()
            if summary_json.startswith("```"):
                summary_json = summary_json.split("```")[1]
                if summary_json.startswith("json"):
                    summary_json = summary_json[4:]

            summary = json.loads(summary_json)

            # Add metadata
            summary['start_time'] = min(mem.created_at for mem in memories)
            summary['end_time'] = max(mem.created_at for mem in memories)
            summary['message_count'] = len(memories)

            return summary

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error summarizing conversation: {e}")
            return None
    
    def merge_similar_facts(
        self, 
        facts: List[Dict[str, Any]],
        similarity_threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Merge similar or duplicate facts.
        
        Args:
            facts: List of facts to merge
            similarity_threshold: Threshold for considering facts similar
        
        Returns:
            Deduplicated list of facts
        """
        if len(facts) <= 1:
            return facts
        
        # Group by fact_type first
        grouped = {}
        for fact in facts:
            fact_type = fact.get('fact_type', 'unknown')
            if fact_type not in grouped:
                grouped[fact_type] = []
            grouped[fact_type].append(fact)
        
        merged = []
        
        for fact_type, type_facts in grouped.items():
            # Simple deduplication based on exact text match
            # In production, you'd use embedding similarity
            seen_facts = {}
            
            for fact in type_facts:
                fact_text = fact['fact'].lower().strip()
                
                if fact_text in seen_facts:
                    # Merge: increase confidence and reinforcement
                    existing = seen_facts[fact_text]
                    existing['confidence'] = min(1.0, existing['confidence'] + 0.1)
                    existing['reinforcement_count'] += 1
                    existing['source_memory_ids'].extend(fact.get('source_memory_ids', []))
                else:
                    seen_facts[fact_text] = fact
            
            merged.extend(seen_facts.values())
        
        return merged
    
    def apply_decay(
        self, 
        memories: List[MemoryItem],
        decay_threshold: float = 0.3
    ) -> List[str]:
        """
        Apply temporal decay and identify memories to prune.
        
        Args:
            memories: List of memory items
            decay_threshold: Threshold below which memories are pruned
        
        Returns:
            List of memory IDs to delete
        """
        to_delete = []
        now = datetime.now(timezone.utc)

        for mem in memories:
            # Calculate age in days
            age_days = (now - ensure_utc(mem.created_at)).days
            
            # Apply decay formula: importance = salience * e^(-decay_rate * age)
            import math
            decayed_importance = mem.salience * math.exp(-mem.decay_rate * age_days)
            
            # Boost by reinforcement
            reinforcement_boost = min(0.3, mem.reinforcement * 0.05)
            final_importance = decayed_importance + reinforcement_boost
            
            # Mark for deletion if below threshold
            if final_importance < decay_threshold:
                to_delete.append(str(mem.id))
        
        return to_delete
    
    def consolidate_batch(
        self,
        episodic_memories: List[MemoryItem],
        extract_facts: bool = True,
        create_summaries: bool = True,
        apply_forgetting: bool = True
    ) -> Dict[str, Any]:
        """
        Run full consolidation on a batch of memories.
        
        Args:
            episodic_memories: Episodic memories to consolidate
            extract_facts: Whether to extract semantic facts
            create_summaries: Whether to create summaries
            apply_forgetting: Whether to apply decay and pruning
        
        Returns:
            Consolidation results
        """
        results = {
            'facts_extracted': [],
            'summaries_created': [],
            'memories_to_delete': [],
            'stats': {
                'input_memories': len(episodic_memories),
                'facts_count': 0,
                'summaries_count': 0,
                'deleted_count': 0
            }
        }
        
        # Extract facts
        if extract_facts and episodic_memories:
            facts = self.extract_facts(episodic_memories)
            facts = self.merge_similar_facts(facts)
            results['facts_extracted'] = facts
            results['stats']['facts_count'] = len(facts)
        
        # Create summaries
        if create_summaries and episodic_memories:
            summary = self.summarize_conversation(episodic_memories)
            if summary:
                results['summaries_created'] = [summary]
                results['stats']['summaries_count'] = 1
        
        # Apply forgetting
        if apply_forgetting:
            to_delete = self.apply_decay(episodic_memories)
            results['memories_to_delete'] = to_delete
            results['stats']['deleted_count'] = len(to_delete)
        
        return results
