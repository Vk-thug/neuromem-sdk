"""
LiteLLM adapter for NeuroMem.

Provides simple integration with LiteLLM for any LLM provider.

Usage:
    from neuromem import NeuroMem
    from neuromem.adapters.litellm import completion_with_memory

    memory = NeuroMem.for_litellm(user_id="user_123")

    response = completion_with_memory(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
        memory=memory
    )
"""

from typing import List, Dict, Iterator

try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    litellm = None


class NeuroMemLiteLLM:
    """
    LiteLLM wrapper with automatic memory handling.

    Usage:
        llm = NeuroMemLiteLLM(neuromem_instance)
        response = llm.completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
    """

    def __init__(self, neuromem, k: int = 5):
        """
        Initialize LiteLLM adapter.

        Args:
            neuromem: NeuroMem instance
            k: Number of memories to retrieve
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm is not installed. Install it with: pip install litellm")
        self.neuromem = neuromem
        self.k = k

    def completion(
        self, model: str, messages: List[Dict[str, str]], stream: bool = False, **kwargs
    ):
        """
        Call LiteLLM completion with automatic memory handling.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3", "gemini-pro")
            messages: List of message dicts
            stream: Whether to stream the response
            **kwargs: Additional arguments for litellm.completion()

        Returns:
            LiteLLM response object or stream iterator
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm is not installed")

        # 1. Extract user message
        user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break

        if not user_msg:
            # No user message, just call LiteLLM
            return litellm.completion(model=model, messages=messages, stream=stream, **kwargs)

        # 2. Retrieve memories
        try:
            memories = self.neuromem.retrieve(query=user_msg, task_type="chat", k=self.k)
            if memories:
                context = "\n".join([f"- {m.content}" for m in memories])
                memory_context = f"Context from previous interactions:\n{context}\n\nUse this context to personalize your response."
            else:
                memory_context = None
        except Exception:
            memory_context = None

        # 3. Inject context into messages
        messages_with_memory = messages.copy()
        if memory_context:
            # Add as system message at the beginning
            has_system = any(msg.get("role") == "system" for msg in messages_with_memory)
            if has_system:
                # Append to existing system message
                for msg in messages_with_memory:
                    if msg.get("role") == "system":
                        msg["content"] = f"{msg['content']}\n\n{memory_context}"
                        break
            else:
                # Insert new system message
                messages_with_memory.insert(0, {"role": "system", "content": memory_context})

        # 4. Call LiteLLM
        response = litellm.completion(
            model=model, messages=messages_with_memory, stream=stream, **kwargs
        )

        # 5. Store conversation
        if stream:
            # For streaming, wrap the iterator to capture the response
            return self._streaming_wrapper(response, user_msg)
        else:
            # For non-streaming, store immediately
            try:
                assistant_output = response.choices[0].message.content
                self.neuromem.observe(user_msg, assistant_output)
            except Exception:
                pass

            return response

    def _streaming_wrapper(self, stream: Iterator, user_msg: str) -> Iterator:
        """Wrap streaming response to capture and store the full response."""
        full_response = []

        try:
            for chunk in stream:
                # Yield chunk to user
                yield chunk

                # Collect response
                if hasattr(chunk.choices[0], "delta") and hasattr(
                    chunk.choices[0].delta, "content"
                ):
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response.append(content)

            # Store after streaming completes
            if full_response:
                assistant_output = "".join(full_response)
                try:
                    self.neuromem.observe(user_msg, assistant_output)
                except Exception:
                    pass

        except Exception as e:
            # If streaming fails, still try to store what we have
            if full_response:
                try:
                    self.neuromem.observe(user_msg, "".join(full_response))
                except Exception:
                    pass
            raise e


def completion_with_memory(
    model: str, messages: List[Dict[str, str]], memory, k: int = 5, stream: bool = False, **kwargs
):
    """
    Drop-in replacement for litellm.completion() with automatic memory.

    This is the simplest way to add memory to LiteLLM - just replace
    litellm.completion() with completion_with_memory()!

    Args:
        model: Model name (e.g., "gpt-4", "claude-3", "gemini-pro")
        messages: List of message dicts
        memory: NeuroMem instance
        k: Number of memories to retrieve
        stream: Whether to stream the response
        **kwargs: Additional arguments for litellm.completion()

    Returns:
        LiteLLM response object or stream iterator

    Usage:
        from neuromem import NeuroMem
        from neuromem.adapters.litellm import completion_with_memory

        memory = NeuroMem.for_litellm(user_id="user_123")

        # Just add memory parameter!
        response = completion_with_memory(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            memory=memory
        )

        print(response.choices[0].message.content)
    """
    adapter = NeuroMemLiteLLM(memory, k=k)
    return adapter.completion(model=model, messages=messages, stream=stream, **kwargs)


async def acompletion_with_memory(
    model: str, messages: List[Dict[str, str]], memory, k: int = 5, stream: bool = False, **kwargs
):
    """
    Async version of completion_with_memory().

    Args:
        model: Model name
        messages: List of message dicts
        memory: NeuroMem instance
        k: Number of memories to retrieve
        stream: Whether to stream the response
        **kwargs: Additional arguments for litellm.acompletion()

    Returns:
        LiteLLM response object or async stream iterator
    """
    if not LITELLM_AVAILABLE:
        raise ImportError("litellm is not installed")

    # Extract user message
    user_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    if not user_msg:
        return await litellm.acompletion(model=model, messages=messages, stream=stream, **kwargs)

    # Retrieve memories
    try:
        memories = memory.retrieve(query=user_msg, task_type="chat", k=k)
        if memories:
            context = "\n".join([f"- {m.content}" for m in memories])
            memory_context = f"Context from previous interactions:\n{context}\n\nUse this context to personalize your response."
        else:
            memory_context = None
    except Exception:
        memory_context = None

    # Inject context
    messages_with_memory = messages.copy()
    if memory_context:
        has_system = any(msg.get("role") == "system" for msg in messages_with_memory)
        if has_system:
            for msg in messages_with_memory:
                if msg.get("role") == "system":
                    msg["content"] = f"{msg['content']}\n\n{memory_context}"
                    break
        else:
            messages_with_memory.insert(0, {"role": "system", "content": memory_context})

    # Call LiteLLM
    response = await litellm.acompletion(
        model=model, messages=messages_with_memory, stream=stream, **kwargs
    )

    # Store conversation (async via Phase 2+ workers)
    if not stream:
        try:
            assistant_output = response.choices[0].message.content
            memory.observe(user_msg, assistant_output)
        except Exception:
            pass

    return response


__all__ = [
    "NeuroMemLiteLLM",
    "completion_with_memory",
    "acompletion_with_memory",
]
