"""
Example: Brain-Inspired Memory Optimization

Demonstrates how to use the new consolidation, optimization, and retrieval features.
"""

import sys
import os
from datetime import datetime, timedelta
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from neuromem.memory.consolidation import ConsolidationEngine
from neuromem.utils.embedding_optimizer import EmbeddingOptimizer
from neuromem.utils.auto_tagger import AutoTagger
from neuromem.memory.hybrid_retrieval import HybridRetrieval
from neuromem.core.types import MemoryItem, MemoryType


def example_consolidation():
    """Example: Extract facts and create summaries from conversations."""
    print("=" * 60)
    print("EXAMPLE 1: Memory Consolidation")
    print("=" * 60)
    
    # Create sample episodic memories (conversations)
    memories = [
        MemoryItem(
            id=str(uuid.uuid4()),
            user_id="user123",
            content="User: I prefer technical depth in explanations\nAssistant: Got it! I'll provide detailed technical explanations.",
            embedding=[0.1] * 1536,  # Placeholder
            memory_type=MemoryType.EPISODIC,
            salience=0.8,
            confidence=0.9,
            created_at=datetime.now() - timedelta(days=5),
            last_accessed=datetime.now() - timedelta(days=1),
            decay_rate=0.05,
            reinforcement=2,
            inferred=False,
            editable=True,
            tags=[]
        ),
        MemoryItem(
            id=str(uuid.uuid4()),
            user_id="user123",
            content="User: I like concise, bullet-point answers\nAssistant: Understood! I'll use bullet points.",
            embedding=[0.1] * 1536,
            memory_type=MemoryType.EPISODIC,
            salience=0.7,
            confidence=0.9,
            created_at=datetime.now() - timedelta(days=4),
            last_accessed=datetime.now() - timedelta(days=1),
            decay_rate=0.05,
            reinforcement=1,
            inferred=False,
            editable=True,
            tags=[]
        )
    ]
    
    # Initialize consolidation engine
    consolidator = ConsolidationEngine(
        llm_model="gpt-4o-mini",
        min_confidence=0.7
    )
    
    # Run consolidation
    print("\n📊 Running consolidation on", len(memories), "episodic memories...")
    results = consolidator.consolidate_batch(
        memories,
        extract_facts=True,
        create_summaries=True,
        apply_forgetting=True
    )
    
    # Display results
    print("\n✅ Consolidation Results:")
    print(f"  - Facts extracted: {results['stats']['facts_count']}")
    print(f"  - Summaries created: {results['stats']['summaries_count']}")
    print(f"  - Memories to delete: {results['stats']['deleted_count']}")
    
    if results['facts_extracted']:
        print("\n📝 Extracted Facts:")
        for fact in results['facts_extracted']:
            print(f"  - [{fact['fact_type']}] {fact['fact']} (confidence: {fact['confidence']})")
    
    if results['summaries_created']:
        print("\n📋 Conversation Summary:")
        summary = results['summaries_created'][0]
        print(f"  Summary: {summary['summary']}")
        print(f"  Topics: {', '.join(summary['topic_tags'])}")
        print(f"  Key Points:")
        for point in summary['key_points']:
            print(f"    • {point}")


