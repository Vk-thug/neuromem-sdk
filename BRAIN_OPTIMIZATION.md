# Brain-Inspired Memory Optimization

This document describes the brain-inspired memory optimization features added to NeuroMem SDK.

## Overview

The brain-inspired optimization system reduces memory storage by **80-90%** while **improving retrieval quality** through:

1. **Memory Consolidation** - Extract semantic facts from conversations
2. **Embedding Optimization** - Reduce storage through dimensionality reduction and quantization
3. **Auto-Tagging** - Automatically generate hierarchical tags
4. **Hybrid Retrieval** - Multi-stage retrieval with recency and importance boosting

## Features

### 1. Memory Consolidation

Mimics how the human brain consolidates memories during sleep:

- **Fact Extraction**: Extracts semantic facts from episodic memories
- **Summarization**: Creates concise summaries instead of storing full conversations
- **Deduplication**: Merges similar or duplicate facts
- **Temporal Decay**: Applies forgetting curves to low-importance memories

**Example:**
```python
from neuromem.memory.consolidation import ConsolidationEngine

consolidator = ConsolidationEngine(
    llm_model="gpt-4o-mini",
    min_confidence=0.7
)

results = consolidator.consolidate_batch(
    episodic_memories,
    extract_facts=True,
    create_summaries=True,
    apply_forgetting=True
)

print(f"Extracted {len(results['facts_extracted'])} facts")
print(f"Created {len(results['summaries_created'])} summaries")
```

### 2. Embedding Optimization

Reduces embedding storage through multiple techniques:

- **Dimensionality Reduction**: PCA reduction from 1536 → 512 dims (67% reduction)
- **Quantization**: float32 → int8 conversion (75% reduction)
- **Deduplication**: Identifies and merges similar embeddings
- **Combined**: ~90% total storage reduction

**Example:**
```python
from neuromem.utils.embedding_optimizer import EmbeddingOptimizer

optimizer = EmbeddingOptimizer(target_dims=512)

results = optimizer.optimize_batch(
    embeddings,
    reduce_dims=True,
    quantize=True,
    deduplicate=True
)

print(f"Storage reduction: {results['stats']['total_reduction_pct']:.1f}%")
```

### 3. Auto-Tagging

Automatically generates hierarchical tags for memories:

- **Topic Tags**: `topic:machine_learning`, `topic:cooking`
- **Preference Tags**: `preference:technical_depth`, `preference:concise_answers`
- **Entity Tags**: `entity:person:john`, `entity:place:paris`
- **Intent Tags**: `intent:learning`, `intent:question`
- **Sentiment Tags**: `sentiment:positive`, `sentiment:neutral`

**Example:**
```python
from neuromem.utils.auto_tagger import AutoTagger

tagger = AutoTagger(llm_model="gpt-4o-mini")

enrichment = tagger.enrich_memory(content)

print(f"Tags: {enrichment['tags']}")
print(f"Intent: {enrichment['intent']}")
print(f"Sentiment: {enrichment['sentiment']['sentiment']}")
```

### 4. Hybrid Retrieval

Multi-stage retrieval system that combines:

1. **Keyword/Tag Filtering** - Fast initial filtering
2. **Semantic Search** - Vector similarity ranking
3. **Temporal Boosting** - Recency weighting
4. **Importance Weighting** - Salience-based ranking
5. **Final Re-ranking** - Weighted combination

**Example:**
```python
from neuromem.memory.hybrid_retrieval import HybridRetrieval

retriever = HybridRetrieval(
    recency_weight=0.2,
    importance_weight=0.3,
    similarity_weight=0.5
)

results = retriever.retrieve(
    query_embedding,
    all_memories,
    similarities,
    k=10,
    filters={'required_tags': ['topic:important']}
)
```

## Configuration

Add these settings to your `neuromem.yaml`:

```yaml
neuromem:
  model:
    embedding: text-embedding-3-small
    consolidation_llm: gpt-4o-mini
  
  storage:
    vector_store:
      type: postgres
      config:
        url: "postgresql://..."
  
  # Brain-inspired optimization settings
  consolidation:
    enabled: true
    extract_facts: true
    create_summaries: true
    apply_forgetting: true
    min_confidence: 0.7
    decay_threshold: 0.3
  
  embeddings:
    optimization_enabled: true
    dimension_reduction:
      enabled: true
      target_dims: 512
      age_threshold_days: 30
    quantization:
      enabled: true
      dtype: int8
    deduplication:
      enabled: true
      similarity_threshold: 0.95
  
  tagging:
    auto_tag_enabled: true
    max_tags_per_memory: 10
    extract_entities: true
    classify_intent: true
    analyze_sentiment: true
  
  retrieval:
    hybrid_enabled: true
    recency_weight: 0.2
    importance_weight: 0.3
    similarity_weight: 0.5
    recency_half_life_days: 30
```

