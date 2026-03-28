# NeuroMem v0.2.0 — Open Issue Fix Prompt

## Overview

6 open issues from the full benchmark run (2026-03-28) need fixing before v0.2.0 is committed. All are diagnosed with root causes identified below.

**Ground rules**: Python 3.9+ compat, black format (line-length 100), no new dependencies, run `python3 -m pytest tests/ -q --ignore=tests/test_mcp.py` after each fix, all 107+ tests must pass.

---

## Issue 1: datetime naive/aware mismatch in consolidation.py

**Symptom**: `TypeError: can't subtract offset-naive and offset-aware datetimes` at `neuromem/memory/consolidation.py:269`

**Root cause**: The datetime migration (2026-03-28) replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` in most files, but `memory/consolidation.py` still has 3 calls to bare `datetime.now()` (naive). When these naive datetimes are subtracted from aware datetimes stored by the migrated `controller.py`, Python throws TypeError.

**Remaining naive calls** (33 total across codebase — `grep -rn "datetime\.now()" neuromem/ | grep -v timezone | grep -v __pycache__`):

Critical (cause crashes):
- `neuromem/memory/consolidation.py:118` — `datetime.now()`
- `neuromem/memory/consolidation.py:119` — `datetime.now()`
- `neuromem/memory/consolidation.py:265` — `datetime.now()`

Other files with naive `datetime.now()` (may cause future crashes):
- `neuromem/core/controller.py:297`
- `neuromem/core/observability/tracing.py:22,33,41,49`
- `neuromem/core/policies/optimization.py:54`
- `neuromem/core/policies/reconsolidation.py:85,99`
- `neuromem/core/policies/salience.py:28,64`
- `neuromem/core/workers/ingest_worker.py:150,151,160,161,193`
- `neuromem/core/workers/maintenance_worker.py:25,28,31,108,119,130,147,155,160`
- `neuromem/memory/summaries.py:39,114`
- `neuromem/workflows/functions.py:510`
- `neuromem/__init__.py:507,517,544`

**Fix**:
1. Replace ALL remaining `datetime.now()` with `datetime.now(timezone.utc)` across the entire codebase
2. Add `from datetime import timezone` import where missing
3. At subtraction/comparison boundaries where the other operand might be naive (from stored data), use `ensure_utc()` from `neuromem/utils/time.py`:
   ```python
   from neuromem.utils.time import ensure_utc
   age = datetime.now(timezone.utc) - ensure_utc(mem.created_at)
   ```
4. `ensure_utc()` already exists and treats naive datetimes as UTC: `dt.replace(tzinfo=timezone.utc)`

**Verification**: `python3 -m pytest tests/test_core.py::TestRetrieve::test_retrieve_respects_k_parameter -v` — this specific test triggers consolidation and currently fails.

---

## Issue 2: Keyword fallback fails for proper nouns with trailing punctuation

**Symptom**: "Who is Arjun?" → keyword extracted as `arjun?` (with question mark), fails to match `arjun` in memory content. 1/3 pass in benchmark.

**Root cause**: `_keyword_fallback()` in `controller.py` splits query by whitespace and checks `len(w) > 2`, but does NOT strip punctuation. So `"Arjun?"` becomes the keyword `"arjun?"` which doesn't match `"arjun"` in content.

Same issue in `boost_keyword_matches()` in `retrieval.py` — keywords include trailing `?`, `,`, `.`, `!`.

**Fix**:
1. In `controller.py:_keyword_fallback()`, strip punctuation from keywords:
   ```python
   import string
   keywords = [
       w.lower().strip(string.punctuation)
       for w in query_text.split()
       if w.lower().strip(string.punctuation) not in constants.RETRIEVAL_STOP_WORDS
       and len(w.strip(string.punctuation)) > 2
   ]
   ```
2. Apply same fix in `retrieval.py:boost_keyword_matches()`:
   ```python
   query_words = [
       w.strip(string.punctuation)
       for w in query_text.lower().split()
       if w.strip(string.punctuation) not in constants.RETRIEVAL_STOP_WORDS
       and len(w.strip(string.punctuation)) > 1
   ]
   ```

**Verification**:
```python
mem.observe("My colleague Arjun is the tech lead", "Noted!")
results = mem.retrieve("Who is Arjun?", k=5)
assert any("arjun" in r.content.lower() for r in results)
```

---

## Issue 3: Conflict detection fails because auto-tagger tags are inconsistent

**Symptom**: "I prefer PostgreSQL" and "I do not like PostgreSQL anymore" are not detected as conflicting. Both memories returned without resolution.

**Root cause**: Conflict detection requires shared `topic:` tags between two memories. But the auto-tagger (which uses OpenAI) assigns tags inconsistently:
- Memory 1: `['intent:preference', 'sentiment:positive']` — NO topic tags
- Memory 2: `['topic:data_science', 'topic:databases', 'intent:preference']` — HAS topic tags

Because the tag sets have NO shared `topic:` tags, `detect_conflict()` returns False.

The deeper issue: when OpenAI is unavailable, the fallback tagger in `_fallback_tags()` generates different tag sets for semantically similar content. And when OpenAI IS available, it's not deterministic.

**Fix**: The conflict detector should NOT depend on tags at all for content-level contradiction detection. Instead, use content-based detection:

```python
def detect_conflict(self, mem1: MemoryItem, mem2: MemoryItem) -> bool:
    """Detect if two memories contradict each other."""
    # Extract user statements only (before "Assistant:")
    user1 = mem1.content.split("\nAssistant:")[0].replace("User: ", "").lower()
    user2 = mem2.content.split("\nAssistant:")[0].replace("User: ", "").lower()

    # Strategy 1: Same subject + negation difference
    # Find shared significant words (nouns/verbs, not stop words)
    words1 = {w.strip(string.punctuation) for w in user1.split()
              if w.strip(string.punctuation) not in STOP_WORDS and len(w) > 2}
    words2 = {w.strip(string.punctuation) for w in user2.split()
              if w.strip(string.punctuation) not in STOP_WORDS and len(w) > 2}

    shared_words = words1 & words2
    if len(shared_words) < 2:
        return False  # Not about the same topic

    # Check for negation asymmetry in user content
    negation_words = {"not", "never", "don't", "doesn't", "isn't", "no", "hate", "dislike", "switched"}
    neg1 = any(f" {w} " in f" {user1} " for w in negation_words)
    neg2 = any(f" {w} " in f" {user2} " for w in negation_words)

    return neg1 != neg2  # One has negation, other doesn't
