"""
LangGraph adapter for NeuroMem.

Compatible with langgraph >= 0.2.x / 1.x (2025-2026 APIs).

Provides:
1. with_memory() — Wrap any compiled graph with memory (invoke, ainvoke, stream, astream)
2. create_memory_node() — Memory retrieval node (returns dict, never mutates state)
3. create_observation_node() — Memory storage node
4. create_memory_agent_node() — Combined retrieval + agent + storage node
5. NeuroMemStore — LangGraph BaseStore implementation for cross-thread memory

Nodes follow LangGraph convention: return dicts with keys to update, never mutate state.
"""

from typing import List, Callable, Dict, Any, Optional, Iterator
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


def with_memory(graph_app: Any, neuromem: Any, k: int = 8) -> Any:
    """
    Wrap a compiled LangGraph app with automatic memory retrieval and storage.

    Supports invoke, ainvoke, stream, and astream.

    Args:
        graph_app: Compiled LangGraph application
        neuromem: NeuroMem instance
        k: Number of memories to retrieve

    Returns:
        Wrapped app with memory capabilities

    Usage:
        graph = StateGraph(MyState)
        graph.add_node("agent", agent_node)
        graph.add_edge(START, "agent")
        graph.add_edge("agent", END)

        app = with_memory(graph.compile(), memory)
        result = app.invoke({"messages": [HumanMessage("Hello")]})

        # Streaming:
        for chunk in app.stream({"messages": [HumanMessage("Hello")]}):
            print(chunk)
    """

    class MemoryWrapper:
        def __init__(self, app: Any, nm: Any, k_val: int):
            self.app = app
            self.neuromem = nm
            self.k = k_val

        def invoke(
            self, input: Dict[str, Any], config: Optional[Dict] = None, **kwargs
        ) -> Dict[str, Any]:
            enriched = self._inject_memory(input)
            result = self.app.invoke(enriched, config, **kwargs)
            self._store_observation(input, result)
            return result

        async def ainvoke(
            self, input: Dict[str, Any], config: Optional[Dict] = None, **kwargs
        ) -> Dict[str, Any]:
            enriched = self._inject_memory(input)
            result = await self.app.ainvoke(enriched, config, **kwargs)
            self._store_observation(input, result)
            return result

        def stream(
            self, input: Dict[str, Any], config: Optional[Dict] = None, **kwargs
        ) -> Iterator:
            """
            Stream graph execution with memory context.

            Supports all LangGraph stream_mode values:
            'values', 'updates', 'messages', 'custom', etc.
            """
            enriched = self._inject_memory(input)
            collected_output = []

            for chunk in self.app.stream(enriched, config, **kwargs):
                yield chunk
                # Try to capture final output for observation
                if isinstance(chunk, dict):
                    collected_output.append(chunk)

            # Store observation from collected output
            if collected_output:
                self._store_from_stream(input, collected_output)

        async def astream(
            self, input: Dict[str, Any], config: Optional[Dict] = None, **kwargs
        ):
            """Async stream with memory context."""
            enriched = self._inject_memory(input)
            collected_output = []

            async for chunk in self.app.astream(enriched, config, **kwargs):
                yield chunk
                if isinstance(chunk, dict):
                    collected_output.append(chunk)

            if collected_output:
                self._store_from_stream(input, collected_output)

        def get_state(self, config: Dict) -> Any:
            """Pass through to underlying graph."""
            return self.app.get_state(config)

        def get_state_history(self, config: Dict) -> Any:
            """Pass through to underlying graph."""
            return self.app.get_state_history(config)

        def update_state(self, config: Dict, values: Dict, **kwargs) -> Any:
            """Pass through to underlying graph."""
            return self.app.update_state(config, values, **kwargs)

        def _inject_memory(self, input: Dict[str, Any]) -> Dict[str, Any]:
            """Retrieve memories and inject into input state."""
            query = self._extract_query(input)
            if not query:
                return input

            try:
                memories = self.neuromem.retrieve(query=query, task_type="chat", k=self.k)
                context = [m.content for m in memories]
            except Exception as e:
                logger.warning("Memory retrieval failed", extra={"error": str(e)[:200]})
                context = []

            enriched = dict(input)

            # Inject as 'context' key
            if context:
                enriched["context"] = context

            # Also inject into messages if present
            if context and "messages" in enriched and isinstance(enriched["messages"], list):
                from langchain_core.messages import SystemMessage

                ctx_text = "\n".join([f"- {c}" for c in context])
                ctx_msg = SystemMessage(content=f"FACTS ABOUT THE USER:\n{ctx_text}")
                msgs = list(enriched["messages"])
                if msgs and isinstance(msgs[0], SystemMessage):
                    msgs.insert(1, ctx_msg)
                else:
                    msgs.insert(0, ctx_msg)
                enriched["messages"] = msgs

            return enriched

        def _store_observation(self, input: Dict[str, Any], result: Dict[str, Any]) -> None:
            """Store observation from invoke result, skipping junk responses."""
            user_input = self._extract_query(input)
            output = self._extract_output(result)
            if user_input and output and not self._is_junk_response(output):
                try:
                    self.neuromem.observe(user_input, output)
                except Exception:
                    pass

        @staticmethod
        def _is_junk_response(output: str) -> bool:
            """Check if the response is uninformative and should not be stored."""
            output_lower = output.lower()
            junk_markers = [
                "i don't have access to personal",
                "i don't have any information",
                "i don't have personal information",
                "i'm not sure what",
                "could you provide more context",
                "unless it has been shared",
                "i need more context",
                "wasn't mentioned in the provided memory",
                "wasn't mentioned in our past",
                "i don't have enough information",
            ]
            return any(marker in output_lower for marker in junk_markers)

        def _store_from_stream(
            self, input: Dict[str, Any], chunks: List[Dict[str, Any]]
        ) -> None:
            """Store observation from streamed chunks.

            LangGraph stream chunks have the format:
            {node_name: {key: value, ...}}
            We need to unwrap the node name layer.
            """
            user_input = self._extract_query(input)
            if not user_input:
                return

            # Try to find output from chunks (unwrap node layer)
            output = ""
            for chunk in reversed(chunks):
                # LangGraph wraps updates under node name
                if isinstance(chunk, dict):
                    for node_name, node_update in chunk.items():
                        if isinstance(node_update, dict):
                            output = self._extract_output(node_update)
                            if output:
                                break
                    if output:
                        break
                output = self._extract_output(chunk)
                if output:
                    break

            if user_input and output and not self._is_junk_response(output):
                try:
                    self.neuromem.observe(user_input, output)
                except Exception:
                    pass

        def _extract_query(self, input: Dict[str, Any]) -> str:
            """Extract query from various state shapes."""
            if "input" in input:
                return str(input["input"])
            if "question" in input:
                return str(input["question"])
            if "messages" in input and isinstance(input["messages"], list):
                for msg in reversed(input["messages"]):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        # Only extract from human messages
                        from langchain_core.messages import HumanMessage

                        if isinstance(msg, HumanMessage):
                            return msg.content
                    elif isinstance(msg, dict) and msg.get("role") == "user":
                        return msg.get("content", "")
            return ""

        def _extract_output(self, result: Dict[str, Any]) -> str:
            """Extract output text from various result shapes."""
            if isinstance(result, str):
                return result
            if not isinstance(result, dict):
                return str(result) if result else ""

            if "output" in result:
                return str(result["output"])
            if "answer" in result:
                return str(result["answer"])
            if "messages" in result and isinstance(result["messages"], list):
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content"):
                        from langchain_core.messages import AIMessage

                        if isinstance(msg, AIMessage):
                            return msg.content
            return ""

    return MemoryWrapper(graph_app, neuromem, k)


