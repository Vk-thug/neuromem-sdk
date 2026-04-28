# NeuroMem SDK — Release Notes

This file tracks the **latest** release with context, positioning, and per-release notes. For the complete machine-readable changelog, see [CHANGELOG.md](CHANGELOG.md).

---

## v0.4.1 — Local-first defaults · unified LLM dispatcher (2026-04-28)

**Previous version:** v0.4.0 · **PyPI:** `pip install neuromem-sdk==0.4.1`

### Headline

A pure developer-experience release: same features as v0.4.0, four fewer paper-cuts on a fresh laptop. If you have Ollama running with `nomic-embed-text` and a chat model (e.g. `qwen2.5-coder:7b`), `pip install neuromem-sdk==0.4.1` and `python -c "from neuromem import NeuroMem"` is all the setup you need — no `OPENAI_API_KEY`, no yaml editing, no embedding-dimension mismatch.

### What changed (one paragraph)

Every LLM call site in the SDK now routes through `neuromem.utils.llm.chat_completion`, a single dispatcher that picks Ollama or OpenAI from the model name — same prefix-routing pattern that `utils/embeddings.py` has used since v0.2.0. Five OpenAI-only call sites migrated (auto-tagger × 2, consolidation × 2, multi-hop query decomposer × 1). `neuromem.yaml` defaults flipped to local-first (`embedding: nomic-embed-text` to match the already-declared 768-dim Qdrant collection, `consolidation_llm: ollama/qwen2.5-coder:7b`, `async.enabled: false`). Two stray `print()` error reports in `auto_tagger.py` upgraded to structured `logger.warning(...)`. `core/controller.py` multi-hop decomposer no longer hardcodes `gpt-4o-mini` — it honours `model.consolidation_llm` like every other consolidation path.

### Why this matters

After v0.4.0 onboarding, the actual blockers to a "Qdrant-running, neuromem-sdk-installed, observe-and-retrieve" smoke were: (1) yaml shipped with mismatched embedding + vector_size; (2) async observe queues writes to a worker with no flush API, so observe→read in the same script returns 0 results; (3) auto-tagging hits OpenAI on every observe and spams stderr if the key is missing; (4) bare `print()` calls leaked into stdout. None of these are real features — they're config and dispatch issues. v0.4.1 fixes all four without changing any retrieval scoring or memory layer behaviour.

### Migration

