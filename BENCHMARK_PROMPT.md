# NeuroMem SDK — Full Feature Benchmark Prompt

## Objective

Run the comprehensive LoCoMo benchmark suite against all NeuroMem v0.2.0 features to establish a new baseline score after the complete feature set is in place: multi-hop retrieval, entity index, graph-augmented retrieval, keyword fallback, junk filter, salience tuning, conflict detection, reconsolidation, Inngest workflows, and all 8 framework adapters.

## Current Baseline (Last Run: 2026-03-27)

| System | F1 | EM | Hit Rate | Cat1 (single-hop) | Cat4 (multi-hop) |
|--------|----|----|----------|--------------------|-------------------|
| **NeuroMem v0.2.0** | **39.4** | **15.0** | **36.7** | **40.9** | **36.0** |
| Mem0 | 30.6 | 10.0 | 21.7 | 29.4 | 33.3 |
| LangMem | 32.7 | 11.7 | 33.3 | 31.1 | 36.1 |

NeuroMem leads by +6.7 F1 over LangMem, +8.8 over Mem0.

## What to Benchmark

### Phase 1: Core Retrieval Accuracy (LoCoMo)

Run the standard LoCoMo benchmark with all 5 categories to get complete coverage:

```bash
cd /Users/vikramvenkateshkumar/workspaces/Client/megadot/services/neuromem-sdk

# Activate venv (CRITICAL — system Python lacks benchmark deps)
source .venv/bin/activate

# Full benchmark: all 5 categories, 5 conversations, all 3 systems
python -m benchmarks --systems neuromem mem0 langmem \
  --conversations 5 \
  --categories 1 2 3 4 5 \
  --embedding-provider openai \
  --embedding-model text-embedding-3-small \
  --answer-provider openai \
  --answer-model gpt-4o-mini \
  --no-judge \
  --verbose
```

**Categories:**
- Cat 1: Single-hop factual questions (e.g., "Where does X live?")
- Cat 2: Multi-hop questions (e.g., "How do X and Y both feel about...?")
- Cat 3: Open-ended questions (summaries, opinions)
- Cat 4: Temporal questions (e.g., "What changed between session 1 and 3?")
- Cat 5: Unanswerable questions (should return "Unknown")

**Expected improvements to validate:**
- Multi-hop F1 should improve via query decomposition + entity index + graph retrieval
- Single-hop F1 should remain stable (graph retrieval scoped to multi-hop only)
- Cat 5 (unanswerable) should improve via junk filter reducing noise

### Phase 2: Latency Benchmark

```bash
python -m benchmarks --latency --systems neuromem mem0 langmem \
  --embedding-provider openai \
  --embedding-model text-embedding-3-small
```

**Metrics to capture:**
- Store latency (p50, p95, p99)
- Search latency (p50, p95, p99)
- End-to-end latency per question

**Known performance characteristics:**
- NeuroMem store: ~710ms (embedding + storage)
- NeuroMem search: ~1305ms (decomposition cost for multi-hop; single-hop ~400ms)
- Thread-safe LRU cache should reduce repeated embedding calls
- Vectorized cosine similarity (NumPy) should improve search for in-memory backend

### Phase 3: Feature-Specific Validation

After the LoCoMo benchmark, run targeted tests to validate specific features:

#### 3.1 Keyword Fallback (proper noun retrieval)

```python
# Test that proper nouns are found even when embedding similarity is weak
import uuid
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))

# Store facts about specific people
mem.observe("My colleague Arjun is the tech lead on MegaAuth", "Noted!")
mem.observe("Priya handles frontend with React and Next.js", "Got it!")
mem.observe("Our CI/CD pipeline uses GitHub Actions", "Good setup!")

# Retrieve by name — embedding alone might miss these
for q in ["Who is Arjun?", "What does Priya do?", "What CI/CD tool do we use?"]:
    results = mem.retrieve(q, k=5)
    found = any(kw in r.content.lower() for r in results for kw in q.lower().split() if len(kw) > 3)
    print(f"{'PASS' if found else 'FAIL'}: {q}")

mem.close()
```

**Expected:** 3/3 PASS (keyword fallback finds proper nouns)

#### 3.2 Multi-Hop Query Decomposition

