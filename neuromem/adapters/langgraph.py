"""
LangGraph adapter for NeuroMem.

Provides integration with LangGraph's state-based agent framework.
"""

from typing import TypedDict, List, Callable
from neuromem import NeuroMem


class AgentState(TypedDict):
    """
    Default agent state for LangGraph integration.
    
    You can extend this with your own state fields.
    """
    input: str
    context: List[str]
    output: str


def create_memory_node(memory: NeuroMem) -> Callable:
    """
    Create a LangGraph node that retrieves memories.
    
    This node:
    1. Takes the user input from state
    2. Retrieves relevant memories
    3. Adds them to state["context"]
    
    Args:
        memory: NeuroMem instance
    
    Returns:
        Node function for LangGraph
    
    Example:
        >>> from langgraph.graph import StateGraph
        >>> from neuromem.adapters.langgraph import create_memory_node, AgentState
        >>> 
        >>> memory = NeuroMem.for_langgraph(user_id="user_123")
        >>> 
        >>> graph = StateGraph(AgentState)
        >>> graph.add_node("memory", create_memory_node(memory))
        >>> graph.add_node("agent", agent_node)
        >>> 
        >>> graph.set_entry_point("memory")
        >>> graph.add_edge("memory", "agent")
        >>> 
        >>> app = graph.compile()
    """
    def memory_node(state: AgentState) -> AgentState:
        """Memory retrieval node."""
        # Retrieve relevant memories
        memories = memory.retrieve(
            query=state["input"],
            task_type="chat",
            k=8
        )
        
        # Add to context
        state["context"] = [m.content for m in memories]
        
        return state
    
    return memory_node


def create_observation_node(memory: NeuroMem) -> Callable:
    """
    Create a LangGraph node that stores observations.
    
    This node:
    1. Takes input and output from state
    2. Stores them as episodic memory
    
    Args:
        memory: NeuroMem instance
    
    Returns:
        Node function for LangGraph
    
    Example:
        >>> graph.add_node("observe", create_observation_node(memory))
        >>> graph.add_edge("agent", "observe")
    """
    def observation_node(state: AgentState) -> AgentState:
        """Observation storage node."""
        if "input" in state and "output" in state:
            memory.observe(state["input"], state["output"])
        
        return state
    
    return observation_node


def create_memory_agent_node(memory: NeuroMem, agent_func: Callable) -> Callable:
    """
    Create a combined node that retrieves memories and runs the agent.
    
    This is a convenience function that combines memory retrieval
    and agent execution in a single node.
    
    Args:
        memory: NeuroMem instance
        agent_func: Agent function that takes state and returns state
    
    Returns:
        Combined node function
    
    Example:
        >>> def my_agent(state):
        ...     # Use state["context"] for memory context
        ...     state["output"] = llm.invoke(state["input"])
        ...     return state
        >>> 
        >>> graph.add_node("agent", create_memory_agent_node(memory, my_agent))
    """
    def combined_node(state: AgentState) -> AgentState:
        """Combined memory + agent node."""
        # Retrieve memories
        memories = memory.retrieve(
            query=state["input"],
            task_type="chat",
            k=8
        )
        
        # Add to context
        state["context"] = [m.content for m in memories]
        
        # Run agent
        state = agent_func(state)
        
        # Store observation
        if "output" in state:
            memory.observe(state["input"], state["output"])
        
        return state
    
    return combined_node


# Export commonly used types
__all__ = [
    "AgentState",
    "create_memory_node",
    "create_observation_node",
    "create_memory_agent_node",
]
