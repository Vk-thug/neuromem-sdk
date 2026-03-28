"""
AutoGen (AG2) adapter for NeuroMem.

Provides tool registration functions and a Teachability-style capability
that auto-injects memory context into agent messages.

Usage:
    from neuromem import NeuroMem
    from neuromem.adapters.autogen import register_neuromem_tools, NeuroMemCapability
    from autogen import ConversableAgent

    memory = NeuroMem.for_autogen(user_id="user_123")

    assistant = ConversableAgent("assistant", llm_config={...})
    user_proxy = ConversableAgent("user_proxy", human_input_mode="NEVER")

    # Option A: Register as callable tools
    register_neuromem_tools(memory, caller=assistant, executor=user_proxy, k=5)

    # Option B: Auto-inject context into every message
    capability = NeuroMemCapability(memory, k=5)
    capability.add_to_agent(assistant)

    user_proxy.initiate_chat(assistant, message="What did we decide about the API design?")
"""

import logging
from typing import Any

try:
    from autogen import register_function

    AUTOGEN_AVAILABLE = True
except ImportError:
    try:
        from ag2 import register_function

        AUTOGEN_AVAILABLE = True
    except ImportError:
        AUTOGEN_AVAILABLE = False
        register_function = None  # type: ignore

logger = logging.getLogger(__name__)


def register_neuromem_tools(
    neuromem: Any,
    caller: Any,
    executor: Any,
    k: int = 5,
) -> None:
    """Register all NeuroMem tools with AutoGen agents.

    Registers 4 tool functions on the caller (proposes tool calls) and
    executor (runs tool calls).

    Args:
        neuromem: NeuroMem instance
        caller: ConversableAgent that proposes tool calls (e.g., assistant)
        executor: ConversableAgent that executes tools (e.g., user_proxy)
        k: Default number of results for search operations

    Usage:
        register_neuromem_tools(memory, assistant, user_proxy, k=5)
    """
    if not AUTOGEN_AVAILABLE:
        raise ImportError("autogen/ag2 is not installed. Install it with: pip install ag2")

    def search_memory(query: str, k: int = 5) -> str:
        """Search NeuroMem for relevant memories, past decisions, and context.

        Args:
            query: The search query
            k: Number of results to return
        """
        try:
            results = neuromem.retrieve(query=query, task_type="chat", k=k)
            if not results:
                return "No relevant memories found."
            lines = []
            for r in results:
                lines.append(f"[{r.memory_type.value}] (conf:{r.confidence:.2f}) {r.content}")
            return "\n".join(lines)
        except Exception:
            return "Memory search temporarily unavailable."

    def store_memory(content: str, response: str = "Acknowledged") -> str:
        """Store important information as a persistent memory.

        Args:
            content: The content to remember
            response: The assistant's response
        """
        try:
            neuromem.observe(content, response)
            return f"Memory stored: {content[:100]}..."
        except Exception:
            return "Failed to store memory."

    def list_memories(memory_type: str = "", limit: int = 20) -> str:
        """List stored memories with optional type filter (episodic, semantic, procedural).

        Args:
            memory_type: Filter by type, or empty for all
            limit: Maximum number of results
        """
        try:
            results = neuromem.list(memory_type=memory_type or None, limit=limit)
            if not results:
                return "No memories found."
            lines = [f"[{r.id[:8]}] [{r.memory_type.value}] {r.content[:80]}..." for r in results]
            return f"Found {len(results)} memories:\n" + "\n".join(lines)
        except Exception:
            return "Failed to list memories."

    def consolidate_memories() -> str:
        """Consolidate episodic memories into stable knowledge."""
        try:
            neuromem.consolidate()
            return "Memory consolidation complete."
        except Exception:
            return "Memory consolidation failed."

    # Register all tools
    register_function(
        search_memory,
        caller=caller,
        executor=executor,
        name="search_memory",
        description="Search NeuroMem for relevant memories, past decisions, and context",
    )
    register_function(
        store_memory,
        caller=caller,
        executor=executor,
        name="store_memory",
        description="Store important information as a persistent memory",
    )
    register_function(
        list_memories,
        caller=caller,
        executor=executor,
        name="list_memories",
        description="List stored memories with optional type filter (episodic, semantic, procedural)",
    )
    register_function(
        consolidate_memories,
        caller=caller,
        executor=executor,
        name="consolidate_memories",
        description="Consolidate episodic memories into stable knowledge",
    )


class NeuroMemCapability:
    """AG2 capability that adds persistent memory to any ConversableAgent.

    Automatically enriches incoming messages with relevant memory context,
    similar to AG2's Teachability capability.

    Args:
        neuromem: NeuroMem instance
        k: Number of memories to retrieve for context

    Usage:
        capability = NeuroMemCapability(memory, k=5)
        capability.add_to_agent(assistant)
    """

    def __init__(self, neuromem: Any, k: int = 5):
        if not AUTOGEN_AVAILABLE:
            raise ImportError("autogen/ag2 is not installed. Install it with: pip install ag2")
        self.neuromem = neuromem
        self.k = k

    def add_to_agent(self, agent: Any) -> None:
        """Add memory capability to an AutoGen agent.

        Registers a hook on process_last_received_message to prepend
        relevant memories to every incoming message.

        Args:
            agent: ConversableAgent to add memory to
        """
        agent.register_hook(
            hookable_method="process_last_received_message",
            hook=self._enrich_with_memory,
        )

    def _enrich_with_memory(self, message: str) -> str:
        """Hook that prepends relevant memories to incoming messages."""
        try:
            memories = self.neuromem.retrieve(query=message, task_type="chat", k=self.k)
            if memories:
                context = "\n".join([f"- {m.content}" for m in memories])
                return f"[Relevant context from memory:\n{context}]\n\n{message}"
        except Exception:
            pass
        return message


__all__ = [
    "register_neuromem_tools",
    "NeuroMemCapability",
]
