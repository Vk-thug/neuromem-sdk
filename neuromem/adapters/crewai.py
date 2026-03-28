"""
CrewAI adapter for NeuroMem.

Provides BaseTool subclasses that give CrewAI agents access to NeuroMem's
brain-inspired memory system.

Usage:
    from neuromem import NeuroMem
    from neuromem.adapters.crewai import create_neuromem_tools
    from crewai import Agent, Task, Crew

    memory = NeuroMem.for_crewai(user_id="user_123")
    tools = create_neuromem_tools(memory, k=5)

    agent = Agent(
        role="Research Assistant",
        goal="Help the user with context-aware research",
        tools=tools,
    )

    task = Task(
        description="Find what the user previously decided about the database schema",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task])
    result = crew.kickoff()
"""

import logging
from typing import Any, List, Optional, Type

try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, ConfigDict, Field

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    BaseTool = object  # type: ignore
    from pydantic import BaseModel, ConfigDict, Field  # type: ignore

logger = logging.getLogger(__name__)


# --- Input Schemas ---


class SearchInput(BaseModel):
    """Input schema for memory search."""

    query: str = Field(description="The search query to find relevant memories")
    k: int = Field(default=5, description="Number of results to return")
    memory_type: Optional[str] = Field(
        default=None,
        description="Filter by memory type: episodic, semantic, procedural, or None for all",
    )


class StoreInput(BaseModel):
    """Input schema for memory storage."""

    content: str = Field(description="The content to store as a memory")
    assistant_response: str = Field(default="Acknowledged", description="The assistant's response")
    template: Optional[str] = Field(
        default=None,
        description="Memory template: preference, decision, fact, goal, or None for auto-detect",
    )


class ContextInput(BaseModel):
    """Input schema for graph-expanded context retrieval."""

    query: str = Field(description="The query to get context for")
    k: int = Field(default=8, description="Number of results to return")


# --- Tools ---


class NeuroMemSearchTool(BaseTool):
    """Search the memory system for relevant context, past decisions, preferences, and knowledge."""

    name: str = "neuromem_search"
    description: str = (
        "Search the memory system for relevant context, past decisions, "
        "preferences, and knowledge"
    )
    args_schema: Type[BaseModel] = SearchInput

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _neuromem: Any = None
    _k: int = 5

    def __init__(self, neuromem: Any, k: int = 5, **kwargs: Any):
        super().__init__(**kwargs)
        self._neuromem = neuromem
        self._k = k

    def _run(
        self,
        query: str,
        k: int = 5,
        memory_type: Optional[str] = None,
    ) -> str:
        """Search NeuroMem for relevant memories."""
        try:
            results = self._neuromem.retrieve(query=query, task_type="chat", k=k)
            if not results:
                return "No relevant memories found."
            lines = []
            for r in results:
                tags = ", ".join(r.tags) if r.tags else "none"
                lines.append(
                    f"[{r.memory_type.value}] (conf:{r.confidence:.2f}) {r.content} "
                    f"[tags: {tags}]"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Memory search failed", extra={"error": str(e)[:200]})
            return "Memory search temporarily unavailable."


class NeuroMemStoreTool(BaseTool):
    """Store important information as a memory — preferences, decisions, facts, or goals."""

    name: str = "neuromem_store"
    description: str = (
        "Store important information as a memory — preferences, decisions, facts, or goals"
    )
    args_schema: Type[BaseModel] = StoreInput

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _neuromem: Any = None

    def __init__(self, neuromem: Any, **kwargs: Any):
        super().__init__(**kwargs)
        self._neuromem = neuromem

    def _run(
        self,
        content: str,
        assistant_response: str = "Acknowledged",
        template: Optional[str] = None,
    ) -> str:
        """Store a memory in NeuroMem."""
        try:
            self._neuromem.observe(content, assistant_response, template=template)
            return f"Memory stored: {content[:100]}..."
        except Exception as e:
            logger.warning("Memory store failed", extra={"error": str(e)[:200]})
            return "Failed to store memory."


class NeuroMemConsolidateTool(BaseTool):
    """Consolidate memories — promote recurring patterns into stable knowledge and apply forgetting curves."""

    name: str = "neuromem_consolidate"
    description: str = (
        "Consolidate memories — promote recurring patterns into stable knowledge "
        "and apply forgetting curves"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _neuromem: Any = None

    def __init__(self, neuromem: Any, **kwargs: Any):
        super().__init__(**kwargs)
        self._neuromem = neuromem

    def _run(self, **kwargs: Any) -> str:
        """Trigger memory consolidation."""
        try:
            self._neuromem.consolidate()
            return "Memory consolidation complete."
        except Exception as e:
            logger.warning("Memory consolidation failed", extra={"error": str(e)[:200]})
            return "Memory consolidation failed."


class NeuroMemContextTool(BaseTool):
    """Get graph-expanded context for a query — retrieves memories plus related entities and connections."""

    name: str = "neuromem_context"
    description: str = (
        "Get graph-expanded context for a query — retrieves memories plus "
        "related entities and connections"
    )
    args_schema: Type[BaseModel] = ContextInput

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _neuromem: Any = None
    _k: int = 8

    def __init__(self, neuromem: Any, k: int = 8, **kwargs: Any):
        super().__init__(**kwargs)
        self._neuromem = neuromem
        self._k = k

    def _run(self, query: str, k: int = 8) -> str:
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


def create_neuromem_tools(neuromem: Any, k: int = 5) -> List:
    """Create all NeuroMem tools for CrewAI agents.

    Args:
        neuromem: NeuroMem instance
        k: Default number of results for search/context tools

    Returns:
        List of CrewAI BaseTool instances

    Usage:
        tools = create_neuromem_tools(memory, k=5)
        agent = Agent(role="...", tools=tools)
    """
    if not CREWAI_AVAILABLE:
        raise ImportError("crewai is not installed. Install it with: pip install crewai")
    return [
        NeuroMemSearchTool(neuromem=neuromem, k=k),
        NeuroMemStoreTool(neuromem=neuromem),
        NeuroMemConsolidateTool(neuromem=neuromem),
        NeuroMemContextTool(neuromem=neuromem, k=k),
    ]


__all__ = [
    "NeuroMemSearchTool",
    "NeuroMemStoreTool",
    "NeuroMemConsolidateTool",
    "NeuroMemContextTool",
    "create_neuromem_tools",
]
