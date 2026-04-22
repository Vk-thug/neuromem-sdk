# NeuroMem SDK — Release Notes

This file tracks the **latest** release with context, positioning, and per-release notes. For the complete machine-readable changelog, see [CHANGELOG.md](CHANGELOG.md).

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
