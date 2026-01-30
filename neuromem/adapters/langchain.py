"""
LangChain adapter for NeuroMem.

Provides seamless integration with LangChain's memory interface.
"""

from typing import List, Dict, Any
from neuromem import NeuroMem


class LangChainMemoryAdapter:
    """
    Adapter to make NeuroMem compatible with LangChain's memory interface.
    
    This allows NeuroMem to be used as a drop-in replacement for
    LangChain's built-in memory systems.
    
    Example:
        >>> memory = NeuroMem.for_langchain(user_id="user_123")
        >>> chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
    """
    
    def __init__(self, neuromem: NeuroMem):
        """
        Initialize the adapter.
        
        Args:
            neuromem: NeuroMem instance
        """
        self.neuromem = neuromem
        self.memory_key = "history"
        self.input_key = "input"
        self.output_key = "output"
    
    @property
    def memory_variables(self) -> List[str]:
        """Return memory variables."""
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load memory variables for LangChain.
        
        Args:
            inputs: Input dictionary
        
        Returns:
            Dictionary with memory context
        """
        # Get the query
        query = inputs.get(self.input_key, "")
        
        # Retrieve relevant memories
        memories = self.neuromem.retrieve(query=query, task_type="chat", k=5)
        
        # Format memories as context
        context_parts = []
        for memory in memories:
            context_parts.append(f"- {memory.content}")
        
        context = "\n".join(context_parts) if context_parts else "No relevant context."
        
        return {self.memory_key: context}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        Save interaction to memory.
        
        Args:
            inputs: Input dictionary
            outputs: Output dictionary
        """
        user_input = inputs.get(self.input_key, "")
        assistant_output = outputs.get(self.output_key, "")
        
        if user_input and assistant_output:
            self.neuromem.observe(user_input, assistant_output)
    
    def clear(self) -> None:
        """Clear session memory (not persistent memory)."""
        # Only clear session, not persistent memories
        self.neuromem.controller.session.clear()
