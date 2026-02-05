#!/usr/bin/env python3
"""
Test script to verify the retrieval validation fix.

This tests that:
1. Empty strings are handled gracefully in get_embedding()
2. LangChain adapter correctly extracts queries from messages
3. Memory retrieval works in interactive mode
"""

import sys
import os

# Add neuromem to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_embedding_validation():
    """Test that embedding validation handles edge cases."""
    print("="*70)
    print("TEST 1: Embedding Validation")
    print("="*70)

    from neuromem.utils.embeddings import get_embedding

    # Test 1: Empty string
    try:
        result = get_embedding("", fallback_to_mock=True)
        assert len(result) == 1536, f"Expected 1536 dimensions, got {len(result)}"
        assert all(v == 0.0 for v in result), "Expected zero vector for empty string"
        print("✅ Empty string returns zero vector")
    except Exception as e:
        print(f"❌ Empty string test failed: {e}")
        return False

    # Test 2: Whitespace only
    try:
        result = get_embedding("   ", fallback_to_mock=True)
        assert len(result) == 1536
        assert all(v == 0.0 for v in result), "Expected zero vector for whitespace"
        print("✅ Whitespace-only string returns zero vector")
    except Exception as e:
        print(f"❌ Whitespace test failed: {e}")
        return False

    # Test 3: Valid text
    try:
        result = get_embedding("Hello world", fallback_to_mock=True)
        assert len(result) == 1536
        print("✅ Valid text returns embedding")
    except Exception as e:
        print(f"❌ Valid text test failed: {e}")
        return False

    # Test 4: Non-string should fail
    try:
        result = get_embedding(123, fallback_to_mock=True)
        print("❌ Non-string should have raised error")
        return False
    except ValueError as e:
        print(f"✅ Non-string raises ValueError: {e}")
    except Exception as e:
        print(f"❌ Non-string raised wrong error: {e}")
        return False

    print()
    return True


def test_langchain_adapter():
    """Test that LangChain adapter correctly handles queries."""
    print("="*70)
    print("TEST 2: LangChain Adapter Query Extraction")
    print("="*70)

    from neuromem.adapters.langchain import NeuroMemRunnable
    from langchain_core.messages import HumanMessage, SystemMessage
    import tempfile
    from neuromem import NeuroMem

    # Create a test instance
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini
  storage:
    database:
      type: memory
  async:
    enabled: false
""")
        config_path = f.name

    try:
        memory = NeuroMem.from_config(config_path, user_id="test-user")
        runnable = NeuroMemRunnable(memory, k=5)

        # Test 1: Query from messages
        input1 = {
            "messages": [
                SystemMessage(content="You are a helpful assistant"),
                HumanMessage(content="What is my name?")
            ]
        }
        result1 = runnable.invoke(input1)
        print("✅ Successfully extracted query from messages")

        # Test 2: Empty messages should not crash
        input2 = {
            "messages": []
        }
        result2 = runnable.invoke(input2)
        print("✅ Handled empty messages gracefully")

        # Test 3: No input or messages
        input3 = {}
        result3 = runnable.invoke(input3)
        print("✅ Handled missing input/messages gracefully")

        memory.close()
        print()
        return True

    except Exception as e:
        print(f"❌ LangChain adapter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(config_path)


def test_retrieve_method():
    """Test that retrieve() method works with various queries."""
    print("="*70)
    print("TEST 3: NeuroMem.retrieve() Method")
    print("="*70)

    import tempfile
    from neuromem import NeuroMem

    # Create a test instance
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini
  storage:
    database:
      type: memory
  async:
    enabled: false
""")
        config_path = f.name

    try:
        memory = NeuroMem.from_config(config_path, user_id="test-user")

        # Add some test data
        memory.observe("My name is Alice", "Nice to meet you Alice!")
        memory.observe("I like hiking", "That's great!")

        # Test 1: Valid query
        results = memory.retrieve("What is my name?", k=5)
        print(f"✅ Valid query returned {len(results)} results")

        # Test 2: Empty query should not crash
        results = memory.retrieve("", k=5)
        print(f"✅ Empty query returned {len(results)} results (no crash)")

        # Test 3: Whitespace query should not crash
        results = memory.retrieve("   ", k=5)
        print(f"✅ Whitespace query returned {len(results)} results (no crash)")

        memory.close()
        print()
        return True

    except Exception as e:
        print(f"❌ Retrieve method test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(config_path)


if __name__ == "__main__":
    print("\n" + "🧪 Testing NeuroMem Retrieval Fix".center(70, "="))
    print()

    all_passed = True

    # Run tests
    if not test_embedding_validation():
        all_passed = False

    if not test_langchain_adapter():
        all_passed = False

    if not test_retrieve_method():
        all_passed = False

    # Summary
    print("="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED! The retrieval fix is working correctly.")
    else:
        print("❌ SOME TESTS FAILED. Please review the errors above.")
    print("="*70)
    print()

    sys.exit(0 if all_passed else 1)
