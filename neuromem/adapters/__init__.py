"""Framework adapters for NeuroMem"""

from neuromem.adapters.langchain import (
    NeuroMemRunnable,
    NeuroMemChatMessageHistory,
    add_memory,
    NeuroMemLangChain,
    LangChainMemoryAdapter,
)

from neuromem.adapters.langgraph import (
    AgentState,
    with_memory,
    NeuroMemCheckpointer,
    create_memory_node,
    create_observation_node,
    create_memory_agent_node,
)

# LiteLLM imports (optional - only if litellm is installed)
try:
    from neuromem.adapters.litellm import (
        NeuroMemLiteLLM,
        completion_with_memory,
        acompletion_with_memory,
    )
    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False
    NeuroMemLiteLLM = None
    completion_with_memory = None
    acompletion_with_memory = None

__all__ = [
    # LangChain
    "NeuroMemRunnable",
    "NeuroMemChatMessageHistory",
    "add_memory",
    "NeuroMemLangChain",
    "LangChainMemoryAdapter",
    # LangGraph
    "AgentState",
    "with_memory",
    "NeuroMemCheckpointer",
    "create_memory_node",
    "create_observation_node",
    "create_memory_agent_node",
    # LiteLLM
    "NeuroMemLiteLLM",
    "completion_with_memory",
    "acompletion_with_memory",
]
