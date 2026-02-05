"""
Enhanced LangChain adapter for NeuroMem.

Provides multiple integration patterns:
1. NeuroMemRunnable - LCEL-compatible Runnable
2. add_memory() - Decorator to add memory to any chain
3. NeuroMemLangChain - Simple chat wrapper
4. NeuroMemChatMessageHistory - BaseChatMessageHistory implementation
"""

from typing import List, Dict, Any, Optional, Callable
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory


class NeuroMemRunnable(Runnable):
    """
    LCEL-compatible Runnable for memory retrieval.
    
    Usage:
        memory_runnable = NeuroMemRunnable(neuromem_instance)
        chain = memory_runnable | prompt | llm | output_parser
    """
    
    def __init__(self, neuromem, k: int = 5, memory_key: str = "memory_context"):
        self.neuromem = neuromem
        self.k = k
        self.memory_key = memory_key
    
    def invoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        """Retrieve memories and add to input."""
        # Extract query from input
        query = input.get("input", input.get("question", ""))

        # If no query text, try to extract from messages
        if not query and "messages" in input and isinstance(input["messages"], list):
            for msg in reversed(input["messages"]):
                if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
                    query = msg.content
                    break

        # Retrieve memories
        try:
            if query and query.strip():
                memories = self.neuromem.retrieve(query=query, task_type="chat", k=self.k)
                context = "\n".join([f"- {m.content}" for m in memories])
            else:
                # No query provided, skip retrieval
                memories = []
                context = ""
            # if context:
            #     print(f"\n🧠 Retrieved Context:\n{context}\n")
        except Exception as e:
            print(f"⚠️ Memory retrieval failed: {e}")
            context = ""
        
        # Add to input
        input[self.memory_key] = context
        
        # Also inject directly into messages if present (more robust for some agents)
        if context and "messages" in input and isinstance(input["messages"], list):
            # Prepend as a system message or append as a clarifying message
            # Prepending is usually best for "instructional" memory
            ctx_msg = SystemMessage(content=f"FACTS ABOUT THE USER:\n{context}")
            
            # Check if there is already a system message at the start
            msgs = list(input["messages"]) # Copy to avoid side effects
            if msgs and isinstance(msgs[0], SystemMessage):
                # Insert after the main system message
                msgs.insert(1, ctx_msg)
            else:
                # Prepend at the start
                msgs.insert(0, ctx_msg)
            input["messages"] = msgs
            
        return input
    
    async def ainvoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        """Async version - currently same as sync (Phase 2+ workers handle async)."""
        # Reuse sync implementation since NeuroMem already handles async via workers
        return self.invoke(input, config)