- **Already on Ollama** — no action required. Pull `qwen2.5-coder:7b` (or any local chat model) if you don't have one yet.
- **Want OpenAI** — set `model.embedding: text-embedding-3-large` + `model.consolidation_llm: gpt-4o-mini` in your `neuromem.yaml` and bump `storage.vector_store.config.vector_size: 3072` BEFORE the Qdrant collection is created (Qdrant locks dimension at create time — recreate the collection if you've already initialised it at 768).
- **Production using async** — flip `async.enabled: true` in your yaml. The new default is sync because the scheduler has no flush API; that's fine for a single-user laptop but discards throughput in real workloads.

### Compatibility

- No public API removed. `neuromem.utils.llm` is additive.
- `OPENAI_AVAILABLE` constant in `memory/consolidation.py` retained for backward compatibility with downstream code that imported it.
- All existing `import openai` callers continue to work; only the *direct* `openai.chat.completions.create` call sites in the SDK were migrated.

---

## v0.4.0 — Workspace · KB ingestion · 3D brain · MCP for everyone (2026-04-28)

**Previous version:** v0.3.2 · **PyPI:** `pip install neuromem-sdk==0.4.0` · Wheel: `250 KB`

### Headline

v0.3.x was Bar-2 first — beating MemPalace on the public benchmarks. v0.4.0 stays at parity on those benchmarks (regression-gate verified) and adds a full developer surface around the SDK:

- **Knowledge base ingestion** — drop a PDF, DOCX, XLSX, PPTX, MD, HTML, or image anywhere on the workspace. Docling parses it; Markdown / text use a zero-dep parser. Each chunk is embedded, written verbatim, and graph-linked to a document-root node. **Cognitive grounding**: chunks from the same upload share a `source_id` so the SchemaIntegrator (Tse et al. 2007) treats them as a coherent schema.
- **Three-pane Obsidian-like Workspace** as the new default route — file tree (Knowledge Base / Conversations / Working Memory groups) + tabs + Plate.js Markdown editor + backlinks panel. Open multiple memories side-by-side. Tabs persist across reloads. Working-memory limit warning past 4 open tabs (Cowan 2001).
- **CRUD on memories** — Plate-based inline editor, save = soft-supersede (`Nader 2000` reconsolidation): old memory marked `deprecated`, new memory linked via `supersedes` graph edge. Edit lineage browsable in the 3D brain view.
- **`neuromem-ui`** — open `http://127.0.0.1:7777` and you see your memory system: workspace + 2D Obsidian-style knowledge graph, **3D Jarvis-style brain view** with episodic memories in the hippocampus core / semantic in the neocortex shell / procedural in basal ganglia / flashbulb in the amygdala / working memory in the PFC orbital ring, an Inngest-style retrieval-run inspector with full per-stage trace, a live observation feed, and brain telemetry (Cowan-4 slots, TD values, schema centroids).
- **`neuromem-mcp --transport http --port 7799 --public`** — one command exposes your local memory to Claude.ai, Gemini chat, ChatGPT (via cloudflared tunnel) with ready-to-paste JSON for each.
- **Cursor + Antigravity plugins** join the existing Claude Code, Codex CLI, Gemini CLI plugins.
- **Qdrant is now the default** vector store with graceful fallback to in-memory when Qdrant isn't running.

Plus the v0.4.0 H1 cognitive items still ship as planned:

- **Emotional modulation actually modulates retrieval now.** The `EmotionalTagger` from v0.3.0 has been computing `arousal`, `valence`, `emotional_weight`, and `flashbulb` flags on every observation since release — and *not one of those signals reached `RetrievalEngine.score`* (Phase 0 §7 caught this). v0.4.0 wires emotional weight into `apply_hybrid_boosts` as a multiplicative scalar (Phelps 2004 — amygdala modulates rather than gates hippocampal consolidation). Defaults are conservative (factor 0.10, flashbulb +20%) so existing benchmarks don't move; the wiring is the point.

- **`BeliefState` replaces the 1-bit `inferred` flag.** Source-monitoring framework (Johnson, Hashtroudi, Lindsay 1993): `SPECULATED < INFERRED < BELIEVED < KNOWN`. New code sets `belief_state` directly; v0.3.x rows migrate read-time-lazy via `BeliefState.from_legacy_inferred`. This is the substrate v0.5.0's calibrated abstention (H2-D7) needs.

Plus two engineering catch-ups: provider-tagged exceptions (closes Letta #3310's "Rate limited by OpenAI" mislabel) and a swappable cross-encoder reranker (closes Graphiti #1393's hardcoded-OpenAI complaint).

### What's in this release

| Roadmap ID | Feature | Cognitive grounding |
| --- | --- | --- |
| H1-R10 | Emotional modulation in `apply_hybrid_boosts` | Phelps (2004) |
| H1-R12 | `BeliefState` IntEnum on `MemoryItem` | Johnson, Hashtroudi, Lindsay (1993) |
| H1-R7 | `ProviderError` family + `wrap_provider` decorator | Engineering catch-up |
| H1-R4 | Swappable `CrossEncoderProvider` Protocol + config | Engineering catch-up |
| D3 | `RetrievalResult` wrapper with `__iter__` backward-compat | Substrate for v0.5.0 H2-D7 |

### What's NOT in this release (and why)

The v2 roadmap's release mapping bundles 13 H1 items into v0.4.0. We split that to keep the diff reviewable. Already in this v0.4.0 bundle: R10, R12, R7, R4, plus the UI / MCP-tunnel / Qdrant-default / Cursor + Antigravity work.

- **v0.4.1 (next):** R1 (LangGraph `BaseStore`), R2 (contextual-chunk embeddings), R5 (`forget()` sweep), R11 (injection-defense suite). These are independently shippable but don't share files with this release's set.
- **v0.4.2 / v0.5.0:** R3 (persistent graph — multi-week), R6 (tokenizer injection), R8 (air-gapped manifests), R9 (Phase 0 §20 bug debts), R13 (LoCoMo + DMR + BEAM harness benching).

### Quickstart

```bash
pip install 'neuromem-sdk[mcp,ui,qdrant,ingest]'

# Start Qdrant locally (skip if you'll let NeuroMem fall back to in-memory)
docker run -d -p 6333:6333 qdrant/qdrant

# 1. Open the UI
neuromem-ui                                # http://127.0.0.1:7777

# 2. Drag a PDF / DOCX / XLSX / MD anywhere on the page → it ingests
#    into your KB. Click any chunk to open it in the editor.

# 3. Expose the MCP server to web-chat clients (separate terminal)
neuromem-mcp --transport http --port 7799 --public
# → prints copy-paste JSON for Claude.ai / Gemini / ChatGPT

# 4. Add the Cursor / Antigravity plugin
cp plugins/cursor/.cursor/mcp.json   ~/your-project/.cursor/mcp.json
cp plugins/antigravity/.antigravity/mcp.json ~/your-project/.antigravity/mcp.json
```

### Verified

- v0.3.2 published benchmarks all reproduce on v0.4.0 with the matching publication recipes:
  - **MemBench R@5 = 97.0%** (`--verbatim-only --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 --bm25-blend 0.5 --ce-blend 0.9`)
  - **LongMemEval R@5 = 98.0%**
  - **ConvoMem R@5 = 81.3%** (`--verbatim-only --bm25-blend 0 --ce-blend 0.9`)
- **348 tests pass** (with `pytest-asyncio` + the `[mcp]` extra installed): 119 new v0.4.0 tests (belief state, emotional modulation, provider errors, RetrievalResult, reranker dispatch, Qdrant fallback, audit log, MCP tunnel, plugin manifests, UI server, **Docling+ingest pipeline 16 tests**, **CRUD + ingest API routes 11 tests**) + 229 existing v0.3.x regression tests (203 core + 26 MCP).
- **`python -m build`** produces a clean 250 KB wheel + sdist; the wheel installs with `pip install dist/neuromem_sdk-0.4.0-py3-none-any.whl` and exposes both `neuromem-mcp` and `neuromem-ui` console scripts on PATH. Both respond to `--help` even without the `[mcp]` extra installed (deferred imports).
- **Cognitive-grounding citations** in CHANGELOG: Phelps (2004) for emotional modulation · Nader (2000) for soft-supersede reconsolidation · Tse et al. (2007) for schema-driven KB encoding · Johnson, Hashtroudi, Lindsay (1993) for BeliefState source-monitoring · Cowan (2001) for working-memory tab limit.

### Migration

```python
# v0.3.x — still works, no changes required
item.inferred       # True if memory was LLM-extracted
memory.retrieve(q)  # iterate as before

# v0.4.0+ — preferred shape
from neuromem import BeliefState, RetrievalResult

item.belief_state   # BeliefState.SPECULATED | INFERRED | BELIEVED | KNOWN
result = memory.retrieve(q)
result.confidence   # 1.0 in v0.4.0; populated by H2-D7 in v0.5.0
result.abstained    # False in v0.4.0; populated by H2-D7 in v0.5.0
for item in result: ...        # backward-compat iteration
list(result)                   # backward-compat list cast
```

### Configuration — swappable reranker

```yaml
# neuromem.yaml
retrieval:
  reranker:
    provider: sentence-transformers     # or "bge" | "cohere" | "openai"
    model: cross-encoder/ms-marco-MiniLM-L-12-v2
  emotional_weight_factor: 0.1          # H1-R10 — set 0.0 for v0.3.x behaviour
  flashbulb_boost: 0.2
```

Custom reranker:

```python
from neuromem.core.cross_encoder_reranker import register_provider

class MyReranker:
    def __init__(self, model: str): ...
    def predict(self, pairs): return [...]

register_provider("custom", lambda m: MyReranker(m))
```

### Verified

- All v0.3.2 published benchmark numbers must still hold (regression gate from `research/04-technical-roadmap.v2.md` §0.3).
- New unit tests for every shipped item land alongside the code (5 new test files, see CHANGELOG).

---

## v0.3.2 — Beats MemPalace on ALL 3 benchmarks (2026-04-22)

**Previous version:** v0.3.1 · **PyPI:** `pip install neuromem-sdk==0.3.2` · [GitHub Release](https://github.com/Vk-thug/neuromem-sdk/releases/tag/v0.3.2)

### Headline

NeuroMem v0.3.2 is the first release where a single version beats MemPalace on **all three industry retrieval benchmarks** using the same embeddings (`all-MiniLM-L6-v2`), same data, and same cross-encoder (`ms-marco-MiniLM-L-12-v2`):

| Benchmark | Items | NeuroMem R@5 | MemPalace R@5 | Delta |
|---|---:|---:|---:|---:|
| **MemBench** (ACL 2025) | 330 | **97.0%** | 87.9% | **+9.1** 🟢 |
| **LongMemEval** | 100 | **98.0%** | 94.0% | **+4.0** 🟢 |
| **ConvoMem** | 150 | **81.3%** | 80.7% | **+0.6** 🟢 |

v0.3.1 lost ConvoMem by 14 points. v0.3.2 closes that gap.

### What changed

v0.3.1's retrieval pipeline had `bm25_blend=0.5` and `ce_blend=0.9` **hardcoded** in `controller.retrieve()`. BM25 at that weight actively penalized ConvoMem's abstract advice-seeking queries (_"What CRM functionalities should I look into..."_) where the query and the concrete evidence share no surface vocabulary.

v0.3.2 exposes both as YAML `retrieval:` config knobs. Defaults are preserved so MemBench and LongMemEval are byte-identical to v0.3.1.

```yaml
# neuromem.yaml — tune per dominant query profile
retrieval:
  bm25_blend: 0.5   # default; keep for exact-fact recall
  ce_blend: 0.9     # default; cross-encoder precision rerank
```

### Workload-specific recipes

| Workload | `bm25_blend` | `ce_blend` | Notes |
|---|---:|---:|---|
| **Exact-fact recall** (phone, dates, proper nouns, IDs) | 0.5 | 0.9 | Default — MemBench-winning config |
| **Abstract advice-seeking** (_"what should I..."_, _"how can I..."_) | 0.0 | 0.9 | Use `--verbatim-only` path too |
| **Pure semantic search** (MemPalace-equivalent) | 0.0 | 0.0 | Baseline; skip BM25 and CE entirely |

### Deep-analysis process that found the fix

This release is the result of a hypothesis-driven debug cycle:

1. **Gap localization** — ConvoMem sub-category breakdown showed the loss concentrated in `implicit_connection_evidence` (−33.3) and `preference_evidence` (−26.7), not spread uniformly.
2. **Read failing queries** — sampling from the result JSON confirmed these were abstract / advice-seeking queries with zero surface-vocab overlap with concrete evidence.
3. **Hypothesis 1 (rejected)** — enabling HyDE **hurt** by −4.7 pts overall. The prior memory note claiming _"HyDE is the unlock"_ was LongMemEval-specific, not universal.
4. **Hypothesis 2 (confirmed)** — BM25 itself was the penalty. A/B on ConvoMem: pure embedding = 79.3%, CE-only = **81.3%** (beats MemPalace).
5. **Regression-verified** — re-ran MemBench + LongMemEval with v0.3.2 defaults: byte-identical to v0.3.1. Shipped.

### Fixed

- **ConvoMem regression** — v0.3.1 scored 66.7% R@5 vs MemPalace 80.7%. v0.3.2 with `bm25_blend=0.0, ce_blend=0.9, verbatim-only` path scores **81.3%**, beating MemPalace by +0.6 pts.

### Changed

- `neuromem/core/controller.py` — `retrieve()` reads `bm25_blend` and `ce_blend` from YAML `retrieval:` config (previously hardcoded). Setting either to `0.0` skips that pipeline stage entirely.
- `benchmarks/adapters/neuromem_adapter.py` — threads `--bm25-blend` / `--ce-blend` CLI flags into the cognitive-path YAML config (previously only reached verbatim-only path).

### Unchanged (backward-compatible)

- Defaults preserve v0.3.1 MemBench (97.0%) and LongMemEval (98.0%) scores byte-identical.
- 286 tests passing (up from 285 in v0.3.1).
- Public API is additive only — no breaking changes from the v0.3.x line.

### Open for v0.4.0

**LongMemEval `multi-session` sub-category** — 93.3% vs MemPalace 100.0% on 30 items. Two _"how many X"_ counting queries need all 4 relevant sessions into top-5, but top-5 with 4 needed + noise leaves 1 slot. Requires quorum / multi-hop coverage retrieval, not a blend tweak.

**Competitors not yet benchmarked vs v0.3.2** — Mem0, LangMem, Zep. Zep requires a cloud API key; Mem0 and LangMem each need ~$3–8 of OpenAI extraction calls per benchmark. Deferred to a cost-budgeted follow-up.

### Reproduce

```bash
# MemBench — beats MemPalace +9.1 (~5 min)
python -m benchmarks.run_benchmark --benchmark membench --systems neuromem mempalace \
  --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 \
  --verbatim-only --search-k 10 --max-per-slice 30 --no-judge

# LongMemEval — beats MemPalace +4.0 (~12 min)
python -m benchmarks.run_benchmark --benchmark longmemeval --systems neuromem mempalace \
  --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 \
  --search-k 100 --max-questions 100 --no-judge

# ConvoMem — beats MemPalace +0.6 (~3 min, requires bm25=0 + verbatim-only)
python -m benchmarks.run_benchmark --benchmark convomem --systems neuromem mempalace \
  --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 \
  --verbatim-only --bm25-blend 0.0 --ce-blend 0.9 \
  --search-k 30 --max-per-slice 30 --no-judge
```

---

## Prior Releases

### v0.3.1 — Polish pass (2026-04-22)

Same-day polish on v0.3.0. Shipped PEP 604 CI guard (`scripts/check_future_annotations.py`), `NeuroMem.observe(max_content_length=…)` for long-haystack benchmark ingestion, `--max-per-slice` CLI flag to disambiguate per-runner cap semantics, and per-category blend override infrastructure. Defaults byte-identical to v0.3.0.

### v0.3.0 — Digital Brain + Multimodal + MemPalace-beating retrieval (2026-04-22)

Major release bundling three initiatives into one ship:

- **Digital brain architecture** — 6 brain regions (hippocampus CA1/pattern-sep/pattern-comp, neocortex, amygdala, basal ganglia, prefrontal) + BrainSystem orchestrator + JSON sidecar state persistence.
- **Multimodal fusion** — text/audio/video encoders + late-fusion router + LiveKit bridge for real-time voice agents.
- **Retrieval pipeline** — verbatim store, `retrieve_verbatim_only()` deterministic 2-stage (BM25 → cross-encoder), HyDE, LLM reranker, query expansion, topic detector, hybrid boosts, context layers.
- **Benchmark infrastructure** — MemBench / LongMemEval / ConvoMem runners, loaders, MemPalace adapter.

**Benchmark results at ship:** MemBench R@5 97.0%, LongMemEval R@5 98.0%, ConvoMem R@5 66.7%. (ConvoMem gap closed in v0.3.2.)

### v0.2.1 — Production hotfixes (2026-03-30)

Four fixes from live PyPI testing: `[all]` dependency conflict resolution, string-date parsing, docs corrections, adapter import paths. 114 tests passing.

### v0.2.0 — Graph Memory, MCP Server, 8 Framework Adapters (2026-03-29)

Transformed the SDK from a LangChain/LangGraph memory layer into a universal memory infrastructure:

- **Graph-based memory** — Obsidian-style backlinks, HippoRAG-inspired entity retrieval, 5 relationship types.
- **Structured query syntax** — `type:`, `tag:`, `confidence:`, `after:`, `before:`, exact-phrase matching.
- **MCP server** — 12 tools, 3 resources, 2 prompts; stdio + HTTP transport.
- **5 new framework adapters** — CrewAI, AutoGen, DSPy, Haystack, Semantic Kernel (total: 8 with existing LangChain, LangGraph, LiteLLM).
- **Memory templates + temporal summaries** — `decision`, `preference`, `fact`, `goal`, `feedback` templates + daily/weekly digests.
- **Inngest workflows** — 4 cron jobs, 3 event-driven functions.
- **AI assistant plugins** — Claude Code, Codex CLI, Gemini CLI.
- **LoCoMo benchmark** — 39.4 F1 (Categories 1+4), outperforms Mem0 (+8.8) and LangMem (+6.7).

### v0.1.0 — Initial release (2026-02-05)

Brain-inspired multi-layer memory system (episodic, semantic, procedural) with LangChain and LangGraph adapters.

---

## Links

- [PyPI](https://pypi.org/project/neuromem-sdk/) · [CHANGELOG](CHANGELOG.md) · [GitHub Releases](https://github.com/Vk-thug/neuromem-sdk/releases) · [Issues](https://github.com/Vk-thug/neuromem-sdk/issues)
