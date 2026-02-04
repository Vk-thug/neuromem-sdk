"""
Enhanced LangChain adapter for NeuroMem with automatic memory handling.

This adapter automatically:
1. Retrieves relevant memories before LLM call (pre-processor)
2. Adds memory context to system prompt
3. Stores conversations after LLM call (post-processor)
"""

from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage


class NeuroMemLangChain:
    """
    Enhanced LangChain adapter that automatically handles memory.
    
    Usage:
        memory_adapter = NeuroMemLangChain(neuromem_instance)
        response = memory_adapter.chat(llm, "user message")
    """
    
    def __init__(self, neuromem, k: int = 5):
        """
        Initialize the adapter.
        
        Args:
            neuromem: NeuroMem instance
            k: Number of memories to retrieve
        """
        self.neuromem = neuromem
        self.k = k
    
    def chat(self, llm, user_input: str, system_prompt: Optional[str] = None) -> str:
        """
        Chat with automatic memory handling.
        
        This method:
        1. Retrieves relevant memories
        2. Adds them to system prompt
        3. Calls LLM
        4. Stores the conversation
        5. Returns the response
        
        Args:
            llm: LangChain LLM instance
            user_input: User's message
            system_prompt: Optional custom system prompt
        
        Returns:
            Assistant's response
        """
        # 1. Retrieve memories (pre-processor)
        try:
            memories = self.neuromem.retrieve(
                query=user_input,
                task_type="chat",
                k=self.k
            )
            
            if memories:
                context = "\n".join([f"- {m.content}" for m in memories])
                context_instruction = f"Here's what you know about the user:\n{context}"
            else:
                context_instruction = "This is a new conversation with no prior context."
        except Exception as e:
            print(f"Warning: Memory retrieval failed: {e}")
            context_instruction = "This is a new conversation with no prior context."
        
        # 2. Build system prompt with context
        if system_prompt is None:
            system_prompt = """You are a helpful AI assistant with memory of past interactions.

{context_instruction}

Use this context to personalize your response and honor any user preferences."""
        
        final_system_prompt = system_prompt.format(context_instruction=context_instruction)
        
        # 3. Call LLM
        messages = [
            SystemMessage(content=final_system_prompt),
            HumanMessage(content=user_input)
        ]
        
        response = llm.invoke(messages)
        assistant_output = response.content
        
        # 4. Store conversation (post-processor)
        try:
            self.neuromem.observe(user_input, assistant_output)
        except Exception as e:
            print(f"Warning: Memory storage failed: {e}")
        
        # 5. Return response
        return assistant_output


# Legacy adapter for backward compatibility
class LangChainMemoryAdapter:
    """
    Legacy adapter - use NeuroMemLangChain instead.
    
    This is kept for backward compatibility.
    """
    
    def __init__(self, neuromem):
        self.neuromem = neuromem
        self.memory_key = "history"
        self.input_key = "input"
        self.output_key = "output"
    
    @property
    def memory_variables(self) -> List[str]:
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get(self.input_key, "")
        
        try:
            memories = self.neuromem.retrieve(query=query, task_type="chat", k=5)
            context_parts = [f"- {m.content}" for m in memories]
            context = "\n".join(context_parts) if context_parts else "No relevant context."
        except:
            context = "No relevant context."
        
        return {self.memory_key: context}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        user_input = inputs.get(self.input_key, "")
        assistant_output = outputs.get(self.output_key, "")
        
        if user_input and assistant_output:
            try:
                self.neuromem.observe(user_input, assistant_output)
            except:
                pass
    
    def clear(self) -> None:
        pass
