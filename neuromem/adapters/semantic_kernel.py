"""
Semantic Kernel adapter for NeuroMem.

Provides a KernelPlugin with @kernel_function methods exposing NeuroMem's
memory operations to Semantic Kernel agents.

Usage:
    from neuromem import NeuroMem
    from neuromem.adapters.semantic_kernel import create_neuromem_plugin
    from semantic_kernel import Kernel

    memory = NeuroMem.for_semantic_kernel(user_id="user_123")
    kernel = Kernel()

    plugin = create_neuromem_plugin(memory, k=5)
    kernel.add_plugin(plugin, plugin_name="neuromem")

    result = await kernel.invoke(
        plugin_name="neuromem",
        function_name="search_memory",
        query="What database did we choose?",
    )
"""

import logging
from typing import Annotated, Any

try:
    from semantic_kernel.functions import kernel_function

    SEMANTIC_KERNEL_AVAILABLE = True
except ImportError:
    SEMANTIC_KERNEL_AVAILABLE = False
    kernel_function = None  # type: ignore

logger = logging.getLogger(__name__)


class NeuroMemPlugin:
    """Semantic Kernel plugin exposing NeuroMem memory operations.

    Each method decorated with @kernel_function becomes available as a
    function that SK agents can invoke.

    Args:
        neuromem: NeuroMem instance
        k: Default number of results for search operations

    Usage:
        plugin = NeuroMemPlugin(memory, k=5)
        kernel.add_plugin(plugin, plugin_name="neuromem")
    """

    def __init__(self, neuromem: Any, k: int = 5):
        if not SEMANTIC_KERNEL_AVAILABLE:
            raise ImportError(
                "semantic-kernel is not installed. " "Install it with: pip install semantic-kernel"
            )
        self._neuromem = neuromem
        self._k = k

    @kernel_function(
        name="search_memory",
        description="Search NeuroMem for relevant memories and context",
    )
    def search_memory(
        self,
        query: Annotated[str, "The search query"],
        k: Annotated[int, "Number of results to return"] = 5,
    ) -> Annotated[str, "Formatted search results"]:
        """Search NeuroMem for relevant memories."""
        try:
            results = self._neuromem.retrieve(query=query, task_type="chat", k=k)
            if not results:
                return "No relevant memories found."
            return "\n".join(
                [f"[{r.memory_type.value}] (conf:{r.confidence:.2f}) {r.content}" for r in results]
            )
        except Exception as e:
            logger.warning("Memory search failed", extra={"error": str(e)[:200]})
            return "Memory search temporarily unavailable."

    @kernel_function(
        name="store_memory",
        description="Store important information as a persistent memory",
    )
    def store_memory(
        self,
        content: Annotated[str, "The content to remember"],
        response: Annotated[str, "The assistant's response"] = "Acknowledged",
        template: Annotated[
            str,
            "Memory template: preference, decision, fact, goal, or empty",
        ] = "",
    ) -> Annotated[str, "Confirmation"]:
        """Store a memory in NeuroMem."""
        try:
            self._neuromem.observe(content, response, template=template or None)
            return f"Memory stored: {content[:100]}..."
        except Exception as e:
            logger.warning("Memory store failed", extra={"error": str(e)[:200]})
            return "Failed to store memory."

    @kernel_function(
        name="list_memories",
        description="List stored memories with optional type filter",
    )
    def list_memories(
        self,
        memory_type: Annotated[
            str,
            "Filter: episodic, semantic, procedural, or empty for all",
        ] = "",
        limit: Annotated[int, "Maximum number of results"] = 20,
    ) -> Annotated[str, "Formatted memory list"]:
        """List stored memories."""
        try:
            results = self._neuromem.list(memory_type=memory_type or None, limit=limit)
            if not results:
                return "No memories found."
            lines = [f"[{r.id[:8]}] [{r.memory_type.value}] {r.content[:80]}..." for r in results]
            return f"Found {len(results)} memories:\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("Memory list failed", extra={"error": str(e)[:200]})
            return "Failed to list memories."

    @kernel_function(
        name="consolidate_memories",
        description="Consolidate episodic memories into stable knowledge",
    )
    def consolidate_memories(
        self,
    ) -> Annotated[str, "Consolidation result"]:
        """Trigger memory consolidation."""
        try:
            self._neuromem.consolidate()
            return "Memory consolidation complete."
        except Exception as e:
            logger.warning("Memory consolidation failed", extra={"error": str(e)[:200]})
            return "Memory consolidation failed."

    @kernel_function(
        name="get_context",
        description="Get graph-expanded context with related memories",
    )
    def get_context(
        self,
        query: Annotated[str, "The query to get context for"],
        k: Annotated[int, "Number of results"] = 8,
    ) -> Annotated[str, "Context with related memories"]:
        """Get graph-expanded context from NeuroMem."""
        try:
            results = self._neuromem.retrieve_with_context(query=query, task_type="chat", k=k)
            if not results:
                return "No context found."
            parts = []
            for r in results:
                parts.append(f"[{r.memory_type.value}] {r.content}")
                expanded = r.metadata.get("expanded_context")
                if expanded:
                    parts.append(f"  → Related: {expanded}")
            return "\n".join(parts)
        except Exception as e:
            logger.warning("Context retrieval failed", extra={"error": str(e)[:200]})
            return "Context retrieval temporarily unavailable."


def create_neuromem_plugin(
    neuromem: Any,
    k: int = 5,
    plugin_name: str = "neuromem",
) -> Any:
    """Create a Semantic Kernel KernelPlugin from NeuroMem.

    Args:
        neuromem: NeuroMem instance
        k: Default number of results for search operations
        plugin_name: Name for the plugin in the kernel

    Returns:
        KernelPlugin instance

    Usage:
        kernel = Kernel()
        plugin = create_neuromem_plugin(memory)
        kernel.add_plugin(plugin, plugin_name="neuromem")
    """
    if not SEMANTIC_KERNEL_AVAILABLE:
        raise ImportError(
            "semantic-kernel is not installed. " "Install it with: pip install semantic-kernel"
        )
    from semantic_kernel.functions import KernelPlugin

    instance = NeuroMemPlugin(neuromem, k=k)
    return KernelPlugin.from_object(
        plugin_name=plugin_name,
        plugin_instance=instance,
        description=(
            "Brain-inspired memory system with episodic, semantic, " "and procedural memory layers"
        ),
    )


__all__ = [
    "NeuroMemPlugin",
    "create_neuromem_plugin",
]
