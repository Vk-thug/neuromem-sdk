# Phase 6 v2 — Technical Roadmap (revised 2026-04-24)

*Supersedes `04-technical-roadmap.md` as the active working roadmap. v1 is the as-of-2026-04-24 pre-revision snapshot and remains immutable.*

**What changed vs v1.** Two inputs not available when v1 was written:
1. **Competitor analysis of Neural AI / Anant 1.0** — surfaces 6 new/extended items (`reference_competitor_anant_neuralai.md` + `project_anant_roadmap_impacts.md`).
2. **North-star goals set by Vikram on 2026-04-24** — two mission bars: match human-brain memory + beat every available and upcoming AI memory system (`project_north_star_goals.md`).

The north-star goals reshape *priority order*, not the underlying analysis. Every v1 item is preserved; 4 are accelerated; 6 are added from Anant analysis; 4 are added from Bar 1 human-memory capability gaps; a new work stream (continuous competitive benching) runs alongside. Two operational rules are new (§0.2, §0.3).

**Base version:** neuromem-sdk v0.3.2. **Target v0.4.0 cutline:** ~4 weeks. Revised release sequence is §Release Mapping at the bottom.

---

## 0. Operating rules

### 0.1 Horizons — unchanged from v1
- **H1 — table stakes (0-4 weeks).** Catch-up / commodity expectations. Do not claim cognitive grounding on these.
- **H2 — differentiators (1-3 months).** Where NeuroMem wins. Cognitive grounding mandatory — every H2 item must cite a Phase-2 subsection.
- **H3 — research bets (3-6 months).** Publishable negative results acceptable.

### 0.2 North-star decision filter (NEW)

Every proposed item answers two questions before it ships:

1. **Does this close a Bar-1 behavioural gap?** (I.e., one of the 10 human-memory capabilities in `project_north_star_goals.md` §"Bar 1".)
2. **Does this contribute to Bar-2 public benchmark lead?** (I.e., measurably improves a published benchmark OR enables a new benchmark NeuroMem uniquely wins.)

- **Both yes** → priority over items scoring only one.
- **Exactly one yes** → ships if effort is S and regression bar is met.
- **Neither yes** → defer unless it's a pure correctness / security fix.

This filter sits above horizon tags, above effort tags, above user-demand signals.

### 0.3 Two-bar merge gate — unchanged from v1
Every item lands behind:
1. **Regression gate.** MemBench R@5 ≥ 97.0%, LongMemEval R@5 ≥ 98.0%, ConvoMem R@5 ≥ 81.3% (v0.3.2 baselines).
2. **Item-specific win bar.** Named per item's test plan.

Failing bar 1 blocks merge. Meeting bar 1 but not bar 2 merges only with `status: experimental` config flag off-by-default.

### 0.4 Competitor-benching work stream (NEW)

A standing maintenance task across horizons: keep `benchmarks/adapters/` current for every named competitor. When a new competitor launches (Anant public launch, Mem0 v4, HippoRAG 3, etc.), the response is a benched comparison within 1 week. This is not a roadmap item — it's a rolling commitment. Budget ~1 engineer-day per new competitor.

---

## Summary of what moved

