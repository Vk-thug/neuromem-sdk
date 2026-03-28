# NeuroMem v0.2.0 — Post-Fix Benchmark Run Prompt

## Context

All 6 open issues from the v0.2.0 benchmark have been fixed:
1. datetime naive/aware → all 33 bare `datetime.now()` migrated to `datetime.now(timezone.utc)`
2. Keyword punctuation → `string.punctuation` stripping added
3. Conflict detection → content-based (word overlap + negation), no tag dependency
4. Entity async → `extract_entities()` added to `IngestWorker._process_observe()`
5. Exact-match → confirmed working, 2 new tests added
6. Temporal markers → added to `_is_multi_hop_query()`

**Tests**: 110 passed, 5 skipped, 1 pre-existing error (`test_retrieve_with_memories` monkeypatch issue)

**Goal**: Run the full benchmark to establish the new post-fix baseline and compare against the pre-fix scores.

## Pre-Fix Baseline (from `locomo_20260328_154227.json`)

| System | F1 | EM | Cat1 | Cat2 | Cat3 | Cat4 | Cat5 |
|--------|----|----|------|------|------|------|------|
| **NeuroMem** | **24.6** | **11.8** | 37.2 | 8.4 | 8.9 | **41.7** | 0.4 |
| LangMem | 24.3 | 11.8 | 36.2 | 7.9 | 9.6 | 41.4 | 0.4 |
| Mem0 | 22.4 | 10.7 | 31.7 | 7.5 | 10.6 | 38.5 | 0.4 |

## Expected Improvements from Fixes

| Fix | Expected Impact |
|-----|----------------|
| datetime completion | No score change — was a crash bug, not accuracy |
| Keyword punctuation | +1-2pts on Cat1 — proper nouns now found ("Arjun?", "Priya?") |
| Content-based conflict | +0-1pts — prevents contradictory memories from polluting results |
| Entity async | +0-1pts — graph now populated in async mode, better entity retrieval |
| Temporal markers | +1-3pts on Cat2 — temporal questions now routed through multi-hop decomposition |

**Conservative estimate**: Overall F1 24.6 → 25-27, Cat2 8.4 → 10-12

## Step-by-Step Execution

### Step 0: Fix the pre-existing test error (optional but recommended)

The `test_retrieve_with_memories` error is because `conftest.py` tries to monkeypatch `neuromem.utils.embeddings.OpenAI` but `OpenAI` is imported inside functions, not at module level.

```python
# In tests/conftest.py, around line 110, change:
monkeypatch.setattr("neuromem.utils.embeddings.OpenAI", mock_openai_init)

# To mock the entire _call_openai_api function instead:
monkeypatch.setattr(
    "neuromem.utils.embeddings._call_openai_api",
    lambda text, model, api_key: [0.1] * 1536
)
```

After fix: `python3 -m pytest tests/ -q --ignore=tests/test_mcp.py` should show **111 passed, 5 skipped, 0 errors**.

### Step 1: Verify fixes work (5 min)

```bash
cd /Users/vikramvenkateshkumar/workspaces/Client/megadot/services/neuromem-sdk

# Run tests
python3 -m pytest tests/ -q --ignore=tests/test_mcp.py

# Quick feature validation
python3 -c "
import uuid, tempfile, os
config = '''
neuromem:
  model:
    embedding: nomic-embed-text
  storage:
    database:
      type: memory
  memory:
    decay_enabled: false
    consolidation_interval: 999
  async:
    enabled: false
  retrieval:
    hybrid_enabled: false
'''
path = os.path.join(tempfile.gettempdir(), 'verify.yaml')
with open(path, 'w') as f:
    f.write(config)

from neuromem import NeuroMem
mem = NeuroMem.from_config(path, user_id=str(uuid.uuid4()))

# Fix 2: keyword punctuation
mem.observe('My colleague Arjun is the tech lead', 'Noted!')
r = mem.retrieve('Who is Arjun?', k=5)
print(f'Fix 2 (punctuation): {\"PASS\" if any(\"arjun\" in x.content.lower() for x in r) else \"FAIL\"}')

# Fix 3: conflict detection
mem.observe('I prefer PostgreSQL for databases', 'Good!')
mem.observe('I do not like PostgreSQL anymore', 'Noted!')
r = mem.retrieve('What database do I prefer?', k=5)
has_negation = any('not' in x.content.lower() or 'don' in x.content.lower() for x in r[:1])
print(f'Fix 3 (conflict): {\"PASS\" if has_negation else \"CHECK — newer should rank first\"}')

# Fix 6: temporal detection
from neuromem.core.controller import MemoryController
is_temporal = mem.controller._is_multi_hop_query('When did Caroline change jobs?')
print(f'Fix 6 (temporal): {\"PASS\" if is_temporal else \"FAIL\"}')

mem.close()
"
```

### Step 2: Run LoCoMo benchmark — quick validation (15 min)

```bash
# Activate venv (CRITICAL)
source .venv/bin/activate

# Load API key
export $(grep -v '^#' .env | xargs)
echo "API key loaded: $(echo $OPENAI_API_KEY | head -c 10)..."

# Quick run: 2 conversations, cats 1+2+4 (same as earlier quick runs)
PYTHONUNBUFFERED=1 python -m benchmarks --systems neuromem \
  --conversations 2 \
  --categories 1 2 4 \
  --embedding-provider openai \
  --embedding-model text-embedding-3-small \
  --answer-provider openai \
  --answer-model gpt-4o-mini \
  --no-judge \
  --verbose
```