```

**Key change**: Uses shared significant words (content overlap) instead of tag overlap. Two memories about "PostgreSQL" + "databases" + "prefer" will share those words regardless of tags.

**Verification**:
```python
mem.observe("I prefer PostgreSQL", "Good!")
mem.observe("I don't like PostgreSQL anymore", "Noted!")
results = mem.retrieve("What database do I prefer?", k=5)
# Newer preference should win
assert "don't" in results[0].content.lower() or "mysql" in results[0].content.lower()
```

---

## Issue 4: Entity graph not populated via async IngestWorker path

**Symptom**: `get_graph()` returns 0 nodes/0 edges when `async.enabled: true`. Entity extraction only runs in `_observe_sync()` path.

**Root cause**: In `controller.py:_observe_sync()` (line 331-335), entity extraction and graph registration happen:
```python
entities = extract_entities(content)
if entities:
    self.graph.register_entities(memory_id, entities)
```

But in `core/workers/ingest_worker.py:_process_observe()`, there is NO entity extraction or graph registration. The async path skips this entirely.

**Fix**: Add entity extraction to `IngestWorker._process_observe()`:

```python
# In ingest_worker.py, after storing the memory (line 167):
self.controller.episodic.store(memory)

# Add entity extraction + graph registration
from neuromem.core.graph import extract_entities
entities = extract_entities(content)
if entities:
    self.controller.graph.register_entities(memory.id, entities)
```

**Verification**:
```python
# With async enabled
mem.observe("Caroline works at Stripe", "Cool!")
import time; time.sleep(6)  # Wait for async worker
entities = mem.controller.graph._entity_index
assert "caroline" in entities
```

---

## Issue 5: Search exact-match returns 0 in benchmark but works in isolation

**Symptom**: Benchmark Phase 3 reports `'"PostgreSQL"'` returns 0 results. But isolated testing shows it works (1 result found).

**Root cause**: This is a test script quoting issue, not a code bug. The benchmark test script was passing `'"PostgreSQL"'` (single quotes wrapping double quotes), but the actual `MemoryQuery` parser correctly handles `"PostgreSQL"` (just double quotes).

The real remaining issue is that exact match is **case-sensitive**. `"postgresql"` won't match content containing `"PostgreSQL"`.

**Fix**: Make exact phrase matching case-insensitive in `MemoryQuery.matches_memory()`:

In `neuromem/core/query.py`, the current code:
```python
for phrase in self.exact_phrases:
    if phrase.lower() not in memory.content.lower():
        return False
