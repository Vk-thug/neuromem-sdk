"""
DSPy adapter for NeuroMem.

Provides a Retrieve subclass, ReAct tool functions, and a pre-built
MemoryAugmentedQA module for DSPy integration.

Usage:
    from neuromem import NeuroMem
    from neuromem.adapters.dspy import NeuroMemRetriever, MemoryAugmentedQA, create_neuromem_tools
    import dspy

    memory = NeuroMem.for_dspy(user_id="user_123")
    lm = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=lm)

    # Option A: As global retriever
    retriever = NeuroMemRetriever(memory, k=5)

    # Option B: Pre-built RAG module
    qa = MemoryAugmentedQA(memory, k=5)
    result = qa(question="What did we decide about the API schema?")

    # Option C: Tools for ReAct
    tools = create_neuromem_tools(memory)
    react = dspy.ReAct("question -> answer", tools=tools)
    result = react(question="Search my memories for database decisions")
"""

import logging
from typing import Any, List, Optional

try:
    import dspy

    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    dspy = None  # type: ignore

logger = logging.getLogger(__name__)


class NeuroMemRetriever:
    """DSPy retriever backed by NeuroMem's brain-inspired memory system.

    Can be used as a drop-in replacement for any DSPy retriever.

    Args:
        neuromem: NeuroMem instance
        k: Default number of passages to retrieve

    Usage:
        retriever = NeuroMemRetriever(memory, k=5)

        # Use directly in a module:
        class MyModule(dspy.Module):
            def __init__(self):
                self.retrieve = NeuroMemRetriever(memory, k=5)

            def forward(self, question):
                context = self.retrieve(question).passages
                ...
    """

    def __init__(self, neuromem: Any, k: int = 5):
        if not DSPY_AVAILABLE:
            raise ImportError("dspy is not installed. Install it with: pip install dspy")
        self.neuromem = neuromem
        self.k = k

    def __call__(self, query: str, k: Optional[int] = None, **kwargs: Any) -> Any:
        """Retrieve passages from NeuroMem.

        Args:
            query: The search query
            k: Number of passages (overrides default)

        Returns:
            dspy.Prediction with passages list
        """
        return self.forward(query, k=k, **kwargs)

    def forward(self, query: str, k: Optional[int] = None, **kwargs: Any) -> Any:
        """Retrieve passages from NeuroMem.

        Args:
            query: The search query
            k: Number of passages (overrides default)

        Returns:
            dspy.Prediction with passages list
        """
        k = k if k is not None else self.k
        try:
            results = self.neuromem.retrieve(query=query, task_type="chat", k=k)
            passages = [r.content for r in results]
        except Exception as e:
            logger.warning("NeuroMem retrieval failed", extra={"error": str(e)[:200]})
            passages = []
        return dspy.Prediction(passages=passages)


class MemoryAugmentedQA:
    """Pre-built DSPy module that retrieves NeuroMem context before answering.

    Args:
        neuromem: NeuroMem instance
        k: Number of memories to retrieve for context

    Usage:
        qa = MemoryAugmentedQA(memory, k=5)
        result = qa(question="What database did we choose?")
        print(result.answer)
    """

    def __init__(self, neuromem: Any, k: int = 5):
        if not DSPY_AVAILABLE:
            raise ImportError("dspy is not installed. Install it with: pip install dspy")
        self.retrieve = NeuroMemRetriever(neuromem, k=k)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def __call__(self, question: str) -> Any:
        return self.forward(question)

    def forward(self, question: str) -> Any:
        """Retrieve context and generate answer.

        Args:
            question: The question to answer

        Returns:
            dspy.Prediction with answer field
        """
        context = self.retrieve(question).passages
        return self.generate(context=context, question=question)


def create_neuromem_tools(neuromem: Any, k: int = 5) -> List:
    """Create NeuroMem tools for DSPy ReAct agents.

    Args:
        neuromem: NeuroMem instance
        k: Default number of results for search/context tools

    Returns:
        List of callable tool functions for DSPy ReAct

    Usage:
        tools = create_neuromem_tools(memory)
        react = dspy.ReAct("question -> answer", tools=tools)
    """
    if not DSPY_AVAILABLE:
        raise ImportError("dspy is not installed. Install it with: pip install dspy")

    def search_memory(query: str, k: int = 5) -> str:
        """Search NeuroMem for relevant memories and context."""
        try:
            results = neuromem.retrieve(query=query, task_type="chat", k=k)
            if not results:
                return "No relevant memories found."
            return "\n".join([f"[{r.memory_type.value}] {r.content}" for r in results])
        except Exception:
            return "Memory search temporarily unavailable."

    def store_memory(content: str, response: str = "Acknowledged") -> str:
        """Store important information as a persistent memory."""
        try:
            neuromem.observe(content, response)
            return f"Memory stored: {content[:100]}..."
        except Exception:
            return "Failed to store memory."

    def get_context(query: str) -> str:
        """Get graph-expanded context with related memories and entity connections."""
        try:
            results = neuromem.retrieve_with_context(query=query, task_type="chat", k=k)
            if not results:
                return "No context found."
            parts = []
            for r in results:
                parts.append(f"[{r.memory_type.value}] {r.content}")
                expanded = r.metadata.get("expanded_context")
                if expanded:
                    parts.append(f"  Related: {expanded}")
            return "\n".join(parts)
        except Exception:
            return "Context retrieval temporarily unavailable."

    return [search_memory, store_memory, get_context]


__all__ = [
    "NeuroMemRetriever",
    "MemoryAugmentedQA",
    "create_neuromem_tools",
]
