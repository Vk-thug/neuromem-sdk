"""
Enhanced LangGraph adapter for NeuroMem.

Provides multiple integration patterns:
1. with_memory() - Wrap any graph with memory
2. NeuroMemCheckpointer - Custom checkpointer for persistence
3. create_memory_node() - Memory retrieval node
4. create_observation_node() - Memory storage node
"""

from typing import TypedDict, List, Callable, Dict, Any, Optional
from datetime import datetime
import json


class AgentState(TypedDict):
    """
    Default agent state for LangGraph integration.
    
    Extend this with your own state fields:
        class MyState(AgentState):
            custom_field: str
    """
    input: str
    context: List[str]
    output: str


def with_memory(graph_app, neuromem, k: int = 8):
    """
    Wrap a compiled LangGraph app with automatic memory handling.
    
    This is the simplest way to add memory to LangGraph - just wrap your app!
    
    Args:
        graph_app: Compiled LangGraph application
        neuromem: NeuroMem instance
        k: Number of memories to retrieve
    
    Returns:
        Wrapped app with memory capabilities
    
    Usage:
        from langgraph.graph import StateGraph
        from neuromem import NeuroMem
        from neuromem.adapters.langgraph import with_memory, AgentState
        
        memory = NeuroMem.for_langgraph(user_id="user_123")
        
        # Build your graph
        graph = StateGraph(AgentState)
        graph.add_node("agent", agent_node)
        graph.set_entry_point("agent")
        graph.set_finish_point("agent")
        
        # Wrap with memory - that's it!
        app = with_memory(graph.compile(), memory)
        
        # Use normally
        result = app.invoke({"input": "Hello"})
    """
    class MemoryWrapper:
        def __init__(self, app, nm, k_val):
            self.app = app
            self.neuromem = nm
            self.k = k_val
        
        def invoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
            # 1. Retrieve memories and inject into state
            if "input" in input:
                try:
                    memories = self.neuromem.retrieve(
                        query=input["input"],
                        task_type="chat",
                        k=self.k
                    )
                    input["context"] = [m.content for m in memories]
                except Exception:
                    input["context"] = []
            
            # 2. Run the graph
            result = self.app.invoke(input, config)
            
            # 3. Store observation
            if "input" in result and "output" in result:
                try:
                    self.neuromem.observe(result["input"], result["output"])
                except Exception:
                    pass
            
            return result
        
        async def ainvoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
            # Async version
            if "input" in input:
                try:
                    memories = self.neuromem.retrieve(
                        query=input["input"],
                        task_type="chat",
                        k=self.k
                    )
                    input["context"] = [m.content for m in memories]
                except Exception:
                    input["context"] = []
            
            result = await self.app.ainvoke(input, config)
            
            if "input" in result and "output" in result:
                try:
                    self.neuromem.observe(result["input"], result["output"])
                except Exception:
                    pass
            
            return result
        
        def stream(self, input: Dict[str, Any], config: Optional[Dict] = None):
            """Stream support."""
            if "input" in input:
                try:
                    memories = self.neuromem.retrieve(
                        query=input["input"],
                        task_type="chat",
                        k=self.k
                    )
                    input["context"] = [m.content for m in memories]
                except Exception:
                    input["context"] = []
            
            return self.app.stream(input, config)
    
    return MemoryWrapper(graph_app, neuromem, k)


