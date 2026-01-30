"""
Test script to verify NeuroMem SDK installation and setup.

Run this to ensure everything is working correctly.
"""

import sys


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import neuromem
        print("  ✅ neuromem")
    except ImportError as e:
        print(f"  ❌ neuromem: {e}")
        return False
    
    try:
        import numpy
        print("  ✅ numpy")
    except ImportError:
        print("  ⚠️  numpy not installed (required)")
        return False
    
    try:
        import yaml
        print("  ✅ yaml")
    except ImportError:
        print("  ⚠️  pyyaml not installed (required)")
        return False
    
    # Optional dependencies
    try:
        import openai
        print("  ✅ openai (optional)")
    except ImportError:
        print("  ⚠️  openai not installed (optional, for embeddings)")
    
    try:
        import langgraph
        print("  ✅ langgraph (optional)")
    except ImportError:
        print("  ⚠️  langgraph not installed (optional, for LangGraph integration)")
    
    try:
        import langchain
        print("  ✅ langchain (optional)")
    except ImportError:
        print("  ⚠️  langchain not installed (optional, for LangChain integration)")
    
    try:
        import psycopg2
        print("  ✅ psycopg2 (optional)")
    except ImportError:
        print("  ⚠️  psycopg2 not installed (optional, for PostgreSQL backend)")
    
    return True


def test_basic_functionality():
    """Test basic NeuroMem functionality."""
    print("\nTesting basic functionality...")
    
    try:
        from neuromem import NeuroMem, UserManager
        from neuromem.config import create_default_config
        import tempfile
        import os
        
        # Create temp config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        try:
            create_default_config(config_path)
            print("  ✅ Config creation")
            
            # Create user
            user = UserManager.create(external_id="test_user")
            print(f"  ✅ User creation (ID: {user.id[:8]}...)")
            
            # Initialize memory
            memory = NeuroMem.from_config(config_path, user_id=user.id)
            print("  ✅ Memory initialization")
            
            # Test observe
            memory.observe("Test input", "Test output")
            print("  ✅ Memory observation")
            
            # Test retrieve
            results = memory.retrieve("Test query", k=5)
            print(f"  ✅ Memory retrieval ({len(results)} results)")
            
            # Test list
            memories = memory.list(limit=10)
            print(f"  ✅ Memory listing ({len(memories)} memories)")
            
            return True
            
        finally:
            # Cleanup
            if os.path.exists(config_path):
                os.unlink(config_path)
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_storage_backends():
    """Test available storage backends."""
    print("\nTesting storage backends...")
    
    try:
        from neuromem.storage import InMemoryBackend
        backend = InMemoryBackend()
        print("  ✅ In-memory backend")
    except Exception as e:
        print(f"  ❌ In-memory backend: {e}")
    
    try:
        from neuromem.storage import SQLiteBackend
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
            backend = SQLiteBackend(f.name)
        print("  ✅ SQLite backend")
    except Exception as e:
        print(f"  ❌ SQLite backend: {e}")
    
    try:
        from neuromem.storage import PostgresBackend
        print("  ⚠️  PostgreSQL backend available (requires database)")
    except Exception as e:
        print(f"  ⚠️  PostgreSQL backend: {e}")


def test_memory_layers():
    """Test memory layer implementations."""
    print("\nTesting memory layers...")
    
    try:
        from neuromem.memory import SessionMemory, EpisodicMemory, SemanticMemory, ProceduralMemory
        from neuromem.storage import InMemoryBackend
        
        backend = InMemoryBackend()
        
        session = SessionMemory()
        print("  ✅ Session memory")
        
        episodic = EpisodicMemory(backend, "test_user")
        print("  ✅ Episodic memory")
        
        semantic = SemanticMemory(backend, "test_user")
        print("  ✅ Semantic memory")
        
        procedural = ProceduralMemory(backend, "test_user")
        print("  ✅ Procedural memory")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_cognitive_engines():
    """Test cognitive engines."""
    print("\nTesting cognitive engines...")
    
    try:
        from neuromem.core import RetrievalEngine, Consolidator, DecayEngine
        
        retriever = RetrievalEngine()
        print("  ✅ Retrieval engine")
        
        consolidator = Consolidator()
        print("  ✅ Consolidation engine")
        
        decay = DecayEngine()
        print("  ✅ Decay engine")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("NeuroMem SDK Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Basic Functionality", test_basic_functionality()))
    results.append(("Storage Backends", test_storage_backends()))
    results.append(("Memory Layers", test_memory_layers()))
    results.append(("Cognitive Engines", test_cognitive_engines()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed! NeuroMem SDK is ready to use.")
        print("\nNext steps:")
        print("  1. Set OPENAI_API_KEY for embeddings (optional)")
        print("  2. Run: python examples/basic_usage.py")
        print("  3. Run: python examples/demo_agent.py")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
