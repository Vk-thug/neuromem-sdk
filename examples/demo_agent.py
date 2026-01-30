"""
Demo LangGraph agent with NeuroMem integration.

This demonstrates a complete production-ready agent that:
1. Uses real LangGraph StateGraph
2. Integrates with OpenAI LLM
3. Retrieves relevant memories
4. Processes user input with context
5. Stores observations
6. Learns user style over time

Requirements:
    pip install langgraph openai
    export OPENAI_API_KEY=your_key_here
"""

import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import TypedDict, List, Annotated
from neuromem import NeuroMem, UserManager

try:
    from langgraph.graph import StateGraph, END
    from openai import OpenAI
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("⚠️  LangGraph not installed. Install with: pip install langgraph openai")


# Define agent state
class AgentState(TypedDict):
    """State for the LangGraph agent."""
    input: str
    context: List[str]
    output: str
    messages: List[str]


def create_demo_agent():
    """Create a production-ready demo agent with memory."""
    
    if not LANGGRAPH_AVAILABLE:
        print("❌ Cannot create agent without LangGraph. Please install dependencies.")
        return None, None
    
    # 1. Create user
    user = UserManager.create(external_id="demo_user_123")
    print(f"✅ Created user: {user.id}")
    
    # 2. Initialize memory
    memory = NeuroMem.from_config("neuromem.yaml", user_id=user.id)
    print("✅ Initialized NeuroMem")
    
    # 3. Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY") or "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"
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set. Using mock responses.")
        client = None
    else:
        client = OpenAI(api_key=api_key)
        print("✅ OpenAI client initialized")
    
    # 4. Define memory retrieval node
    def memory_node(state: AgentState) -> AgentState:
        """Retrieve relevant memories based on user input."""
        print(f"  🧠 Retrieving memories for: '{state['input'][:50]}...'")
        
        memories = memory.retrieve(
            query=state["input"],
            task_type="chat",
            k=5
        )
        
        state["context"] = [m.content for m in memories]
        print(f"  📚 Retrieved {len(memories)} memories")
        
        return state
    
    # 5. Define agent node with real LLM
    def agent_node(state: AgentState) -> AgentState:
        """Process user input with LLM, using memory context."""
        user_input = state["input"]
        context = state.get("context", [])
        
        # Build prompt with memory context
        if context:
            context_text = "\n".join([f"- {ctx}" for ctx in context[:3]])
            system_prompt = f"""You are a helpful AI assistant with memory of past interactions.

Here's what you know about the user:
{context_text}

Use this context to personalize your response. If the user has preferences (e.g., concise answers, technical depth), honor them."""
        else:
            system_prompt = "You are a helpful AI assistant."
        
        # Call LLM
        if client:
            try:
                print(f"  🤖 Calling LLM...")
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                output = response.choices[0].message.content
                print(f"  ✅ LLM response generated")
            except Exception as e:
                print(f"  ⚠️  LLM error: {e}")
                output = f"[Error calling LLM: {str(e)}]"
        else:
            # Mock response when no API key
            if context:
                output = f"Based on what I know about you:\n{context_text}\n\nRegarding '{user_input}': I understand your question and would provide a detailed answer here."
            else:
                output = f"Regarding '{user_input}': I would provide a helpful answer here."
        
        state["output"] = output
        return state
    
    # 6. Define observation node
    def observe_node(state: AgentState) -> AgentState:
        """Store the interaction in memory."""
        print(f"  💾 Storing interaction in memory...")
        memory.observe(state["input"], state["output"])
        return state
    
    # 7. Build LangGraph
    print("🔧 Building LangGraph...")
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("retrieve_memory", memory_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("observe", observe_node)
    
    # Define edges
    workflow.set_entry_point("retrieve_memory")
    workflow.add_edge("retrieve_memory", "agent")
    workflow.add_edge("agent", "observe")
    workflow.add_edge("observe", END)
    
    # Compile graph
    app = workflow.compile()
    print("✅ LangGraph compiled")
    
    # Wrapper function
    def run_agent(user_input: str) -> str:
        """Run the agent pipeline."""
        initial_state = AgentState(
            input=user_input,
            context=[],
            output="",
            messages=[]
        )
        
        result = app.invoke(initial_state)
        return result["output"]
    
    return run_agent, memory


def main():
    """Run the demo."""
    print("=" * 60)
    print("NeuroMem Demo Agent")
    print("=" * 60)
    print()
    
    # Create agent
    run_agent, memory = create_demo_agent()
    
    if run_agent is None:
        print("❌ Agent creation failed (missing dependencies).")
        return
    
    # Simulate conversation
    interactions = [
        "I prefer concise, bullet-point answers",
        "What is a vector database?",
        "I like technical depth in explanations",
        "Explain how embeddings work",
        "Can you summarize what you know about my preferences?",
    ]
    
    for i, user_input in enumerate(interactions, 1):
        print(f"\n--- Turn {i} ---")
        print(f"User: {user_input}")
        
        response = run_agent(user_input)
        print(f"Agent: {response}")
        
        # Show memory stats after each turn
        if i % 2 == 0:
            print("\n[Memory Stats]")
            episodic = memory.list(memory_type="episodic", limit=10)
            print(f"Episodic memories: {len(episodic)}")
    
    # Trigger consolidation
    print("\n" + "=" * 60)
    print("Triggering memory consolidation...")
    memory.consolidate()
    
    # Show consolidated memories
    print("\n[Consolidated Memories]")
    semantic = memory.list(memory_type="semantic", limit=5)
    procedural = memory.list(memory_type="procedural", limit=5)
    
    print(f"\nSemantic memories: {len(semantic)}")
    for mem in semantic:
        print(f"  - {mem.content[:100]}...")
    
    print(f"\nProcedural memories: {len(procedural)}")
    for mem in procedural:
        print(f"  - {mem.content[:100]}...")
    
    # Test memory explanation
    if semantic:
        print("\n" + "=" * 60)
        print("Memory Explanation Example:")
        explanation = memory.explain(semantic[0].id)
        print(f"Content: {explanation['content']}")
        print(f"Type: {explanation['memory_type']}")
        print(f"Source: {explanation['source']}")
        print(f"Confidence: {explanation['why_used']['confidence']}")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
