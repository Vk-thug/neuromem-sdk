"""
Memory decay engine for NeuroMem.

Implements forgetting curves and memory decay, similar to how human
memories fade over time without reinforcement.
"""

import math
from datetime import datetime, timedelta
from typing import List
from neuromem.core.types import MemoryItem


class DecayEngine:
    """
    Manages memory decay and forgetting.
    
    Implements Ebbinghaus forgetting curve:
    - Memories decay exponentially over time
    - Reinforcement slows decay
    - High-salience memories decay slower
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize the decay engine.
        
        Args:
            enabled: Whether decay is enabled (default: True)
        """
        self.enabled = enabled
    
    def calculate_decay(self, item: MemoryItem) -> float:
        """
        Calculate the current strength of a memory based on decay.
        
        Uses the Ebbinghaus forgetting curve:
        strength = e^(-decay_rate * time)
        
        Args:
            item: Memory item to calculate decay for
        
        Returns:
            Current memory strength (0.0-1.0)
        """
        if not self.enabled:
            return 1.0
        
        # Time since last access in days
        time_delta = datetime.utcnow() - item.last_accessed
        days = time_delta.total_seconds() / 86400.0
        
        # Adjust decay rate based on reinforcement
        # More reinforced memories decay slower
        adjusted_decay_rate = item.decay_rate / (1 + math.log(1 + item.reinforcement))
        
        # Adjust for salience - important memories decay slower
        adjusted_decay_rate *= (1 - item.salience * 0.5)
        
        # Calculate strength using exponential decay
        strength = math.exp(-adjusted_decay_rate * days)
        
        return max(strength, 0.0)
    
    def should_forget(
        self,
        item: MemoryItem,
        threshold: float = 0.1
    ) -> bool:
        """
        Determine if a memory should be forgotten.
        
        Args:
            item: Memory item to check
            threshold: Strength threshold below which to forget (default: 0.1)
        
        Returns:
            True if memory should be forgotten
        """
        if not self.enabled:
            return False
        
        strength = self.calculate_decay(item)
        return strength < threshold
    
    def apply_decay(
        self,
        items: List[MemoryItem],
        forget_threshold: float = 0.1
    ) -> tuple[List[MemoryItem], List[MemoryItem]]:
        """
        Apply decay to a list of memories and separate active from forgotten.
        
        Args:
            items: List of memory items
            forget_threshold: Strength threshold for forgetting
        
        Returns:
            Tuple of (active_memories, forgotten_memories)
        """
        active = []
        forgotten = []
        
        for item in items:
            if self.should_forget(item, forget_threshold):
                forgotten.append(item)
            else:
                active.append(item)
        
        return active, forgotten
    
    def reinforce(self, item: MemoryItem) -> MemoryItem:
        """
        Reinforce a memory (called when accessed).
        
        This updates:
        - last_accessed timestamp
        - reinforcement count
        
        Args:
            item: Memory item to reinforce
        
        Returns:
            Updated memory item
        """
        item.last_accessed = datetime.utcnow()
        item.reinforcement += 1
        return item
    
    def get_retention_period(self, item: MemoryItem, strength_threshold: float = 0.5) -> int:
        """
        Calculate how many days until a memory decays below a threshold.
        
        Args:
            item: Memory item
            strength_threshold: Strength threshold (default: 0.5)
        
        Returns:
            Number of days until memory decays below threshold
        """
        if not self.enabled:
            return 999999  # Effectively infinite
        
        # Adjust decay rate
        adjusted_decay_rate = item.decay_rate / (1 + math.log(1 + item.reinforcement))
        adjusted_decay_rate *= (1 - item.salience * 0.5)
        
        # Solve for time: strength_threshold = e^(-decay_rate * time)
        # time = -ln(strength_threshold) / decay_rate
        if adjusted_decay_rate > 0:
            days = -math.log(strength_threshold) / adjusted_decay_rate
            return int(days)
        else:
            return 999999
    
    def schedule_consolidation(
        self,
        episodic_items: List[MemoryItem],
        days_threshold: float = 0
    ) -> List[MemoryItem]:
        """
        Identify episodic memories that should be considered for consolidation.
        
        Args:
            episodic_items: List of episodic memories
            days_threshold: Age threshold in days (default: 7)
        
        Returns:
            List of memories ready for consolidation
        """
        threshold_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        candidates = [
            item for item in episodic_items
            if item.created_at < threshold_date
            and not self.should_forget(item)  # Must still be strong enough
        ]
        
        return candidates