```python
# Test that composite questions are decomposed into sub-queries
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))

mem.observe("Alice works as a data scientist at Google", "Interesting!")
mem.observe("Bob is a backend engineer at Meta", "Cool!")
mem.observe("Alice loves hiking and photography", "Nice hobbies!")
mem.observe("Bob enjoys chess and cooking", "Sounds fun!")

# Multi-hop: should decompose and find both Alice and Bob info
results = mem.retrieve("What hobbies do Alice and Bob each enjoy?", k=8)
alice_found = any("alice" in r.content.lower() and "hik" in r.content.lower() for r in results)
bob_found = any("bob" in r.content.lower() and "chess" in r.content.lower() for r in results)
print(f"Alice hobbies: {'PASS' if alice_found else 'FAIL'}")
print(f"Bob hobbies: {'PASS' if bob_found else 'FAIL'}")

mem.close()
```

**Expected:** Both PASS (query decomposition retrieves per-entity)

#### 3.3 Conflict Detection

```python
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))

mem.observe("I prefer PostgreSQL for databases", "Good choice!")
mem.observe("I don't like PostgreSQL anymore, switched to MySQL", "Noted!")

results = mem.retrieve("What database do I prefer?", k=5)
# Should only return the newer preference, not the contradicted one
print(f"Results: {len(results)}")
for r in results:
    print(f"  {r.content[:60]}...")

mem.close()
```

**Expected:** Newer preference (MySQL) ranked higher, deprecated memory filtered

#### 3.4 Junk Filter (adapter level)

```python
from neuromem import NeuroMem
from neuromem.adapters.langgraph import with_memory
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from typing import Annotated, List
from typing_extensions import TypedDict

class State(TypedDict):
    messages: Annotated[list, add_messages]
    context: List[str]

def agent(state):
    # Simulate junk response
    return {"messages": [AIMessage(content="I don't have access to personal information")]}

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))
builder = StateGraph(State)
builder.add_node("a", agent)
builder.add_edge(START, "a")
builder.add_edge("a", END)
app = with_memory(builder.compile(), mem)

# This should NOT be stored (junk response)
app.invoke({"messages": [HumanMessage(content="What is my name?")], "context": []})

count = len(mem.list(limit=100))
print(f"Memories after junk response: {count} (expected: 0)")

mem.close()
```

**Expected:** 0 memories stored (junk filter blocks "I don't have access" responses)

#### 3.5 Entity Index + Graph Retrieval

```python
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))

# Store related facts about the same entity
mem.observe("Caroline moved to San Francisco last year", "Big move!")
mem.observe("Caroline started a new job at Stripe", "Congrats!")
mem.observe("Caroline's favorite restaurant is Tartine Bakery", "Great taste!")

# Entity index should link all "Caroline" memories
graph = mem.get_graph()
print(f"Graph: {graph['node_count']} nodes, {graph['edge_count']} edges")

# Retrieve should find all Caroline facts
results = mem.retrieve("Tell me about Caroline", k=5)
caroline_count = sum(1 for r in results if "caroline" in r.content.lower())
print(f"Caroline memories retrieved: {caroline_count}/3")

mem.close()
```

**Expected:** 3/3 Caroline memories retrieved via entity index

#### 3.6 Salience Scoring

```python
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))

# First-person fact (should be HIGH salience)
mem.observe("I am a senior engineer at Google working on search infrastructure", "Interesting!")

# Question (should be LOWER salience)
mem.observe("What's the weather today?", "It's sunny and 72F")

mems = mem.list(limit=10)
for m in mems:
    source = "FACT" if "I am" in m.content else "QUESTION"
    print(f"[{source}] salience={m.salience:.2f}: {m.content[:60]}...")

# The fact should have higher salience than the question
fact_sal = next((m.salience for m in mems if "I am" in m.content), 0)
q_sal = next((m.salience for m in mems if "weather" in m.content), 0)
print(f"\nFact salience: {fact_sal:.2f}, Question salience: {q_sal:.2f}")
print(f"Fact > Question: {'PASS' if fact_sal > q_sal else 'FAIL'}")

mem.close()
```

**Expected:** PASS — first-person facts get +0.35 boost, questions only +0.05

#### 3.7 Search Query Language

```python
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml", user_id=str(uuid.uuid4()))

mem.observe("I prefer Python for backend work", "Great!")
mem.observe("I use React for frontend", "Nice!")
mem.observe("My database is PostgreSQL", "Solid choice!")

# Structured search
results = mem.search("type:episodic Python")
print(f'search("type:episodic Python"): {len(results)} results')

results = mem.search('"PostgreSQL"')
print(f'search("PostgreSQL" exact): {len(results)} results')

mem.close()
```