class NeuroMemChatMessageHistory(BaseChatMessageHistory):
    """
    LangChain BaseChatMessageHistory implementation using NeuroMem.
    
    Usage:
        history = NeuroMemChatMessageHistory(neuromem_instance)
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: history
        )
    """
    
    def __init__(self, neuromem, k: int = 10):
        self.neuromem = neuromem
        self.k = k
        self._messages: List[BaseMessage] = []
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve messages from memory."""
        try:
            # Use the list() method to get all recent memories instead of retrieve with empty query
            from neuromem.core.types import MemoryType
            memories = self.neuromem.list(memory_type=MemoryType.EPISODIC.value, limit=self.k)
            messages = []
            for m in memories:
                # Parse "User: X\nAssistant: Y" format
                if "User:" in m.content and "Assistant:" in m.content:
                    parts = m.content.split("\nAssistant:")
                    user_part = parts[0].replace("User:", "").strip()
                    ai_part = parts[1].strip() if len(parts) > 1 else ""
                    messages.append(HumanMessage(content=user_part))
                    if ai_part:
                        messages.append(AIMessage(content=ai_part))
            return messages
        except Exception:
            return []
    
    def add_message(self, message: BaseMessage) -> None:
        """Add message (handled by observe())."""
        self._messages.append(message)
    
    def clear(self) -> None:
        """Clear messages."""
        self._messages = []


def add_memory(chain: Runnable, neuromem, k: int = 5) -> Runnable:
    """
    Decorator to add memory to any LangChain chain.
    
    This wraps your chain with memory retrieval and storage.
    
    Args:
        chain: Any LangChain Runnable (chain)
        neuromem: NeuroMem instance
        k: Number of memories to retrieve
    
    Returns:
        Chain with memory capabilities
    
    Usage:
        chain = prompt | llm | output_parser
        chain_with_memory = add_memory(chain, memory)
        
        response = chain_with_memory.invoke({"input": "Hello"})
    """
    memory_runnable = NeuroMemRunnable(neuromem, k=k)
    
    # Create wrapper that handles observation
    class MemoryChain(Runnable):
        def __init__(self, inner_chain, memory_retriever, nm):
            self.chain = inner_chain
            self.memory = memory_retriever
            self.neuromem = nm
        
        def invoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Any:
            # 1. Retrieve memories
            input_with_memory = self.memory.invoke(input, config)
            
            # 2. Run chain
            output = self.chain.invoke(input_with_memory, config)
            
            # 3. Store observation
            try:
                # Optimized input extraction logic
                user_input = ""
                if "input" in input:
                    user_input = input["input"]
                elif "question" in input:
                    user_input = input["question"]
                elif "messages" in input and isinstance(input["messages"], list):
                    # Extract from last message in input messages list
                    last_msg = input["messages"][-1]
                    if hasattr(last_msg, "content"):
                        user_input = last_msg.content
                    else:
                        user_input = str(last_msg)
                
                # Extract clean text content from output
                if isinstance(output, str):
                    assistant_output = output
                elif isinstance(output, dict):
                    # Common LangChain output keys
                    if "output" in output:
                        assistant_output = output["output"]
                    elif "text" in output:
                        assistant_output = output["text"]
                    elif "messages" in output and isinstance(output["messages"], list):
                        # Extract content from last message if it's an AIMessage
                        last_msg = output["messages"][-1]
                        if hasattr(last_msg, "content"):
                            assistant_output = last_msg.content
                        else:
                            assistant_output = str(last_msg)
                    else:
                        assistant_output = str(output)
                elif hasattr(output, "content"):
                    # AIMessage or similar
                    assistant_output = output.content
                else:
                    assistant_output = str(output)
                
                self.neuromem.observe(user_input, assistant_output)
            except Exception as e:
                # print(f"Observation failed: {e}")
                pass
            
            return output
        
        async def ainvoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Any:
            # Async version
            input_with_memory = await self.memory.ainvoke(input, config)
            output = await self.chain.ainvoke(input_with_memory, config)
            
            try:
                user_input = input.get("input", input.get("question", ""))
                assistant_output = output if isinstance(output, str) else str(output)
                self.neuromem.observe(user_input, assistant_output)
            except Exception:
                pass
            
            return output
    
    return MemoryChain(chain, memory_runnable, neuromem)


class NeuroMemLangChain:
    """
    Simple LangChain adapter with automatic memory handling.
    
    Usage:
        memory_adapter = NeuroMemLangChain(neuromem_instance)
        response = memory_adapter.chat(llm, "user message")
    """
    
    def __init__(self, neuromem, k: int = 5):
        self.neuromem = neuromem
        self.k = k
    
    def chat(self, llm, user_input: str, system_prompt: Optional[str] = None) -> str:
        """
        Chat with automatic memory handling.
        
        Args:
            llm: LangChain LLM instance
            user_input: User's message
            system_prompt: Optional custom system prompt
        
        Returns:
            Assistant's response
        """
        # 1. Retrieve memories
        try:
            memories = self.neuromem.retrieve(query=user_input, task_type="chat", k=self.k)
            if memories:
                context = "\n".join([f"- {m.content}" for m in memories])
                context_instruction = f"Here's what you know about the user:\n{context}"
            else:
                context_instruction = "This is a new conversation with no prior context."
        except Exception:
            context_instruction = "This is a new conversation with no prior context."
        
        # 2. Build system prompt
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
        
        # 4. Store conversation
        try:
            self.neuromem.observe(user_input, assistant_output)
        except Exception:
            pass
        
        return assistant_output


# Legacy adapter for backward compatibility
class LangChainMemoryAdapter:
    """
    Legacy adapter - use NeuroMemLangChain or add_memory() instead.
    
    Kept for backward compatibility.
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


__all__ = [
    "NeuroMemRunnable",
    "NeuroMemChatMessageHistory",
    "add_memory",
    "NeuroMemLangChain",
    "LangChainMemoryAdapter",  # Legacy
]