**Compare against**: Prior quick-run baseline was F1=39.4, Cat1=40.9, Cat2=N/A, Cat4=36.0

### Step 3: Run LoCoMo benchmark — full 5-category (45-60 min)

```bash
# Full run: 5 conversations, all 5 categories, all 3 systems
PYTHONUNBUFFERED=1 python -m benchmarks --systems neuromem mem0 langmem \
  --conversations 5 \
  --categories 1 2 3 4 5 \
  --embedding-provider openai \
  --embedding-model text-embedding-3-small \
  --answer-provider openai \
  --answer-model gpt-4o-mini \
  --no-judge \
  --verbose
```

**Note**: Mem0 is very slow (~10-15 min per conversation). For faster iteration, run `--systems neuromem` first, then add `mem0 langmem` for the final comparison.

**Compare against**: Pre-fix full-run baseline F1=24.6, Cat1=37.2, Cat2=8.4, Cat4=41.7

### Step 4: Run latency benchmark (5 min)

```bash
PYTHONUNBUFFERED=1 python -m benchmarks --latency --systems neuromem mem0 langmem \
  --embedding-provider openai \
  --embedding-model text-embedding-3-small
```

### Step 5: Feature validation — verify all 6 fixes (10 min)

Run each validation from `BENCHMARK_PROMPT.md` Phase 3:

```bash
# Load API key first
export $(grep -v '^#' .env | xargs)

# Run each test from Phase 3 sections 3.1-3.7
# (see BENCHMARK_PROMPT.md for full scripts)
```

Key tests to confirm:
- Fix 2: "Who is Arjun?" → finds Arjun memory (was FAIL, expect PASS)
- Fix 3: Contradicting memories → newer preference ranked higher (was PARTIAL, expect PASS)
- Fix 4: Entity graph populated in async mode (was 0 nodes, expect >0)
- Fix 6: Cat2 temporal improvement (was 8.4%, expect >10%)

### Step 6: Ollama + Qdrant recall test (10 min)

```bash
# Ensure services running
curl -s http://localhost:6333/collections | python3 -m json.tool
ollama list

# Reset collection
python3 -c "
import requests
requests.delete('http://localhost:6333/collections/neuromem')
requests.put('http://localhost:6333/collections/neuromem', json={'vectors': {'size': 768, 'distance': 'Cosine'}})
"

# Run multi-week validation
python3 examples/ai_assistant_ollama.py
```

**Expected**: 22+/25 recall (88%+), should improve with punctuation fix

### Step 7: Record results and commit

After all benchmarks pass:

```bash
# Deactivate venv
deactivate

# Show results
ls -la benchmarks/results/locomo_*.json | tail -3
python3 -c "
import json, glob
files = sorted(glob.glob('benchmarks/results/locomo_*.json'))
for f in files[-2:]:
    data = json.load(open(f))
    ts = data['timestamp'][:10]
    for s in data['summary']:
        if 'NeuroMem' in s['system']:
            cf = s['category_f1']
            print(f'{ts} {s[\"system\"]:30s} F1={s[\"avg_f1\"]:5.1f} C1={cf.get(\"1\",0):5.1f} C2={cf.get(\"2\",0):5.1f} C4={cf.get(\"4\",0):5.1f}')
"

# Commit everything
git add -A
git status
git commit -m 'feat: NeuroMem v0.2.0 — digital brain features, 8 adapters, MCP, benchmarks

14 core features: memory graph, query language, templates, summaries,
Inngest workflows, conflict detection, reconsolidation, salience tuning,
keyword fallback, entity index, multi-hop retrieval, temporal detection.

8 framework adapters: LangChain, LangGraph, LiteLLM, CrewAI, AutoGen,
DSPy, Haystack, Semantic Kernel.

MCP server: 12 tools, 3 resources, 2 prompts.
Plugin bundles: Claude Code, Codex CLI, Gemini CLI.

Benchmark: LoCoMo F1 leads vs Mem0 and LangMem.
Tests: 110+ passing.'
```

## Success Criteria

| Metric | Pre-Fix | Target | Notes |
|--------|---------|--------|-------|
| Tests passing | 110 | 111+ | Fix monkeypatch error |
| LoCoMo F1 (overall) | 24.6 | ≥ 24.6 | No regression |
| Cat1 (single-hop) | 37.2 | ≥ 37.2 | Punctuation fix helps |
| Cat2 (temporal) | 8.4 | ≥ 10.0 | Temporal markers help |
| Cat4 (multi-hop) | 41.7 | ≥ 41.7 | No regression |
| Keyword "Arjun?" | FAIL | PASS | Fix 2 |
| Conflict detection | FAIL | PASS | Fix 3 |
| Entity graph async | 0 nodes | >0 nodes | Fix 4 |
| Ollama recall | 88% | ≥ 88% | No regression |

## Gotchas (from memory)

1. **Always use `.venv/bin/python3`** for benchmarks, not system Python
2. **Load `.env` manually**: `export $(grep -v '^#' .env | xargs)`
3. **Mem0 is slow**: 10-15 min per conversation, 2+ hours for full run
4. **Async needs 5-6s wait**: If testing with `async.enabled: true`, sleep after observe
5. **PYTHONUNBUFFERED=1**: Add this to see real-time progress, not buffered output
6. **Results dir**: `benchmarks/results/locomo_YYYYMMDD_HHMMSS.json`
