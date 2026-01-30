"""
Production-ready LangGraph agent with NeuroMem.

This is a complete, production-grade example showing:
- Real LangGraph StateGraph
- OpenAI GPT-4 integration
- Memory-enhanced responses
- Proper error handling
- Streaming support (optional)

Setup:
    pip install langgraph openai
    export OPENAI_API_KEY=your_key_here
"""

import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from openai import OpenAI
from neuromem import NeuroMem, UserManager


class AgentState(TypedDict):
    """State for the memory-enhanced agent."""
    input: str
    context: List[str]
    output: str


def create_production_agent(user_id: str, config_path: str = "neuromem.yaml"):
    """
    Create a production-ready agent with NeuroMem.
    
    Args:
        user_id: User ID for memory isolation
        config_path: Path to NeuroMem config
    
    Returns:
        Compiled LangGraph application
    """
    # Initialize NeuroMem
    memory = NeuroMem.from_config(config_path, user_id=user_id)
    
    # Initialize OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "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")
    
    # Define nodes
    def retrieve_memories(state: AgentState) -> AgentState:
        """Retrieve relevant memories."""
        memories = memory.retrieve(
            query=state["input"],
            task_type="chat",
            k=8
        )
        state["context"] = [m.content for m in memories]
        return state
    
    def generate_response(state: AgentState) -> AgentState:
        """Generate LLM response with memory context."""
        # Build system prompt with memory
        if state["context"]:
            context_text = "\n".join([f"- {ctx}" for ctx in state["context"]])
            system_prompt = f"""You are a helpful AI assistant with memory.

What you know about the user:
{context_text}

Use this context to personalize your response. Honor user preferences."""
        else:
            system_prompt = "You are a helpful AI assistant."
        
        # Call LLM
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state["input"]}
            ],
            temperature=0.7
        )
        
        state["output"] = response.choices[0].message.content
        return state
    
    def store_interaction(state: AgentState) -> AgentState:
        """Store interaction in memory."""
        memory.observe(state["input"], state["output"])
        return state
    
    # Build graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("retrieve", retrieve_memories)
    workflow.add_node("generate", generate_response)
    workflow.add_node("store", store_interaction)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "store")
    workflow.add_edge("store", END)
    
    return workflow.compile(), memory


def main():
    """Run production agent demo."""
    print("=" * 70)
    print("Production LangGraph Agent with NeuroMem")
    print("=" * 70)
    
    # Create user
    user = UserManager.create(external_id="prod_user_001")
    print(f"\n✅ User created: {user.id}")
    
    # Create agent
    print("🔧 Building agent...")
    app, memory = create_production_agent(user.id)
    print("✅ Agent ready\n")
    
    # Test conversations
    conversations = [
        "I prefer concise, bullet-point answers with technical depth",
        "What is a vector database and how does it work?",
        "I'm building a RAG system. What embedding model should I use?",
        "Can you explain the difference between semantic and episodic memory?",
        "Based on what you know about me, how should you format your answers?",
    ]
    
    for i, user_input in enumerate(conversations, 1):
        print(f"\n{'='*70}")
        print(f"Turn {i}")
        print(f"{'='*70}")
        print(f"\n👤 User: {user_input}\n")
        
        # Run agent
        result = app.invoke({
            "input": user_input,
            "context": [],
            "output": ""
        })
        
        print(f"🤖 Assistant: {result['output']}\n")
        
        # Show memory stats periodically
        if i % 2 == 0:
            episodic = memory.list(memory_type="episodic", limit=10)
            print(f"📊 Memory Stats: {len(episodic)} episodic memories stored")
    
    # Trigger consolidation
    print(f"\n{'='*70}")
    print("🧠 Triggering Memory Consolidation...")
    print(f"{'='*70}\n")
    
    memory.consolidate()
    
    # Show consolidated memories
    semantic = memory.list(memory_type="semantic", limit=5)
    procedural = memory.list(memory_type="procedural", limit=5)
    
    print(f"✅ Consolidation complete!")
    print(f"\n📚 Semantic memories: {len(semantic)}")
    for mem in semantic:
        print(f"  • {mem.content[:80]}...")
    
    print(f"\n🎯 Procedural memories: {len(procedural)}")
    for mem in procedural:
        print(f"  • {mem.content[:80]}...")
    
    # Test memory explanation
    if semantic:
        print(f"\n{'='*70}")
        print("🔍 Memory Explanation")
        print(f"{'='*70}\n")
        
        explanation = memory.explain(semantic[0].id)
        print(f"Content: {explanation['content'][:100]}...")
        print(f"Type: {explanation['memory_type']}")
        print(f"Source: {explanation['source']}")
        print(f"Confidence: {explanation['why_used']['confidence']:.2f}")
        print(f"Salience: {explanation['why_used']['salience']:.2f}")
    
    print(f"\n{'='*70}")
    print("✅ Demo Complete!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
