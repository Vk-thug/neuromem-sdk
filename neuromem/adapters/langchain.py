"""
LangChain adapter for NeuroMem.

Compatible with langchain-core >= 0.3.x / 1.x (2025-2026 APIs).

Provides:
1. NeuroMemRunnable — LCEL-compatible Runnable with streaming
2. add_memory() — Wrap any chain with memory
3. NeuroMemLangChain — Simple chat wrapper
4. NeuroMemChatMessageHistory — BaseChatMessageHistory implementation
5. LangChainMemoryAdapter — Legacy backward-compatible adapter
"""

from typing import List, Dict, Any, Optional, Iterator
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
)
from langchain_core.chat_history import BaseChatMessageHistory
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


class NeuroMemRunnable(Runnable):
    """
    LCEL-compatible Runnable for memory retrieval with streaming support.

    Retrieves relevant memories and injects them into the input dict.
    Supports invoke, ainvoke, stream, and astream.

    Usage:
        memory_runnable = NeuroMemRunnable(neuromem_instance)
        chain = memory_runnable | prompt | llm | output_parser
    """

    def __init__(self, neuromem: Any, k: int = 5, memory_key: str = "memory_context"):
        self.neuromem = neuromem
        self.k = k
        self.memory_key = memory_key

    def invoke(
        self, input: Dict[str, Any], config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Retrieve memories and add to input."""
        query = self._extract_query(input)

        try:
            if query and query.strip():
                memories = self.neuromem.retrieve(query=query, task_type="chat", k=self.k)
                context = "\n".join([f"- {m.content}" for m in memories])
            else:
                context = ""
        except Exception as e:
            logger.warning("Memory retrieval failed", extra={"error": str(e)[:200]})
            context = ""

        input[self.memory_key] = context

        # Inject into messages if present
        if context and "messages" in input and isinstance(input["messages"], list):
            ctx_msg = SystemMessage(content=f"FACTS ABOUT THE USER:\n{context}")
            msgs = list(input["messages"])
            if msgs and isinstance(msgs[0], SystemMessage):
                msgs.insert(1, ctx_msg)
            else:
                msgs.insert(0, ctx_msg)
            input["messages"] = msgs

        return input

    async def ainvoke(
        self, input: Dict[str, Any], config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Async version — reuses sync since NeuroMem handles async via workers."""
        return self.invoke(input, config)

    def _extract_query(self, input: Dict[str, Any]) -> str:
        """Extract query text from various input formats."""
        query = input.get("input", input.get("question", ""))

        if not query and "messages" in input and isinstance(input["messages"], list):
            for msg in reversed(input["messages"]):
                if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
                    query = msg.content
                    break

        return query


class NeuroMemChatMessageHistory(BaseChatMessageHistory):
    """
    LangChain BaseChatMessageHistory backed by NeuroMem.

    Compatible with RunnableWithMessageHistory:
        history = NeuroMemChatMessageHistory(neuromem_instance)
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: history,
        )
    """

    def __init__(self, neuromem: Any, k: int = 10):
        self.neuromem = neuromem
        self.k = k
        self._messages: List[BaseMessage] = []

    @property
    def messages(self) -> List[BaseMessage]:
        """Return messages from NeuroMem memory."""
        try:
            from neuromem.core.types import MemoryType

            memories = self.neuromem.list(memory_type=MemoryType.EPISODIC.value, limit=self.k)
            messages: List[BaseMessage] = []
            for m in memories:
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


def add_memory(chain: Runnable, neuromem: Any, k: int = 5) -> Runnable:
    """
    Wrap any LangChain chain with memory retrieval, storage, and streaming.

    Args:
        chain: Any LangChain Runnable
        neuromem: NeuroMem instance
        k: Number of memories to retrieve

    Returns:
        Chain with memory capabilities (supports invoke, ainvoke, stream, astream)

    Usage:
        chain = prompt | llm | output_parser
        chain_with_memory = add_memory(chain, memory)
        response = chain_with_memory.invoke({"input": "Hello"})

        # Streaming:
        for chunk in chain_with_memory.stream({"input": "Hello"}):
            print(chunk, end="", flush=True)
    """
    memory_runnable = NeuroMemRunnable(neuromem, k=k)

    class MemoryChain(Runnable):
        def __init__(self, inner_chain: Runnable, memory_retriever: NeuroMemRunnable, nm: Any):
            self.chain = inner_chain
            self.memory = memory_retriever
            self.neuromem = nm

        def invoke(self, input: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Any:
            input_with_memory = self.memory.invoke(input, config)
            output = self.chain.invoke(input_with_memory, config)
            self._store_observation(input, output)
            return output

        async def ainvoke(
            self, input: Dict[str, Any], config: Optional[RunnableConfig] = None
        ) -> Any:
            input_with_memory = await self.memory.ainvoke(input, config)
            output = await self.chain.ainvoke(input_with_memory, config)
            self._store_observation(input, output)
            return output

        def stream(
            self, input: Dict[str, Any], config: Optional[RunnableConfig] = None, **kwargs
        ) -> Iterator:
            """Stream with memory — retrieves context first, then streams chain output."""
            input_with_memory = self.memory.invoke(input, config)
            collected_chunks: List[str] = []

            for chunk in self.chain.stream(input_with_memory, config, **kwargs):
                yield chunk
                # Collect text content for observation
                if isinstance(chunk, str):
                    collected_chunks.append(chunk)
                elif hasattr(chunk, "content") and isinstance(chunk.content, str):
                    collected_chunks.append(chunk.content)

            # Store after stream completes
            if collected_chunks:
                full_output = "".join(collected_chunks)
                user_input = self._extract_user_input(input)
                if user_input and full_output:
                    try:
                        self.neuromem.observe(user_input, full_output)
                    except Exception:
                        pass

        async def astream(
            self, input: Dict[str, Any], config: Optional[RunnableConfig] = None, **kwargs
        ):
            """Async stream with memory."""
            input_with_memory = await self.memory.ainvoke(input, config)
            collected_chunks: List[str] = []

            async for chunk in self.chain.astream(input_with_memory, config, **kwargs):
                yield chunk
                if isinstance(chunk, str):
                    collected_chunks.append(chunk)
                elif hasattr(chunk, "content") and isinstance(chunk.content, str):
                    collected_chunks.append(chunk.content)

            if collected_chunks:
                full_output = "".join(collected_chunks)
                user_input = self._extract_user_input(input)
                if user_input and full_output:
                    try:
                        self.neuromem.observe(user_input, full_output)
                    except Exception:
                        pass

        def _store_observation(self, input: Dict[str, Any], output: Any) -> None:
            """Extract user/assistant text and store observation."""
            try:
                user_input = self._extract_user_input(input)
                assistant_output = self._extract_output(output)
                if user_input and assistant_output:
                    self.neuromem.observe(user_input, assistant_output)
            except Exception:
                pass

        def _extract_user_input(self, input: Dict[str, Any]) -> str:
            if "input" in input:
                return input["input"]
            if "question" in input:
                return input["question"]
            if "messages" in input and isinstance(input["messages"], list):
                for msg in reversed(input["messages"]):
                    if hasattr(msg, "content"):
                        return msg.content
                    return str(msg)
            return ""

        def _extract_output(self, output: Any) -> str:
            if isinstance(output, str):
                return output
            if isinstance(output, dict):
                for key in ("output", "text", "answer"):
                    if key in output:
                        return str(output[key])
                if "messages" in output and isinstance(output["messages"], list):
                    last = output["messages"][-1]
                    return last.content if hasattr(last, "content") else str(last)
                return str(output)
            if hasattr(output, "content"):
                return output.content
            return str(output)

    return MemoryChain(chain, memory_runnable, neuromem)


class NeuroMemLangChain:
    """
    Simple LangChain adapter with streaming support.

    Usage:
        adapter = NeuroMemLangChain(neuromem_instance)
        response = adapter.chat(llm, "user message")

        # Streaming:
        for chunk in adapter.stream_chat(llm, "user message"):
            print(chunk, end="", flush=True)
    """

    def __init__(self, neuromem: Any, k: int = 5):
        self.neuromem = neuromem
        self.k = k

    def chat(self, llm: Any, user_input: str, system_prompt: Optional[str] = None) -> str:
        """Chat with automatic memory handling. Returns full response."""
        messages = self._build_messages(user_input, system_prompt)
        response = llm.invoke(messages)
        assistant_output = response.content if hasattr(response, "content") else str(response)

        try:
            self.neuromem.observe(user_input, assistant_output)
        except Exception:
            pass

        return assistant_output

    def stream_chat(
        self, llm: Any, user_input: str, system_prompt: Optional[str] = None
    ) -> Iterator[str]:
        """Stream chat with automatic memory handling. Yields text chunks."""
        messages = self._build_messages(user_input, system_prompt)
        collected: List[str] = []

        for chunk in llm.stream(messages):
            text = chunk.content if hasattr(chunk, "content") else str(chunk)
            if text:
                collected.append(text)
                yield text

        # Store after stream completes
        if collected:
            full_output = "".join(collected)
            try:
                self.neuromem.observe(user_input, full_output)
            except Exception:
                pass

    async def astream_chat(self, llm: Any, user_input: str, system_prompt: Optional[str] = None):
        """Async stream chat. Yields text chunks."""
        messages = self._build_messages(user_input, system_prompt)
        collected: List[str] = []

        async for chunk in llm.astream(messages):
            text = chunk.content if hasattr(chunk, "content") else str(chunk)
            if text:
                collected.append(text)
                yield text

        if collected:
            full_output = "".join(collected)
            try:
                self.neuromem.observe(user_input, full_output)
            except Exception:
                pass

    def _build_messages(self, user_input: str, system_prompt: Optional[str]) -> List[BaseMessage]:
        """Build message list with memory context."""
        try:
            memories = self.neuromem.retrieve(query=user_input, task_type="chat", k=self.k)
            if memories:
                context = "\n".join([f"- {m.content}" for m in memories])
                context_block = f"Here's what you know about the user:\n{context}"
            else:
                context_block = "This is a new conversation with no prior context."
        except Exception:
            context_block = "This is a new conversation with no prior context."

        if system_prompt is None:
            system_prompt = (
                "You are a helpful AI assistant with memory of past interactions.\n\n"
                "{context}\n\n"
                "Use this context to personalize your response."
            )

        final_system = system_prompt.format(context=context_block)

        return [
            SystemMessage(content=final_system),
            HumanMessage(content=user_input),
        ]


class LangChainMemoryAdapter:
    """
    Legacy adapter for backward compatibility.

    Use NeuroMemLangChain or add_memory() for new projects.
    """

    def __init__(self, neuromem: Any):
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
            context = (
                "\n".join([f"- {m.content}" for m in memories])
                if memories
                else "No relevant context."
            )
        except Exception:
            context = "No relevant context."
        return {self.memory_key: context}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        user_input = inputs.get(self.input_key, "")
        assistant_output = outputs.get(self.output_key, "")
        if user_input and assistant_output:
            try:
                self.neuromem.observe(user_input, assistant_output)
            except Exception:
                pass

    def clear(self) -> None:
        pass


# Type alias for Any to avoid circular imports
Any = object


__all__ = [
    "NeuroMemRunnable",
    "NeuroMemChatMessageHistory",
    "add_memory",
    "NeuroMemLangChain",
    "LangChainMemoryAdapter",
]
