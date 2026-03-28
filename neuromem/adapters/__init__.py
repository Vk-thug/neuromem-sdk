"""
Framework adapters for NeuroMem.

All imports are lazy — only loaded when the corresponding
framework package is installed.
"""

# LangChain adapter (requires: pip install langchain langchain-core)
try:
    from neuromem.adapters.langchain import (
        NeuroMemRunnable,
        NeuroMemChatMessageHistory,
        add_memory,
        NeuroMemLangChain,
        LangChainMemoryAdapter,
    )

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    NeuroMemRunnable = None  # type: ignore
    NeuroMemChatMessageHistory = None  # type: ignore
    add_memory = None  # type: ignore
    NeuroMemLangChain = None  # type: ignore
    LangChainMemoryAdapter = None  # type: ignore

# LangGraph adapter (requires: pip install langgraph)
try:
    from neuromem.adapters.langgraph import (
        with_memory,
        create_memory_node,
        create_observation_node,
        create_memory_agent_node,
    )

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    with_memory = None  # type: ignore
    create_memory_node = None  # type: ignore
    create_observation_node = None  # type: ignore
    create_memory_agent_node = None  # type: ignore

# LiteLLM adapter (requires: pip install litellm)
try:
    from neuromem.adapters.litellm import (
        NeuroMemLiteLLM,
        completion_with_memory,
        acompletion_with_memory,
    )

    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False
    NeuroMemLiteLLM = None  # type: ignore
    completion_with_memory = None  # type: ignore
    acompletion_with_memory = None  # type: ignore

# CrewAI adapter (requires: pip install crewai)
try:
    from neuromem.adapters.crewai import (
        NeuroMemSearchTool,
        NeuroMemStoreTool,
        NeuroMemConsolidateTool,
        NeuroMemContextTool,
        create_neuromem_tools as create_crewai_tools,
    )

    _CREWAI_AVAILABLE = True
except (ImportError, NameError, TypeError):
    _CREWAI_AVAILABLE = False
    NeuroMemSearchTool = None  # type: ignore
    NeuroMemStoreTool = None  # type: ignore
    NeuroMemConsolidateTool = None  # type: ignore
    NeuroMemContextTool = None  # type: ignore
    create_crewai_tools = None  # type: ignore

# AutoGen / AG2 adapter (requires: pip install ag2)
try:
    from neuromem.adapters.autogen import (
        register_neuromem_tools,
        NeuroMemCapability,
    )

    _AUTOGEN_AVAILABLE = True
except (ImportError, NameError, TypeError):
    _AUTOGEN_AVAILABLE = False
    register_neuromem_tools = None  # type: ignore
    NeuroMemCapability = None  # type: ignore

# DSPy adapter (requires: pip install dspy)
try:
    from neuromem.adapters.dspy import (
        NeuroMemRetriever as DSPyRetriever,
        MemoryAugmentedQA,
        create_neuromem_tools as create_dspy_tools,
    )

    _DSPY_AVAILABLE = True
except (ImportError, NameError, TypeError):
    _DSPY_AVAILABLE = False
    DSPyRetriever = None  # type: ignore
    MemoryAugmentedQA = None  # type: ignore
    create_dspy_tools = None  # type: ignore

# Haystack adapter (requires: pip install haystack-ai)
try:
    from neuromem.adapters.haystack import (
        NeuroMemRetriever as HaystackRetriever,
        NeuroMemWriter,
        NeuroMemContextRetriever,
    )

    _HAYSTACK_AVAILABLE = True
except (ImportError, NameError, TypeError):
    _HAYSTACK_AVAILABLE = False
    HaystackRetriever = None  # type: ignore
    NeuroMemWriter = None  # type: ignore
    NeuroMemContextRetriever = None  # type: ignore

# Semantic Kernel adapter (requires: pip install semantic-kernel)
try:
    from neuromem.adapters.semantic_kernel import (
        NeuroMemPlugin,
        create_neuromem_plugin,
    )

    _SEMANTIC_KERNEL_AVAILABLE = True
except (ImportError, NameError, TypeError):
    _SEMANTIC_KERNEL_AVAILABLE = False
    NeuroMemPlugin = None  # type: ignore
    create_neuromem_plugin = None  # type: ignore

__all__ = [
    # LangChain
    "NeuroMemRunnable",
    "NeuroMemChatMessageHistory",
    "add_memory",
    "NeuroMemLangChain",
    "LangChainMemoryAdapter",
    # LangGraph
    "with_memory",
    "create_memory_node",
    "create_observation_node",
    "create_memory_agent_node",
    # LiteLLM
    "NeuroMemLiteLLM",
    "completion_with_memory",
    "acompletion_with_memory",
    # CrewAI
    "NeuroMemSearchTool",
    "NeuroMemStoreTool",
    "NeuroMemConsolidateTool",
    "NeuroMemContextTool",
    "create_crewai_tools",
    # AutoGen
    "register_neuromem_tools",
    "NeuroMemCapability",
    # DSPy
    "DSPyRetriever",
    "MemoryAugmentedQA",
    "create_dspy_tools",
    # Haystack
    "HaystackRetriever",
    "NeuroMemWriter",
    "NeuroMemContextRetriever",
    # Semantic Kernel
    "NeuroMemPlugin",
    "create_neuromem_plugin",
]