### Phase 4: Ollama + Qdrant Integration Test

Run the full multi-week conversation validation with real local infrastructure:

```bash
# Ensure services are running
curl http://localhost:6333/collections  # Qdrant
ollama list                              # Ollama models

# Reset Qdrant collection
python3 -c "
import requests
requests.delete('http://localhost:6333/collections/neuromem')
requests.put('http://localhost:6333/collections/neuromem', json={'vectors': {'size': 768, 'distance': 'Cosine'}})
"

# Run multi-week validation
python examples/ai_assistant_ollama.py
```

**Expected:**
- 50+ memories stored in Qdrant
- 22+/25 recall questions answered correctly (88%+)
- Streaming response works in Week 6

### Phase 5: MCP Server Validation

```bash
# Test MCP server starts and tools work
pip install mcp pydantic
python -m pytest tests/test_mcp.py -v

# Manual test
python -m neuromem.mcp --help
```

**Expected:** 26 MCP tests passing, 12 tools registered

### Phase 6: Framework Adapter Compatibility

```bash
# Run all adapter tests
python -m pytest tests/test_crewai_adapter.py tests/test_autogen_adapter.py \
  tests/test_dspy_adapter.py tests/test_haystack_adapter.py \
  tests/test_semantic_kernel_adapter.py -v

# Run core tests
python -m pytest tests/test_core.py tests/test_graph.py tests/test_query.py \
  tests/test_workflows.py -v
```

**Expected:** 108+ tests passing, 0 failures

## Success Criteria

| Metric | Target | Current |
|--------|--------|---------|
| LoCoMo F1 (overall) | > 39.4 | 39.4 |
| LoCoMo F1 (multi-hop, Cat 2+4) | > 36.0 | 36.0 |
| LoCoMo F1 (single-hop, Cat 1) | > 40.0 | 40.9 |
| Keyword fallback | 3/3 | 3/3 |
| Multi-hop decomposition | 2/2 | 2/2 |
| Conflict detection | Works | Works |
| Junk filter | 0 junk stored | 0 |
| Entity index retrieval | 3/3 | 3/3 |
| Salience ordering | Fact > Question | Works |
| Search query language | Works | Works |
| Ollama recall score | > 88% | 88% |
| MCP tests | 26 pass | 26 pass |
| Total test suite | > 108 pass | 108 pass |
| Store latency p95 | < 2000ms | 1571ms |

## Environment Setup

```bash
# Venv (CRITICAL — use this, not system Python)
source .venv/bin/activate

# Verify deps
python -c "import langchain_core; print(f'langchain-core: {langchain_core.__version__}')"
python -c "from importlib.metadata import version; print(f'langgraph: {version(\"langgraph\")}')"
python -c "import openai; print(f'openai: {openai.__version__}')"

# API key
echo $OPENAI_API_KEY | head -c 10

# Local services
curl -s http://localhost:6333/collections | python -m json.tool
ollama list
```

## Known Issues to Watch For

1. **datetime.utcnow() deprecation**: ~25 call sites use deprecated API. Produces DeprecationWarning but doesn't affect correctness. Holistic migration deferred.
2. **Search latency for multi-hop**: ~1300ms due to LLM decomposition call. Single-hop is ~400ms.
3. **Mem0 UPDATE errors**: Mem0 adapter throws non-fatal ID errors during benchmark. Ignore.
4. **dotenv loading**: `OPENAI_API_KEY` must be in `.env` at repo root. The benchmark runner loads it via `load_dotenv()`.
5. **HybridRetrieval re-instantiation**: Created fresh every `retrieve()` call. Could be cached for latency improvement.

## How to Read Results

Results are saved to `benchmarks/results/locomo_YYYYMMDD_HHMMSS.json`. Key fields:

```json
{
  "summary": [{
    "system": "NeuroMem (v0.2.0, memory)",
    "avg_f1": 39.4,           // Main metric
    "exact_match": 15.0,      // Strict match
    "avg_containment": 40.9,  // Answer substring present
    "retrieval_hit_rate": 36.7, // Retrieved context has answer
    "category_f1": {
      "1": 40.9,  // Single-hop
      "2": ...,   // Multi-hop
      "3": ...,   // Open-ended
      "4": 36.0,  // Temporal
      "5": ...    // Unanswerable
    }
  }]
}
```

**F1 is the primary metric** — harmonic mean of precision and recall on answer tokens. Uses stemming to match "dance" = "dancing".
