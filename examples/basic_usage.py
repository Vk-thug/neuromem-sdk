"""
Basic usage examples for NeuroMem SDK.
"""

import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neuromem import NeuroMem, UserManager


def example_basic_usage():
    """Basic memory operations."""
    print("=== Basic Usage ===\n")
    
    # Create user
    user = UserManager.create(external_id="user_001")
    print(f"Created user: {user.id}\n")
    
    # Initialize memory
    memory = NeuroMem.from_config("neuromem.yaml", user_id=user.id)
    
    # Store some interactions
    memory.observe(
        user_input="I prefer concise answers",
        assistant_output="Understood! I'll keep responses brief."
    )
    
    memory.observe(
        user_input="I work with Python and TypeScript",
        assistant_output="Great! I'll focus on those languages."
    )
    
    # Retrieve memories
    results = memory.retrieve(
        query="What programming languages does the user know?",
        task_type="chat",
        k=3
    )
    
    print("Retrieved memories:")
    for mem in results:
        print(f"  - {mem.content[:80]}...")
    
    print()


def example_langchain_integration():
    """LangChain integration example."""
    print("=== LangChain Integration ===\n")
    
    user = UserManager.create(external_id="user_002")
    
    # Create LangChain-compatible memory
    memory = NeuroMem.for_langchain(user_id=user.id)
    
    print("Memory created for LangChain")
    print("Use with: LLMChain(llm=llm, prompt=prompt, memory=memory)")
    print()


def example_memory_control():
    """User control over memories."""
    print("=== Memory Control ===\n")
    
    user = UserManager.create(external_id="user_003")
    memory = NeuroMem.from_config("neuromem.yaml", user_id=user.id)
    
    # Store a memory
    memory.observe(
        user_input="I live in San Francisco",
        assistant_output="Got it!"
    )
    
    # List memories
    memories = memory.list(limit=10)
    print(f"Total memories: {len(memories)}")
    
    if memories:
        mem = memories[0]
        
        # Explain a memory
        explanation = memory.explain(mem.id)
        print(f"\nMemory explanation:")
        print(f"  Content: {explanation['content'][:60]}...")
        print(f"  Confidence: {explanation['why_used']['confidence']}")
        print(f"  Source: {explanation['source']}")
        
        # Update a memory
        memory.update(mem.id, "Updated content")
        print(f"\nMemory updated")
        
        # Delete a memory
        memory.forget(mem.id)
        print(f"Memory deleted")
    
    print()


def example_consolidation():
    """Memory consolidation example."""
    print("=== Memory Consolidation ===\n")
    
    user = UserManager.create(external_id="user_004")
    memory = NeuroMem.from_config("neuromem.yaml", user_id=user.id)
    
    # Store repeated patterns
    for i in range(5):
        memory.observe(
            user_input="I prefer bullet points",
            assistant_output="Using bullets!"
        )
    
    print("Stored 5 similar interactions")
    
    # Trigger consolidation
    memory.consolidate()
    print("Consolidation complete")
    
    # Check for procedural memories
    procedural = memory.list(memory_type="procedural")
    print(f"\nProcedural memories created: {len(procedural)}")
    for mem in procedural:
        print(f"  - {mem.content}")
    
    print()


if __name__ == "__main__":
    example_basic_usage()
    example_langchain_integration()
    example_memory_control()
    example_consolidation()
    
    print("All examples complete!")