class NeuroMemCheckpointer:
    """
    Custom LangGraph checkpointer that stores state in NeuroMem.
    
    This allows you to persist graph state across sessions using NeuroMem's
    procedural memory.
    
    Usage:
        from langgraph.checkpoint import MemorySaver
        from neuromem.adapters.langgraph import NeuroMemCheckpointer
        
        checkpointer = NeuroMemCheckpointer(memory)
        app = graph.compile(checkpointer=checkpointer)
    """
    
    def __init__(self, neuromem):
        self.neuromem = neuromem
    
    def put(self, config: Dict, checkpoint: Dict, metadata: Dict) -> Dict:
        """Save checkpoint to NeuroMem."""
        try:
            # Store as procedural memory
            checkpoint_id = config.get("configurable", {}).get("thread_id", "default")
            content = json.dumps({
                "checkpoint": checkpoint,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat()
            })
            
            # Use procedural memory for workflow state
            from neuromem.core.types import MemoryItem, MemoryType
            import uuid
            
            memory_item = MemoryItem(
                id=f"checkpoint_{checkpoint_id}",
                user_id=self.neuromem.user_id,
                content=content,
                embedding=[0.0] * 1536,  # Checkpoints don't need embeddings
                memory_type=MemoryType.PROCEDURAL,
                salience=1.0,
                confidence=1.0,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                decay_rate=0.0,  # Don't decay checkpoints
                reinforcement=1,
                inferred=False,
                editable=False,
                tags=["checkpoint", checkpoint_id]
            )
            
            self.neuromem.controller.procedural.store(memory_item)
            
        except Exception as e:
            print(f"Warning: Checkpoint save failed: {e}")
        
        return config
    
    def get(self, config: Dict) -> Optional[Dict]:
        """Retrieve checkpoint from NeuroMem."""
        try:
            checkpoint_id = config.get("configurable", {}).get("thread_id", "default")
            
            # Retrieve from procedural memory
            memories = self.neuromem.controller.procedural.get_all(limit=100)
            
            for memory in memories:
                if f"checkpoint_{checkpoint_id}" in memory.tags:
                    data = json.loads(memory.content)
                    return data.get("checkpoint")
            
            return None
            
        except Exception:
            return None
    
    def list(self, config: Dict) -> List[Dict]:
        """List all checkpoints."""
        # Not implemented for now
        return []


def create_memory_node(memory, k: int = 8) -> Callable:
    """
    Create a LangGraph node that retrieves memories.
    
    Args:
        memory: NeuroMem instance
        k: Number of memories to retrieve
    
    Returns:
        Node function for LangGraph
    
    Usage:
        graph.add_node("memory", create_memory_node(memory))
    """
    def memory_node(state: AgentState) -> AgentState:
        """Memory retrieval node."""
        try:
            memories = memory.retrieve(
                query=state["input"],
                task_type="chat",
                k=k
            )
            state["context"] = [m.content for m in memories]
        except Exception:
            state["context"] = []
        
        return state
    
    return memory_node


def create_observation_node(memory) -> Callable:
    """
    Create a LangGraph node that stores observations.
    
    Args:
        memory: NeuroMem instance
    
    Returns:
        Node function for LangGraph
    
    Usage:
        graph.add_node("observe", create_observation_node(memory))
    """
    def observation_node(state: AgentState) -> AgentState:
        """Observation storage node."""
        if "input" in state and "output" in state:
            try:
                memory.observe(state["input"], state["output"])
            except Exception:
                pass
        
        return state
    
    return observation_node


def create_memory_agent_node(memory, agent_func: Callable, k: int = 8) -> Callable:
    """
    Create a combined node that retrieves memories and runs the agent.
    
    Args:
        memory: NeuroMem instance
        agent_func: Agent function that takes state and returns state
        k: Number of memories to retrieve
    
    Returns:
        Combined node function
    
    Usage:
        def my_agent(state):
            # Use state["context"] for memory context
            state["output"] = llm.invoke(state["input"])
            return state
        
        graph.add_node("agent", create_memory_agent_node(memory, my_agent))
    """
    def combined_node(state: AgentState) -> AgentState:
        """Combined memory + agent node."""
        # Retrieve memories
        try:
            memories = memory.retrieve(
                query=state["input"],
                task_type="chat",
                k=k
            )
            state["context"] = [m.content for m in memories]
        except Exception:
            state["context"] = []
        
        # Run agent
        state = agent_func(state)
        
        # Store observation
        if "output" in state:
            try:
                memory.observe(state["input"], state["output"])
            except Exception:
                pass
        
        return state
    
    return combined_node


__all__ = [
    "AgentState",
    "with_memory",
    "NeuroMemCheckpointer",
    "create_memory_node",
    "create_observation_node",
    "create_memory_agent_node",
]