## Storage Savings

### Before Optimization

- **Full conversation text**: ~500 chars per message
- **Full embeddings**: 1536 dims × 4 bytes = 6,144 bytes
- **10,000 memories**: ~61 MB embeddings + ~5 MB text = **~66 MB total**

### After Optimization

- **Extracted facts**: ~50 chars per fact (10x reduction)
- **Summaries**: ~200 chars per conversation (2.5x reduction)
- **Optimized embeddings**: 512 dims × 1 byte = 512 bytes (12x reduction)
- **10,000 memories**: ~5 MB embeddings + ~0.5 MB facts = **~5.5 MB total**

**Total Reduction: ~92%** 🎉

## How It Works

### Memory Consolidation Process

```
Episodic Memories (Conversations)
         ↓
    [Consolidation Engine]
         ↓
    ┌────────────────┐
    │  Fact Extract  │ → Semantic Facts (distilled knowledge)
    ├────────────────┤
    │  Summarization │ → Conversation Summaries (key points)
    ├────────────────┤
    │  Deduplication │ → Merged similar facts
    ├────────────────┤
    │ Temporal Decay │ → Pruned low-importance memories
    └────────────────┘
```

### Embedding Optimization Pipeline

```
Original Embeddings (1536 dims, float32)
         ↓
    [PCA Reduction]
         ↓
    Reduced Embeddings (512 dims, float32)
         ↓
    [Quantization]
         ↓
    Optimized Embeddings (512 dims, int8)
         ↓
    90% Storage Reduction
```

### Hybrid Retrieval Flow

```
Query
  ↓
[Stage 1: Tag/Keyword Filtering]
  ↓
[Stage 2: Semantic Search]
  ↓
[Stage 3: Hybrid Scoring]
  ├─ Similarity Score (50%)
  ├─ Recency Score (20%)
  └─ Importance Score (30%)
  ↓
[Stage 4: Top-K Selection]
  ↓
Results
```

## Running Examples

See the complete example in `examples/brain_optimization_example.py`:

```bash
cd examples
python brain_optimization_example.py
```

This demonstrates:
- Memory consolidation with fact extraction
- Embedding optimization with storage calculations
- Auto-tagging with entity extraction
- Hybrid retrieval with ranking explanations

## Benefits

### Storage Efficiency
- **90% reduction** in embedding storage
- **80% reduction** in text storage through summarization
- Deduplication eliminates redundant data

### Retrieval Quality
- **Faster search** through reduced dimensions
- **Better ranking** with hybrid scoring
- **Context-aware** with tags and metadata

### Scalability
- Handle **10-15 years** of conversation data
- Efficient storage for millions of memories
- Fast retrieval even with large datasets

## Best Practices

1. **Run consolidation regularly** (e.g., nightly) to extract facts and create summaries
2. **Enable auto-tagging** for all new memories to improve searchability
3. **Use hybrid retrieval** for better ranking than pure semantic search
4. **Monitor storage savings** to ensure optimization is working
5. **Adjust weights** in hybrid retrieval based on your use case

## Technical Details

### Fact Extraction
Uses LLM (GPT-4o-mini) to extract structured facts from conversations with confidence scores.

### Dimensionality Reduction
Uses PCA (Principal Component Analysis) to reduce embedding dimensions while preserving semantic information.

### Quantization
Converts float32 embeddings to int8 using min-max scaling with stored scale/offset for reconstruction.

### Temporal Decay
Applies exponential decay formula: `importance = salience × e^(-decay_rate × age)`

### Hybrid Scoring
Combines multiple signals: `score = w₁×similarity + w₂×recency + w₃×importance`

## Future Enhancements

- [ ] UMAP for better dimensionality reduction
- [ ] Product quantization for even more compression
- [ ] Clustering-based deduplication
- [ ] Automated consolidation scheduling
- [ ] Memory tier management (HOT/WARM/COLD)
- [ ] Advanced entity linking
- [ ] Multi-modal memory support

## License

Same as NeuroMem SDK main license.
