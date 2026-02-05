"""
Simple LangGraph + NeuroMem Example

Shows how to add memory to any LangGraph app in just 1 line!
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from neuromem import NeuroMem
from neuromem.adapters.langgraph import with_memory, AgentState

# 1. Initialize NeuroMem
memory = NeuroMem.for_langgraph(user_id="demo_user")

# 2. Define your agent (as usual)
llm = ChatOpenAI(model="gpt-4o-mini")

def agent_node(state: AgentState) -> AgentState:
    """Simple agent that uses memory context."""
    # Memory context is automatically injected into state["context"]
    context_str = "\n".join(state.get("context", []))
    
    prompt = f"""You are a helpful assistant.

Context from memory:
{context_str}

User: {state['input']}

Respond naturally and use the context if relevant."""
    
    response = llm.invoke(prompt)
    state["output"] = response.content
    return state

# 3. Build your graph (as usual)
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.set_entry_point("agent")
graph.set_finish_point("agent")

# 4. Wrap with memory - that's it!
app = with_memory(graph.compile(), memory)

# 5. Use it!
if __name__ == "__main__":
    print("🧠 LangGraph + NeuroMem Demo\n")
    
    # First conversation
    result1 = app.invoke({"input": "My name is Bob and I'm a data scientist"})
    print(f"User: My name is Bob and I'm a data scientist")
    print(f"Assistant: {result1['output']}\n")
    
    # Second conversation - memory will recall!
    result2 = app.invoke({"input": "What do I do for work?"})
    print(f"User: What do I do for work?")
    print(f"Assistant: {result2['output']}\n")
    
    # Third conversation
    result3 = app.invoke({"input": "What's my name again?"})
    print(f"User: What's my name again?")
    print(f"Assistant: {result3['output']}\n")
    
    print("✅ Memory is working! The assistant remembered your name and job.")