def create_memory_node(memory: Any, k: int = 8) -> Callable:
    """
    Create a LangGraph node that retrieves memories.

    Returns a dict update (LangGraph convention), never mutates state.

    Args:
        memory: NeuroMem instance
        k: Number of memories to retrieve

    Returns:
        Node function for StateGraph

    Usage:
        graph.add_node("memory", create_memory_node(memory))
    """

    def memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Memory retrieval node — returns context update dict."""
        query = state.get("input", "")
        if not query and "messages" in state:
            msgs = state["messages"]
            if msgs:
                last = msgs[-1]
                query = last.content if hasattr(last, "content") else str(last)

        try:
            memories = memory.retrieve(query=query, task_type="chat", k=k)
            context = [m.content for m in memories]
        except Exception:
            context = []

        return {"context": context}

    return memory_node


def create_observation_node(memory: Any) -> Callable:
    """
    Create a LangGraph node that stores observations.

    Returns an empty dict (no state changes) — only side effect is storage.

    Args:
        memory: NeuroMem instance

    Returns:
        Node function for StateGraph
    """

    def observation_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Observation storage node — stores and returns empty update."""
        user_input = state.get("input", "")
        output = state.get("output", "")

        if not user_input and "messages" in state:
            msgs = state["messages"]
            for msg in reversed(msgs):
                if hasattr(msg, "content"):
                    from langchain_core.messages import HumanMessage

                    if isinstance(msg, HumanMessage):
                        user_input = msg.content
                        break

        if not output and "messages" in state:
            msgs = state["messages"]
            for msg in reversed(msgs):
                if hasattr(msg, "content"):
                    from langchain_core.messages import AIMessage

                    if isinstance(msg, AIMessage):
                        output = msg.content
                        break

        if user_input and output:
            try:
                memory.observe(user_input, output)
            except Exception:
                pass

        return {}  # No state update — side effect only

    return observation_node


def create_memory_agent_node(
    memory: Any, agent_func: Callable, k: int = 8
) -> Callable:
    """
    Create a combined node: retrieve memories -> run agent -> store observation.

    The agent_func receives state with 'context' populated from memory
    and must return a dict update (LangGraph convention).

    Args:
        memory: NeuroMem instance
        agent_func: Agent function: (state: dict) -> dict
        k: Number of memories to retrieve

    Returns:
        Combined node function

    Usage:
        def my_agent(state):
            context = state.get("context", [])
            # Use context...
            return {"output": "response", "messages": [...]}

        graph.add_node("agent", create_memory_agent_node(memory, my_agent))
    """

    def combined_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Combined memory + agent node."""
        # 1. Retrieve memories
        query = state.get("input", "")
        if not query and "messages" in state:
            msgs = state["messages"]
            if msgs:
                last = msgs[-1]
                query = last.content if hasattr(last, "content") else str(last)

        try:
            memories = memory.retrieve(query=query, task_type="chat", k=k)
            context = [m.content for m in memories]
        except Exception:
            context = []

        # 2. Inject context into state copy for agent
        state_with_context = dict(state)
        state_with_context["context"] = context

        # 3. Run agent — must return a dict update
        result = agent_func(state_with_context)

        # 4. Store observation
        output = ""
        if isinstance(result, dict):
            output = result.get("output", "")
            if not output and "messages" in result:
                msgs = result["messages"]
                if msgs:
                    last = msgs[-1] if isinstance(msgs, list) else msgs
                    output = last.content if hasattr(last, "content") else str(last)

        if query and output:
            try:
                memory.observe(query, output)
            except Exception:
                pass

        return result

    return combined_node


# Type alias
Any = object

__all__ = [
    "with_memory",
    "create_memory_node",
    "create_observation_node",
    "create_memory_agent_node",
]
