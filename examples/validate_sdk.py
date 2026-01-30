"""
Validation script for NeuroMem SDK.

This script validates that the SDK functions according to the PRD:
1. Stores episodic memories
2. Promotes memories to semantic/procedural ONLY after reinforcement (repetition >= 3)
3. Retrieves memories with brain-inspired scoring
"""

import os
import sys
import shutil
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neuromem import NeuroMem, UserManager
from neuromem.core.types import MemoryType


def validate_sdk():
    print("=" * 60)
    print("NeuroMem SDK Validation")
    print("=" * 60)
    
    # Clean up previous validation db if exists
    if os.path.exists("validation.db"):
        try:
            os.remove("validation.db")
        except OSError:
            print("⚠️  Warning: Could not remove validation.db (still in use?)")
    
    # 1. Create User
    print("\n1. Creating User...")
    user = UserManager.create(external_id="validator_001")
    print(f"✅ User created: {user.id}")
    
    # 2. Initialize Memory (using SQLite for persistence)
    print("\n2. Initializing Memory...")
    # Create a temporary config for validation
    config_content = """
neuromem:
  model:
    embedding: text-embedding-3-small
    consolidation_llm: gpt-4o-mini
  storage:
    database:
      type: sqlite
      url: validation.db
  memory:
    decay_enabled: true
    min_confidence_threshold: 0.0  # Lower threshold for validation visibility
"""
    with open("validation_config.yaml", "w") as f:
        f.write(config_content)
        
    memory = NeuroMem.from_config("validation_config.yaml", user_id=user.id)
    print("✅ Memory initialized")
    
    try:
        # 3. Validation: Episodic Storage & Retrieval
        print("\n3. Validating Episodic Storage & Retrieval...")
        
        # Store a single fact (Reinforcement = 1)
        fact_1 = "My favorite color is blue."
        print(f"   Observing: '{fact_1}'")
        memory.observe(user_input=fact_1, assistant_output="Noted.")
        
        # Retrieve using EXACT match because mock embeddings are random without API key
        # In production with real embeddings, semantic search works normally.
        print("   Retrieving (using exact match for mock embedding test)...")
        results = memory.retrieve(query=fact_1, k=1)
        
        if results and "blue" in results[0].content:
            print(f"✅ Successful retrieval: '{results[0].content}'")
            # print(f"   Score details: {results[0].metadata}")
        else:
            print("❌ Retrieval failed (Note: Without API key, mock embeddings require exact string match for dot product)")
            
        # 4. Validation: Consolidation Logic (The "PRD Check")
        print("\n4. Validating Consolidation Logic...")
        print("   PRD Requirement: 'Inferred memories are never promoted without repetition.'")
        
        # Trigger consolidation NOW (Should NOT promote 'blue' as reinforcement is only 1)
        print("   Triggering consolidation (Run 1)...")
        memory.consolidate()
        
        semantic = memory.list(memory_type="semantic")
        if len(semantic) == 0:
            print("✅ Correct: Single memory was NOT promoted (Reinforcement < 3)")
        else:
            print(f"❌ Incorrect: Memory was promoted prematurely! ({len(semantic)} semantic items)")
            
        # Now simulate repetition (Reinforcement 2 & 3)
        print("\n   Simulating repetition for reinforcement...")
        preference = "I prefer python over java."
        
        print(f"   Observing (1/3): '{preference}'")
        memory.observe(user_input=preference, assistant_output="Ok.")
        
        print(f"   Observing (2/3): '{preference}'")
        memory.observe(user_input=preference, assistant_output="Understood.")
        
        print(f"   Observing (3/3): '{preference}'")
        memory.observe(user_input=preference, assistant_output="Got it.")
        
        # Check episodic count
        episodic = memory.list(memory_type="episodic")
        print(f"   Total episodic memories: {len(episodic)}")
        
        # Trigger consolidation AGAIN
        print("   Triggering consolidation (Run 2)...")
        memory.consolidate()
        
        # Check for promotion
        semantic = memory.list(memory_type="semantic")
        procedural = memory.list(memory_type="procedural")
        
        promoted = semantic + procedural
        
        if len(promoted) > 0:
            print(f"✅ Correct: Repeated memory WAS promoted!")
            for m in promoted:
                print(f"   - [{m.memory_type}] {m.content} (Confidence: {m.confidence:.2f})")
        else:
            print("❌ Failed: Repeated memory was NOT promoted.")
            
    finally:
        # 5. Cleanup
        print("\n5. Cleaning up...")
        if hasattr(memory, 'close'):
            memory.close()
            
        if os.path.exists("validation_config.yaml"):
            try:
                os.remove("validation_config.yaml")
            except:
                pass
        # Note: validation.db might still be locked by OS for a moment, so we don't delete it here
        # It will be cleared on next run
        
    print("\n" + "=" * 60)
    print("Validation Complete")
    print("=" * 60)

if __name__ == "__main__":
    validate_sdk()
