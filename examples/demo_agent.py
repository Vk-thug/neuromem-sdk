"""
Minimal Demo: NeuroMem + LangChain with Automatic Memory

The LangChain adapter handles EVERYTHING automatically:
- Pre-processor: Retrieves memories and adds to system prompt
- Post-processor: Stores conversations after LLM response

No manual memory operations needed!

Requirements:
    pip install langchain langchain-openai
    Set OPENAI_API_KEY in environment
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neuromem import NeuroMem, UserManager
from neuromem.adapters.langchain import NeuroMemLangChain
from langchain_openai import ChatOpenAI
from datetime import datetime


def main():
    """Run minimal demo with automatic memory handling."""
    
    print("=" * 60)
    print("🧠 NeuroMem + LangChain: Automatic Memory Demo")
    print("=" * 60)
    print("\nThe adapter automatically:")
    print("  ✅ Retrieves memories before LLM call")
    print("  ✅ Adds them to system prompt")
    print("  ✅ Stores conversations after LLM response")
    print()
    
    # 1. Create user
    user = UserManager.create(
        external_id=f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    print(f"✅ User: {user.id}")
    
    # 2. Initialize NeuroMem
    config_path = os.path.join(os.path.dirname(__file__), "neuromem.yaml")
    memory = NeuroMem.from_config(config_path, user_id=user.id)
    print("✅ NeuroMem initialized")
    
    # 3. Create LangChain adapter (handles everything automatically)
    memory_adapter = NeuroMemLangChain(memory, k=5)
    print("✅ Memory adapter created")
    
    # 4. Initialize LLM
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ OPENAI_API_KEY not set!")
        print("Set it with: export OPENAI_API_KEY=your_key_here")
        return
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    print("✅ LLM initialized\n")
    
    # 6. Interactive chat
    print("=" * 60)
    print("💬 Chat (type 'quit' to exit)")
    print("=" * 60)
    
    turn = 0
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == '/consolidate':
                print("\n🧠 Triggering consolidation...")
                memory.consolidate()
                print("✅ Consolidation complete!")
                
                # Show semantic memories
                semantic = memory.list(memory_type="semantic", limit=10)
                print(f"\n[📚 Semantic Knowledge ({len(semantic)})]")
                for mem in semantic:
                    print(f"  - {mem.content} (Conf: {mem.confidence:.2f})")
                    if mem.metadata:
                        print(f"    Type: {mem.metadata.get('fact_type')}")
                continue
            
            turn += 1
            print(f"\n--- Turn {turn} ---")
            
            # The adapter automatically:
            # 1. Retrieves memories (pre-processor)
            # 2. Adds to system prompt
            # 3. Calls LLM
            # 4. Stores conversation (post-processor)
            
            # Use lower-level retrieve method first to show what's happening
            print("  🔍 Retrieving memories...")
            retrieved = memory.retrieve(user_input, k=3)
            if retrieved:
                for i, mem in enumerate(retrieved):
                    why = memory.explain(mem.id).get("why_used", {})
                    print(f"     {i+1}. [{mem.memory_type.value.upper()}] (Score: {why.get('final_score', 'N/A'):.2f})")
                    print(f"        - Sim: {why.get('similarity', 0):.2f} | Recency: 0.2 | Salience: {mem.salience:.2f}")
                    if mem.tags:
                        print(f"        - Tags: {mem.tags}")
                    print(f"        - Content: {mem.content[:60]}...")
            else:
                print("     (No relevant memories found)")
            
            # Now run the chat
            response = memory_adapter.chat(llm, user_input)
            
            print(f"\n Agent: {response}")
            
            # Show the newly stored memory
            latest = memory.list(memory_type="episodic", limit=1)
            if latest:
                m = latest[0]
                print(f"\n[💾 Memory stored]")
                print(f"  - Tags: {m.tags}")
                if m.metadata:
                    print(f"  - Intent: {m.metadata.get('intent')}")
                    print(f"  - Entities: {m.metadata.get('entities')}")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Show final stats
    print("\n" + "=" * 60)
    print("📊 Final Statistics")
    print("=" * 60)
    
    episodic = memory.list(memory_type="episodic", limit=100)
    semantic = memory.list(memory_type="semantic", limit=100)
    
    print(f"\nMemories stored:")
    print(f"  - Episodic: {len(episodic)}")
    print(f"  - Semantic: {len(semantic)}")
    
    if episodic:
        print(f"\n📚 Recent conversations:")
        for mem in episodic[:3]:
            print(f"  - {mem.content[:80]}...")
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