def example_embedding_optimization():
    """Example: Optimize embeddings to reduce storage."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Embedding Optimization")
    print("=" * 60)
    
    # Create sample embeddings
    embeddings = [
        (f"emb_{i}", [float(i * 0.01 + j * 0.001) for j in range(1536)])
        for i in range(10)
    ]
    
    # Initialize optimizer
    optimizer = EmbeddingOptimizer(target_dims=512)
    
    print(f"\n📊 Optimizing {len(embeddings)} embeddings...")
    print(f"  Original dimensions: 1536")
    print(f"  Target dimensions: 512")
    
    # Run optimization
    results = optimizer.optimize_batch(
        embeddings,
        reduce_dims=True,
        quantize=True,
        deduplicate=True
    )
    
    # Display savings
    stats = results['stats']
    print("\n💾 Storage Savings:")
    print(f"  - Original size per embedding: {stats['original_bytes']} bytes")
    print(f"  - Optimized size per embedding: {stats['optimized_bytes']} bytes")
    print(f"  - Dimensionality reduction: {stats['dim_reduction_pct']:.1f}%")
    print(f"  - Total reduction: {stats['total_reduction_pct']:.1f}%")
    print(f"  - Savings ratio: {stats['savings_ratio']:.1f}x")
    
    if results['duplicate_groups']:
        print(f"\n🔍 Found {len(results['duplicate_groups'])} groups of similar embeddings")


def example_auto_tagging():
    """Example: Automatically generate tags for memories."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Auto-Tagging")
    print("=" * 60)
    
    # Sample memory content
    content = """User: Can you explain how vector databases work?
Assistant: Vector databases store data as high-dimensional vectors and enable fast similarity search using techniques like approximate nearest neighbor search."""
    
    # Initialize auto-tagger
    tagger = AutoTagger(llm_model="gpt-4o-mini")
    
    print("\n📝 Analyzing content:")
    print(f"  {content[:100]}...")
    
    # Generate tags
    print("\n🏷️  Generating tags...")
    enrichment = tagger.enrich_memory(content)
    
    print("\n✅ Generated Tags:")
    for tag in enrichment['tags']:
        print(f"  - {tag}")
    
    print(f"\n🎯 Intent: {enrichment['intent']}")
    
    sentiment = enrichment['sentiment']
    print(f"\n😊 Sentiment: {sentiment['sentiment']} (score: {sentiment['score']:.2f})")
    
    if enrichment['entities']:
        print("\n🔍 Extracted Entities:")
        for entity in enrichment['entities']:
            print(f"  - {entity['type']}: {entity['value']}")


def example_hybrid_retrieval():
    """Example: Hybrid retrieval with multi-stage ranking."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Hybrid Retrieval")
    print("=" * 60)
    
    # Create sample memories with different characteristics
    now = datetime.now()
    memories = [
        {
            'id': '1',
            'content': 'Recent important memory',
            'created_at': now - timedelta(days=1),
            'last_accessed': now,
            'salience': 0.9,
            'reinforcement': 5,
            'confidence': 0.95,
            'tags': ['topic:important', 'preference:technical']
        },
        {
            'id': '2',
            'content': 'Old but reinforced memory',
            'created_at': now - timedelta(days=60),
            'last_accessed': now - timedelta(days=30),
            'salience': 0.7,
            'reinforcement': 10,
            'confidence': 0.9,
            'tags': ['topic:learning']
        },
        {
            'id': '3',
            'content': 'Recent low importance',
            'created_at': now - timedelta(days=2),
            'last_accessed': now - timedelta(days=2),
            'salience': 0.3,
            'reinforcement': 1,
            'confidence': 0.6,
            'tags': ['topic:casual']
        }
    ]
    
    # Simulated similarity scores
    similarities = [0.85, 0.75, 0.90]
    
    # Initialize hybrid retrieval
    retriever = HybridRetrieval(
        recency_weight=0.2,
        importance_weight=0.3,
        similarity_weight=0.5
    )
    
    print("\n📊 Ranking memories with hybrid scoring...")
    
    # Rank results
    ranked = retriever.rank_results(memories, similarities)
    
    print("\n🏆 Ranked Results:")
    for i, (memory, score) in enumerate(ranked, 1):
        print(f"\n  {i}. Memory ID: {memory['id']} (Score: {score:.3f})")
        print(f"     Content: {memory['content']}")
        
        # Get explanation
        explanation = retriever.explain_ranking(memory, similarities[int(memory['id'])-1])
        components = explanation['components']
        print(f"     Breakdown:")
        print(f"       - Similarity: {components['similarity']['contribution']:.3f}")
        print(f"       - Recency: {components['recency']['contribution']:.3f}")
        print(f"       - Importance: {components['importance']['contribution']:.3f}")


def main():
    """Run all examples."""
    print("\n🧠 Brain-Inspired Memory Optimization Examples\n")
    
    try:
        example_consolidation()
        example_embedding_optimization()
        example_auto_tagging()
        example_hybrid_retrieval()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