### Promotions from v1
- **H1/H2 emotional-weight re-ranking wiring** → fixed as **H1-R10** (Bar 1 item 5 free win + enables EmotionalRecall benchmark).
- **H3-B2 Should-I-retrieve-at-all gate** → promoted to **H2-D7 Calibrated abstention** (Bar 1 item 10 + reduces false top-k on chitchat).
- **H2-D1 PPR** → order-position 1 inside H2 (closes v0.3.2 README's honest-open-item on LongMemEval multi-session).

### New items from Anant analysis
- **H1-R11** Injection-defense test suite.
- **H1-R12** Belief-state 4-level upgrade.
- **H2-D8** Cross-script coreference (extends H1-R6).
- **H2-D2** replay scheduler extended with gap-detection + follow-up-question + transitive inference + emotional-weight rerank stages (Anant Memory Dreams parity).
- **H1-R8** Docker/Cloud Run extended with air-gapped deployment spec.

### New items from north-star Bar 1 gaps
- **H2-D9** Self-narrative generation (Bar 1 item 9 — autobiographical continuity).
- **H3-B6** Prospective-memory API (Bar 1 item 8).
- **H2-D7** Calibrated abstention (already listed above — serves both Bar 1 item 10 and Self-RAG gating).

### New items from Bar 2
- **H1-R13** LoCoMo + DMR + BEAM harness benching under NeuroMem runner, apples-to-apples vs Mem0 v3 / Zep / Letta / LangMem.
- **H2-D10** Publish `LongFacts` benchmark — multi-session contradiction retention.
- **H3-B7** Publish `SlowConsolidationBench` — post-offline-period schema extraction.
- **H3-B8** Publish `EmotionalRecall` benchmark.
- **H3-B9** Publish `ProspectiveRecall` benchmark (pairs with H3-B6).

---

## H1 — Table stakes (0-4 weeks)

H1 totals: 13 items, ~5-6 engineer-weeks with parallelism. R3 (persistent graph, L effort) remains the dominant cost and may spill into H2 as in v1.

### H1-R1 — `NeuroMemStore(BaseStore)` for LangGraph
**North-star score.** Bar-1 no. Bar-2 indirect (enables adoption → benchmark submissions from LangGraph users). Ships because effort is S-M and it resolves LangMem #154 pain.
**Unchanged from v1** — see `research/04-technical-roadmap.md` H1-R1.

### H1-R2 — Contextual-chunk embeddings in `VerbatimStore`
**North-star score.** Bar-1 no. Bar-2 yes — Anthropic study projects up to −35% failure-rate reduction, directly contributes to LongMemEval/ConvoMem lead.
**Unchanged from v1.**

### H1-R3 — Persistent graph via `GraphBackend` Protocol
**North-star score.** Bar-1 no (in-process graph already enables retrieval). Bar-2 indirect — unblocks H2-D1 PPR (which is Bar-2 critical) and H2-D5 community summaries.
**Unchanged from v1.** Critical-path item — if it slips, H2 stalls.

### H1-R4 — Swappable reranker config section
**North-star score.** Bar-1 no. Bar-2 yes — unblocks reranker-model A/B benchmarks (provider-independent numbers).
**Unchanged from v1.**

### H1-R5 — `forget()` sweep across all surfaces
**North-star score.** Bar-1 item 3 partial (not RIF, but the engineering substrate for selective forgetting). Bar-2 no. Ships because enterprise compliance is table stakes.
**Unchanged from v1.**

### H1-R6 — Tokenizer / entity-extractor injection points
**North-star score.** Bar-1 no. Bar-2 indirect — unlocks non-English benchmarks (Anant's Hindi market). Ships as the foundation for H2-D8 cross-script coref.
**Unchanged from v1.**

### H1-R7 — Provider-tagged exceptions
**North-star score.** Neither. Ships as correctness polish (Letta #3310 parity).
**Unchanged from v1.**

### H1-R8 — Docker + Cloud Run + Air-gapped deployment manifests (EXTENDED)

**Problem (v2).** v1 ships Docker + Cloud Run. Anant's explicit "air-gapped sovereign deployment" is table stakes for Indian-government / BFSI / regulated-sector buyers — and pairs with NeuroMem's existing `verbatim-only` retrieval path which works without any LLM call.

**Cognitive grounding.** Engineering / compliance.

**Prior art.** Anant Enterprise deployment spec (see `reference_competitor_anant_neuralai.md`); Letta's `compose.yaml`.

**Target.**
```
deploy/
  Dockerfile
  docker-compose.yml
  cloudrun/service.yaml
  airgapped/
    docker-compose.airgapped.yml   # no external network
    README.md                       # sentence-transformers bundle, Ollama-hosted LLM, verbatim-only default
    bundle-embeddings.sh            # offline model download helper
  README.md
```

**Test plan.** CI build + boot + smoke-test, plus an air-gapped boot test that runs with no outbound network.

**Effort.** **S-M** (~5-7 days, extends v1's 2-3d).

**Risk / cost.** Low.

### H1-R9 — Pay down Phase 0 §20 bug debts
**North-star score.** Bar-1 no direct but `days_threshold=0` fix is *prerequisite* for H2-D2 replay scheduler (Bar-1 item 6). Bar-2 indirect.
**Unchanged from v1.**

### H1-R10 — Emotional-weight re-ranking wiring (NEW, promoted from Anant analysis + Bar 1 item 5)

**Problem.** `EmotionalTagger` computes `arousal`, `valence`, `emotional_weight`, `flashbulb` on every observation (Phase 0 §7). None of these signals feed into `RetrievalEngine.score` or the cross-encoder blend. Bar-1 item 5 explicitly demands this wiring. Anant explicitly "re-ranks entities by emotional weight rather than mention frequency" — we have the signal and don't use it.

**Cognitive grounding.** Phelps (2004) — amygdala modulates hippocampal consolidation. `research/02-cognitive-alignment.md` §12. The signal is already computed and already cognitively grounded; this is pure plumbing.

**Prior art.** Anant Memory Dreams "importance re-ranking by emotional weight"; general affect-modulated recall literature.

**Proposed API.**
```yaml
retrieval:
  emotional_weight_factor: 0.1   # 0.0 disables, matches v0.3.2 behaviour
  flashbulb_boost: 0.2           # additional boost for metadata["flashbulb"]=True
```
```python
# neuromem/core/retrieval.py  RetrievalEngine.score()
score += self.emotional_weight_factor * item.metadata.get("emotional_weight", 0.0)
if item.metadata.get("flashbulb", False):
    score += self.flashbulb_boost
```

**Data-model delta.** None — fields already exist on `MemoryItem.metadata`.

**LangGraph integration.** Transparent.

**Test plan.**
- Unit: asserting scored retrieval on a corpus with varied `emotional_weight` matches the expected ordering.
- Regression: MemBench / LongMemEval / ConvoMem (emotional content is a small fraction; expect no drop at `emotional_weight_factor=0.1`).
- **New benchmark (H3-B8 gate):** EmotionalRecall. Success criterion: emotionally-labelled correct answers rank at R@5 ≥ baseline + 10 pts at `factor=0.2`.

**Effort.** **S** (~3 days).

**Risk / cost.** Low. Mitigations: ships at `factor=0.1` default; can be tuned per workload; disabled at `0.0` preserves v0.3.2 behaviour.

### H1-R11 — Injection-defense test suite (NEW, from Anant analysis)

**Problem.** Anant publishes 7/8 sophisticated injection attacks fully blocked. NeuroMem runs LLM calls over raw user content in `Consolidator`, `HyDE`, `llm_reranker`, and returns memory content into downstream LLM contexts with no sanitisation. No injection-defense test suite exists.

**Cognitive grounding.** Engineering / security.

**Prior art.** OWASP LLM Top 10; Anant's public 7/8 claim.

**Proposed API.** No public API change. New private `tests/test_injection_defense.py` + optional `core/safety.py` sanitisation helpers used at LLM-call boundaries.

**Test plan.** Minimum 10 canonical injection prompts covering:
- System-prompt override (`IGNORE PREVIOUS INSTRUCTIONS...`).
- Tool-call injection (content that looks like a tool call).
- Identity override (content claiming to be a system message).
- Memory poisoning (content that tries to promote itself to `semantic` with high salience).
- Cross-user data extraction (content asking to retrieve a different user's memories).
- Prompt cache poisoning.
- Unicode / zero-width / bidi confusable attacks.
- Plus 3 additional per the Mem0 / Letta / LangMem threat models.

Each attack: extraction path must audit-log; retrieval path must not return a poisoned memory above threshold; consolidation must not promote an injection to semantic.

Publish pass rate as a benchmark number in the README.

**Effort.** **S** (~3-5 days).

**Risk / cost.** Low. Pure additive work.

### H1-R12 — Belief-state 4-level upgrade (NEW, from Anant analysis + general calibration need)

**Problem.** `MemoryItem.inferred: bool` is too coarse. Anant ships Known / Believed / Inferred / Speculated. Downstream LLMs can calibrate confidence in retrieved context only if the source-reliability signal is richer than 1 bit. This is the substrate for Bar-1 item 10 (meta-memory / calibrated abstention).

**Cognitive grounding.** Johnson, Hashtroudi, Lindsay (1993) *Psychological Bulletin* 114(1):3-28 — source-monitoring framework.

**Prior art.** Anant belief states; Zep/Graphiti provenance; epistemic-logic.

**Proposed API.**
```python
from enum import IntEnum

class BeliefState(IntEnum):
    SPECULATED = 0   # LLM-extrapolated beyond stated facts
    INFERRED = 1     # LLM-extracted from stated facts
    BELIEVED = 2     # User-stated, not corroborated
    KNOWN = 3        # User-stated, cross-corroborated across sessions

@dataclass
class MemoryItem:
    ...
    belief_state: BeliefState = BeliefState.BELIEVED   # default for user-observed
    # Migration: inferred=True → INFERRED, inferred=False → BELIEVED (not KNOWN — requires corroboration)
```

**Data-model delta.** New column / field. Backward-compat: `inferred` deprecated but retained for one minor version; `belief_state` default `BELIEVED`.

**LangGraph integration.** `NeuroMemStore` surfaces `belief_state` in `Item.value["belief_state"]`.

**Test plan.**
- Migration test: all existing memories round-trip `inferred` ↔ `belief_state` correctly.
- `explain()` surfaces `belief_state`.
- Retrieval ordering: tiebreak uses `belief_state` (KNOWN > BELIEVED > INFERRED > SPECULATED) when composite scores tie.

**Effort.** **S** (~2-3 days).

**Risk / cost.** Low. Mitigations: additive field with sane default; deprecation window for `inferred`.

### H1-R13 — LoCoMo + DMR + BEAM harness benching (NEW, from Bar 2)

**Problem.** Vendor-published numbers for competitors are from their own harnesses — not apples-to-apples vs NeuroMem. Bar 2 requires NeuroMem leads on public benchmarks; "lead" is not verifiable until all systems bench on the same runner. Three benchmarks are currently unbenched on NeuroMem's harness: LoCoMo (Mem0 publishes 91.6 vendor; NeuroMem v0.2.0 ran 39.4 on a different subset), DMR (Zep publishes 94.8), BEAM-1M / 10M (Mem0 publishes 64.1 / 48.6).

**Cognitive grounding.** None — this is a benchmarking task.

**Prior art.** Existing `benchmarks/runners/` infrastructure + adapters for `neuromem`, `mempalace`, `mem0`, `langmem`, `zep`.

**Target.** Three new runners under `benchmarks/runners/`: `locomo_runner.py` (already exists for v0.2.0 — extend/fix), `dmr_runner.py` (new), `beam_runner.py` (new). Each runs NeuroMem + Mem0 v3 + Zep + Letta + LangMem on the same question set. Results published in a new `benchmarks/results/2026-05-*/` run set and summarised in the README.

**Test plan.** The benchmarks themselves; plus a regression test that locks each adapter's expected output shape.

**Effort.** **M** (~2 weeks — adapters already exist for 4 of 5 systems; DMR and BEAM require dataset fetchers).

**Risk / cost.** If NeuroMem loses a benchmark, publish honestly and treat the loss as a gap-analysis input for H2/H3. Do not suppress results.

---

## H2 — Differentiators (1-3 months)

H2 totals: 10 items, ~14 engineer-weeks. Order (revised): **D1 → D3 → D7 → D6 → D2 → D4 → D9 → D5 → D8 → D10**. D2 depends on D3 (LLM arbitration); D2 is also extended to subsume Anant's Memory Dreams task list.

### H2-D1 — Personalized PageRank on entity graph
**North-star score.** Bar-2 yes — closes the v0.3.2 README's "honest open item" on LongMemEval multi-session. Bar-1 no direct.
**Unchanged from v1.** First item in H2 execution order.

### H2-D2 — Replay / CLS-slow consolidation scheduler (EXTENDED — Anant Memory Dreams parity)

**Problem (v2).** v1 proposed consolidation + update-in-place. Anant's Memory Dreams runs a richer task list: consolidation + confidence decay + **transitive inference** + **gap detection** + **follow-up-question generation** + **emotional-weight re-ranking**. Two of those (transitive inference, gap detection) are Generative-Agents-style reflection (Park et al. 2023). If NeuroMem's replay scheduler shipped the v1 task set only, Anant would beat us on "daily reflection richness" even with an inferior CLS schedule.

**Cognitive grounding.** CLS (McClelland 1995) + sharp-wave ripple replay (Buzsáki 1989, Wilson & McNaughton 1994) + Generative-Agents reflection (Park et al. 2023) + schema congruence (Tse et al. 2007) + Phelps amygdala modulation (2004).

**Prior art.** v1 H2-D2; Anant Memory Dreams (`reference_competitor_anant_neuralai.md`); Park et al. *Generative Agents* (arXiv 2304.03442).

**Proposed API.** v1's API plus new stages:
```yaml
brain:
  replay:
    enabled: true
    idle_threshold_minutes: 15
    interleave_ratio: 0.3
    update_existing_semantic: true
    min_sequence_length: 3
    schema_congruence_gate: true
    # NEW stages (Anant parity)
    transitive_inference: true
    gap_detection: true
    followup_question_generation: true
    emotional_weight_rerank: true
    followup_question_queue_path: ~/.neuromem/followup_questions.jsonl
```

**Data-model delta.** Same as v1; plus a per-user `FollowUpQuestion` record (question text, triggering-memory-ids, generated-at, delivered-flag). Semantic items gain `metadata["inferred_from_replay": bool]` for items created by transitive inference (separate from normal consolidation).

**LangGraph integration.** `NeuroMemStore.aget_pending_questions(namespace)` surfaces follow-up questions to the LangGraph agent, which can interleave them into the conversation.

**Test plan.** v1 test plan plus:
- **Transitive inference.** Ingest `A → knows → B` and `B → knows → C`; after replay, assert `A → weakly_knows → C` edge exists with appropriate confidence.
- **Gap detection.** Ingest `Raj works at Acme`, never ingest Raj's role; after replay, assert a `FollowUpQuestion` is generated about Raj's role.
- **Emotional-weight rerank** (coupled with H1-R10 wiring).
- **Anant-parity benchmark.** Head-to-head conversational corpus where gap-detection matters: measure user engagement from follow-up questions.

**Effort.** **L** (~5-6 weeks, extends v1's 3-4w).

**Risk / cost.** LLM cost scales more steeply with the extra stages. Mitigations: each new stage is individually gated by a config flag; benchmarks decide which are on-by-default at v0.6.0 ship time.

### H2-D3 — Prediction-error-gated reconsolidation
**North-star score.** Bar-1 item 4 yes (reconsolidation). Bar-2 yes — directly improves LongMemEval's knowledge-update category.
**Unchanged from v1.**

### H2-D4 — `ContextBudgetPlanner`
**North-star score.** Bar-1 no (but enables D9 self-narrative). Bar-2 indirect.
**Unchanged from v1.**

### H2-D5 — Sample-top-K community summaries (GraphRAG)
**North-star score.** Bar-1 no. Bar-2 yes — enables QFS-shaped benchmark queries.
**Unchanged from v1.**

### H2-D6 — Mem0-parity migration doc + benchmark
**North-star score.** Bar-2 yes (positioning). Low effort, high narrative value.
**Unchanged from v1.**

### H2-D7 — Calibrated abstention at retrieval boundary (PROMOTED from v1 H3-B2)

**Problem.** NeuroMem retrieves top-k on every query even when no memory is actually relevant. Human memory *knows when it doesn't know* (feeling-of-knowing, tip-of-tongue) and returns an explicit "don't know" rather than a noisy top-k. Bar-1 item 10.

**Cognitive grounding.** Koriat (1993) feeling-of-knowing; Bjork & Bjork (1992) distinction between storage strength and retrieval strength.

**Prior art.** Self-RAG reflection-token `IsRel` (arXiv 2310.11511 §6.3 Phase 4 §16.3.3); CRAG retrieval-evaluator (arXiv 2401.15884).

**Proposed API.**
```python
@dataclass(frozen=True)
class RetrievalResult:
    items: list[MemoryItem]
    confidence: float                     # 0-1 aggregate retrieval confidence
    abstained: bool                       # True when confidence below threshold
    abstention_reason: str | None         # "no_high_conf_match" | "query_ambiguous" | None

def retrieve(
    self,
    query: str,
    task_type: str = "chat",
    k: int = 8,
    abstain_threshold: float = 0.4,       # new
) -> RetrievalResult: ...                 # CHANGED return type; v1 returned list[MemoryItem]
```

**Data-model delta.** `RetrievalResult` wraps the current `list[MemoryItem]` return. Backward-compat via `__iter__` that yields items — existing callers unchanged unless they want `.abstained` / `.confidence`.

**LangGraph integration.** `NeuroMemStore.asearch` surfaces `abstained` in `SearchItem.score = 0.0` with metadata marker.

**Test plan.**
- Unit: query that matches nothing returns `abstained=True`.
- Benchmark: on a held-out set where the correct answer is "not in memory," assert abstention ≥ 80%.
- Regression: existing benchmarks must not trigger abstention spuriously (threshold calibrated).

**Effort.** **S-M** (~1-2 weeks).

**Risk / cost.** Over-abstention hurts benchmarks more than under-abstention. Mitigations: conservative threshold default; ablation sweep.

### H2-D8 — Cross-script coreference (EXTENDS H1-R6, from Anant analysis)

**Problem.** H1-R6 ships tokenizer injection. Cross-script coreference is a separate problem: `पापा दिल्ली में हैं` (Hindi) and "my father is retired" (English) should resolve to the *same* entity. NeuroMem's current `extract_entities` is English-only; even with `tokenizer_fn` injection, coreference across scripts requires LLM-based or multilingual-NER logic.

**Cognitive grounding.** Engineering / fairness.

**Prior art.** Anant cross-script merging (public claim, mechanism not disclosed); spaCy multi-language; multilingual E5 / LaBSE embeddings as coref substrate.

**Proposed API.**
```python
# neuromem/core/coref.py  NEW
class CorefResolver(Protocol):
    def resolve(self, entity: str, existing: list[str]) -> str | None:
        """Return canonical entity ID if ``entity`` matches an existing one, else None."""

class ExactMatchResolver(CorefResolver): ...           # default
class MultilingualEmbeddingResolver(CorefResolver): ...  # opt-in via neuromem-sdk[multilang]
```

**Data-model delta.** `_entity_index` keys become canonical IDs, not raw strings. Existing deployments migrate via a one-time pass where each raw-string key stays its own canonical (no new merges).

**LangGraph integration.** Transparent.

**Test plan.**
- Synthetic Hinglish corpus: 20 conversations with cross-script mentions; assert ≥ 90% coref accuracy with `MultilingualEmbeddingResolver`.
- Regression on English-only benchmarks.

**Effort.** **M** (~2 weeks; extends H1-R6's tokenizer work by ~1w additional).

**Risk / cost.** Over-merging (false positives) merges distinct entities and corrupts the graph. Mitigations: high cosine threshold; LLM arbitration on marginal cases.

### H2-D9 — Self-narrative generation extending `ContextManager` L0 (NEW, Bar 1 item 9)

**Problem.** NeuroMem's L0 `ContextManager` identity field is currently static — `set_identity("Senior Python dev at Acme")`. Humans maintain a *dynamic autobiographical narrative* — a coherent self-story that updates as life unfolds. No memory system in the survey ships this. Bar-1 item 9.

**Cognitive grounding.** McAdams (2001) *Review of General Psychology* 5(2):100-122 on autobiographical narrative identity; Baddeley (2000) episodic buffer as the integration locus.

**Prior art.** Generative-Agents character reflections (arXiv 2304.03442); no AI-memory SDK ships this.

**Proposed API.**
```python
# neuromem/core/self_narrative.py  NEW
class SelfNarrativeBuilder:
    def rebuild(self, max_tokens: int = 200) -> str: ...
    def get_current(self) -> str: ...

class ContextManager:
    # UPDATED — L0 becomes auto-generated by SelfNarrativeBuilder unless set_identity() is called explicitly
    ...
```

Triggered on the same schedule as H2-D2 replay — at the end of each replay pass, if significant new content was consolidated, the self-narrative is regenerated.

**Data-model delta.** Per-user `self_narrative` record with `(text, generated_at, sources: list[memory_id])`.

**LangGraph integration.** `NeuroMemStore.aget_self_narrative(namespace)` surfaces the current narrative.

**Test plan.**
- Ingest ~100 memories spanning 3 life themes (work, family, health); after replay, assert `self_narrative` captures all three themes in ≤ 200 tokens.
- **Continuity test:** ingest a new job change; after replay, assert the narrative updated the work theme without losing family/health.

**Effort.** **M** (~2-3 weeks).

**Risk / cost.** LLM generation cost per replay. Mitigations: only regenerate when new-content delta exceeds threshold; default off for v0.5.0, on for v0.6.0.

### H2-D10 — Publish `LongFacts` benchmark (NEW, Bar 2)

**Problem.** Current benchmarks (MemBench / LongMemEval / ConvoMem / LoCoMo / DMR / BEAM) don't stress-test the specific failure mode that differentiates temporal-versioning systems from immediate-add systems: **multi-session consistency under contradiction**. Mem0 v3 ADD-only fails this by design (#4956). Anant's temporal versioning passes. NeuroMem's conflict resolver + deprecation passes. Publishing this benchmark *defines the competition on terms NeuroMem wins.*

**Cognitive grounding.** Reconsolidation + CLS (Bar-1 items 4 and 6).

**Prior art.** MemBench / LongMemEval question formats; the Mem0 #4956 reproduction scenario.

**Proposed API.** Dataset + runner:
```
benchmarks/
  datasets/longfacts/
    sessions/                       # simulated 30-day sessions with contradictions
    questions/                      # "where does X work as of 2026-04-15?"
    ground_truth/                   # current-true fact, not most-recent mention
  runners/longfacts_runner.py
  README.md                         # protocol, metrics, leaderboard instructions
```

Metric: Recall@5 of the *current-true* fact as of the query date, scored by an LLM judge with a strict ground-truth match.

**Test plan.** The benchmark itself. NeuroMem must publish numbers for all 5 competitors on this dataset alongside its own.

**Effort.** **M-L** (~3-4 weeks — dataset construction is the dominant cost).

**Risk / cost.** If a competitor passes LongFacts as well as NeuroMem, we haven't invented a winning lane. Mitigations: design the dataset to include cases only a bi-temporal + conflict-resolved system passes (e.g., "what did X believe in March given they updated in April?"). Publish the dataset even if NeuroMem doesn't top it — credibility builds the community.

---

## H3 — Research bets (3-6 months)

### H3-B1 — RAPTOR collapsed-tree on `VerbatimStore`
**Unchanged from v1.**

### H3-B2 — (MERGED into H2-D7 above)
v1's "Should-I-retrieve-at-all gate" is subsumed by H2-D7 calibrated abstention.

### H3-B3 — Multimodal `observe_multimodal` for real
**Unchanged from v1.**

### H3-B4 — RIF / interference-theory forgetting research spike
**North-star score.** Bar-1 item 3. Publishable negative result acceptable.
**Unchanged from v1.**

### H3-B5 — Stable 1.0 release with deprecation policy
**Unchanged from v1.**

### H3-B6 — Prospective-memory API (NEW, Bar 1 item 8)

**Problem.** No AI-memory SDK ships "remind me about X when Y happens." Human memory handles this natively — prospective memory (Einstein & McDaniel 1990). Bar-1 item 8.

**Cognitive grounding.** Einstein & McDaniel (1990) *JEP:LMC* 16(4):717-726 on event-based vs time-based prospective memory.

**Prior art.** Calendar reminders are time-based prospective memory, poorly integrated with conversational context. No SDK ships event-based (triggered by conversational content) prospective memory.

**Proposed API.**
```python
class NeuroMem:
    def remind(
        self,
        trigger: str,                      # natural-language trigger description, e.g. "when I mention hospital"
        content: str,                      # what to surface
        expires: datetime | None = None,
    ) -> str:                              # reminder_id
        ...

    def get_pending_reminders(
        self,
        new_content: str | None = None,    # check whether new observed content triggers any reminders
    ) -> list[Reminder]: ...
```

Implementation: reminders are stored as `MemoryItem` with `memory_type=PROSPECTIVE` (new enum value — pair with H1-R12 belief-state upgrade); trigger text is embedded; on every `observe()`, the new content embedding is compared to pending-reminder trigger embeddings; matches above threshold surface via `get_pending_reminders`.

**Data-model delta.** New `MemoryType.PROSPECTIVE`. New backend semantics: `Reminder` with `(trigger_embedding, content, created_at, expires, triggered_count)`.

**LangGraph integration.** `NeuroMemStore.areminders_for(new_content)` surfaces matches.

**Test plan.** Unit: set reminder on "when I mention hospital"; call `get_pending_reminders("my father is in the hospital")`; assert reminder fires. Benchmark: H3-B9 ProspectiveRecall.

**Effort.** **L** (~4 weeks).

**Risk / cost.** Trigger matching quality varies with embedding model. Mitigations: opt-in; low-threshold default + explicit user confirmation UI.

### H3-B7 — Publish `SlowConsolidationBench` (NEW, Bar 2)

**Problem.** Post-offline-period schema extraction — insert 1000 episodic memories over a simulated week, run the system's consolidation pass, ask questions requiring *schema-level* (not verbatim) answers. Every immediate-consolidation system degrades (they already over-consolidated during ingestion); CLS-slow wins.

**Cognitive grounding.** CLS + schema theory (Bar-1 items 6 and 7).

**Prior art.** None. This is a novel benchmark.

**Proposed API.** Dataset + runner parallel to H2-D10.

**Effort.** **M-L** (~3-4 weeks).

**Risk / cost.** Same as H2-D10 — if the bench doesn't discriminate, we haven't invented a winning lane.

### H3-B8 — Publish `EmotionalRecall` benchmark (NEW, Bar 2 / Bar 1 item 5)

**Problem.** Retrieval accuracy on emotionally-salient events. Conversational corpus with emotion labels; query tests retrieval of the emotionally-salient memory over recency-based competitors. Needs H1-R10 emotional-weight wiring.

**Cognitive grounding.** Phelps (2004), McGaugh (2000).

**Prior art.** LoCoMo has some emotional content but doesn't score on emotional salience per se.

**Proposed API.** Dataset + runner.

**Effort.** **M** (~2-3 weeks).

**Risk / cost.** Standard.

### H3-B9 — Publish `ProspectiveRecall` benchmark (NEW, Bar 2 / Bar 1 item 8)

**Problem.** "Remind me when Y happens" evaluation. Pairs with H3-B6 prospective-memory API.

**Cognitive grounding.** Einstein & McDaniel (1990).

**Prior art.** None in AI-memory evaluation.

**Proposed API.** Dataset + runner.

**Effort.** **M** (~2-3 weeks).

**Risk / cost.** Standard.

---

## Cross-horizon dependency graph (v2)

```
H1-R1 BaseStore ───────────────► H2-D4 ContextBudgetPlanner ──► H2-D9 Self-narrative
H1-R3 Persistent graph ────────► H2-D1 PPR
                                └► H2-D5 Community summaries
                                └► H2-D2 Replay scheduler (needs graph backend for transitive inference)
H1-R6 Tokenizer injection ─────► H2-D8 Cross-script coref
H1-R5 forget() sweep ──────────► H2-D3 Reconsolidation
H1-R9 bug debts ───────────────► H2-D2 Replay (days_threshold fix prerequisite)
H1-R10 Emotional-weight wire ──► H2-D2 (emotional_weight_rerank stage)
                                └► H3-B8 EmotionalRecall benchmark
H1-R12 Belief-state upgrade ───► H2-D7 Calibrated abstention (uses belief_state in confidence calc)
                                └► H3-B6 Prospective memory (uses MemoryType.PROSPECTIVE)
H1-R13 Harness benching ───────► v0.5.0 competitive-position narrative
H2-D3 Reconsolidation ─────────► H2-D2 Replay (D2's update-in-place uses D3's LLM arbitration)
H2-D1 PPR + H2-D5 communities ─► H3-B1 RAPTOR
H2-D2 Replay extended ─────────► H3-B7 SlowConsolidationBench
H3-B6 Prospective memory ──────► H3-B9 ProspectiveRecall benchmark
```

Critical path: **H1-R3 → H2-D1 → H2-D5 → H3-B1** (graph → PPR → communities → RAPTOR) remains from v1. New: **H1-R10 → H2-D2 extensions → H3-B7 SlowConsolidationBench** (emotional wiring → replay completeness → bench NeuroMem wins).

---

## Release mapping (revised)

- **v0.4.0** (~4-5 weeks out): all H1 items except R3 and R13 if they slip. This is 11 items including 4 new ones (R10 emotional wiring, R11 injection tests, R12 belief-state, R8 air-gapped extension). Notable: R10 is a free-win Bar-1 item — ship first.
- **v0.4.1** (if R3 / R13 slip): persistent-graph backend + harness benching published.
- **v0.5.0** (~8-10 weeks): H2-D1 PPR + H2-D3 reconsolidation + H2-D6 Mem0-doc + H2-D7 calibrated abstention. Plus H2-D10 LongFacts benchmark published.
- **v0.6.0** (~14-16 weeks): H2-D2 extended replay scheduler + H2-D4 context planner + H2-D9 self-narrative + H2-D5 community summaries + H2-D8 cross-script coref. This is the version where "NeuroMem ships CLS-slow consolidation with Anant-parity daily reflection" becomes the public claim.
- **v1.0.0** (~18-22 weeks): H3-B5 stability release once v0.6.0 benchmarks hold.
- **v1.x**: H3-B1 RAPTOR, H3-B3 multimodal real, H3-B4 RIF spike, H3-B6 prospective memory, H3-B7/B8/B9 benchmark publications.

---

## What v2 does NOT include

All exclusions from v1 remain: ColBERT reranker, true Hopfield CA3, procedural-as-implicit-skill, Titans surprise-triggered write, full async refactor of core.

New v2 exclusions from the north-star goal analysis:
- **Do not chase the "biggest context window" race.** RULER (Phase 4 §16.3.5) shows the 2M-context claims are marketing. Bar 1 item 1 is already hit via retrieval + persistence.
- **Do not ship a consumer chat product.** Anant is in that lane. NeuroMem stays a developer SDK. Cognitive ambitions don't require product-market-fit in chat.
- **Do not ship a visual-UI memory inspector.** That's tooling, not the core algorithm. `explain(memory_id)` + `get_graph()` JSON export cover the need; visual tools are downstream community work.

---

## Exit criterion for Phase 6 v2

Every item satisfies the v1 criteria PLUS:
- **North-star decision filter §0.2 answered.** Bar-1 and/or Bar-2 contribution stated.
- **Competitor-benching commitment §0.4.** On every new item with retrieval implications, confirm it lands in the head-to-head benchmark matrix within the release that ships it.

If any item drifts from these seven criteria during implementation, revisit before merging — do not silently scope-creep.