```

This is already case-insensitive! The benchmark test script was the problem, not the code. **Verify this is already correct and add a test case.**

**Verification**:
```python
from neuromem.core.query import MemoryQuery
q = MemoryQuery('"PostgreSQL"')
assert q.exact_phrases == ["PostgreSQL"]
# Should match case-insensitively
assert q.matches_memory(mock_memory_with_content("I use postgresql"))
```

---

## Issue 6: Cat2 temporal (8.4%) and Cat3 open-ended (8.9%) are weak

**Symptom**: LoCoMo Cat2 (temporal questions like "What changed between session 1 and 3?") and Cat3 (open-ended summaries) score much lower than Cat1/Cat4.

**Root cause**: Two separate issues:

**Cat2 (temporal)**: NeuroMem has no temporal awareness in retrieval. Questions like "When did X happen?" or "What changed over time?" require session/time metadata that isn't used during retrieval ranking. The `TemporalSummarizer` exists but isn't integrated into the retrieval pipeline.

**Cat3 (open-ended)**: These require synthesizing across many memories (e.g., "Describe X's personality"). The current retrieval returns top-k individual memories but doesn't aggregate or summarize them.

**Fix for Cat2** (medium effort):
1. During `observe()`, store session metadata (if provided) in `MemoryItem.metadata`:
   ```python
   metadata["session_id"] = session_id  # Already done in benchmark adapter
   ```
2. In retrieval, when query contains temporal markers ("when", "what changed", "over time", "between session"), boost memories that have `session_id` metadata matching the query's referenced sessions.
3. Add temporal keyword detection to `_is_multi_hop_query()`:
   ```python
   temporal_markers = ["when did", "what changed", "over time", "between session",
                       "first time", "last time", "before", "after"]
   if any(m in query_lower for m in temporal_markers):
       return True
   ```

**Fix for Cat3** (lower priority — this is an LLM answer generation issue, not retrieval):
- Cat3 questions need the answer prompt to allow longer, synthesized responses
- Current `ANSWER_PROMPT` says "be extremely brief" which hurts open-ended questions
- Consider a category-aware prompt in the benchmark runner (not an SDK change)

**Note**: Cat2/Cat3 improvements are stretch goals. The primary fix target is Cat2 temporal detection. Cat3 is an LLM prompt engineering issue in the benchmark evaluator, not an SDK bug.

**Verification**: Run LoCoMo with `--categories 2` only and compare against previous 8.4% baseline.

---

## Execution Order

```
Fix 1 (datetime): 30 min → fixes the test failure, unblocks everything
Fix 2 (punctuation): 15 min → fixes keyword fallback for proper nouns
Fix 3 (conflict): 30 min → fixes contradiction detection
Fix 4 (entity async): 15 min → fixes graph population in async mode
Fix 5 (exact match): 10 min → verify already works, add test
Fix 6 (temporal): 45 min → stretch goal for Cat2 improvement
```

After all fixes:
```bash
python3 -m pytest tests/ -q --ignore=tests/test_mcp.py
# Expected: 107+ passed, 0 failed, 5 skipped

# Then run the full benchmark to get new baseline:
source .venv/bin/activate
python -m benchmarks --systems neuromem mem0 langmem \
  --conversations 2 --categories 1 2 4 \
  --embedding-provider openai --embedding-model text-embedding-3-small \
  --answer-provider openai --answer-model gpt-4o-mini --no-judge --verbose
```

## Files to Modify

| File | Issue | Change |
|------|-------|--------|
| `neuromem/memory/consolidation.py` | #1 | `datetime.now()` → `datetime.now(timezone.utc)` (3 calls) |
| `neuromem/core/controller.py` | #1 | `datetime.now()` → `datetime.now(timezone.utc)` (1 call) |
| `neuromem/core/observability/tracing.py` | #1 | 4 calls |
| `neuromem/core/policies/optimization.py` | #1 | 1 call + `ensure_utc()` |
| `neuromem/core/policies/reconsolidation.py` | #1 | 2 calls |
| `neuromem/core/policies/salience.py` | #1 | 2 calls + `ensure_utc()` |
| `neuromem/core/workers/ingest_worker.py` | #1, #4 | 5 datetime calls + add entity extraction |
| `neuromem/core/workers/maintenance_worker.py` | #1 | 9 calls |
| `neuromem/memory/summaries.py` | #1 | 2 calls |
| `neuromem/__init__.py` | #1 | 3 calls |
| `neuromem/workflows/functions.py` | #1 | 1 call |
| `neuromem/core/controller.py` | #2 | Strip punctuation in `_keyword_fallback()` |
| `neuromem/core/retrieval.py` | #2 | Strip punctuation in `boost_keyword_matches()` |
| `neuromem/core/policies/conflict_resolution.py` | #3 | Content-based conflict detection |
| `neuromem/core/workers/ingest_worker.py` | #4 | Add entity extraction + graph registration |
| `tests/test_core.py` or `tests/test_query.py` | #5 | Add exact-match test |
| `neuromem/core/controller.py` | #6 | Temporal marker detection in `_is_multi_hop_query()` |
