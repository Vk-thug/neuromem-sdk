# Phase 2 — Cognitive & Neuroscience Grounding

*Goal: map every mechanism NeuroMem ships (or could ship) onto a cited memory-science mechanism. The aim is not neuroscientific purity — it is to ensure every Phase-6 roadmap item has a cognitive theory behind it, not just "because Mem0 does it."*

*Accessed 2026-04-24. Citations include year + canonical paper; where the field has a 2020s update that changes the engineering implication, the update is named.*

---

## 0. Method and scope

- **One mechanism per subsection.** Each mechanism is named with its foundational citation, a one-paragraph explanation grounded in the cited work, and a strict mapping to a file/symbol in NeuroMem.
- **Mappings are graded** — ✅ implemented, ◐ partial (named but mechanism doesn't match theory), ❌ absent.
- **Engineering implications** are written as constraints on Phase 6 proposals, not as proposals themselves. Phase 6 is where mechanisms become line-item roadmap entries.
- **Out of scope:** sensorimotor / perceptual grounding, embodied cognition, developmental trajectory. NeuroMem is a text/multimodal agent memory SDK, not a cognitive architecture.

---

## 1. Tulving's taxonomy (1972, 1985) — episodic × semantic × procedural

**Citation.** Tulving, E. (1972). "Episodic and semantic memory." In *Organization of memory*. Tulving, E. (1985). "Memory and consciousness." *Canadian Psychology*, 26(1):1–12 — introduces autonoetic/noetic/anoetic consciousness.

**Claim.** Long-term memory partitions into **declarative** (explicit, language-reportable) and **non-declarative** (implicit). Declarative splits into **episodic** (autonoetic — accompanied by mental time travel to the encoding context) and **semantic** (noetic — factual knowledge divorced from source episode). Non-declarative includes **procedural** (skills), **priming** (exposure-based facilitation), and simple conditioning.

**Critical gap most SDKs gloss over.** Tulving's taxonomy treats procedural as *non-declarative*. Every AI-memory SDK (NeuroMem included) implements "procedural memory" as a *declarative* store of preferences expressed in natural language ("User prefers dark mode"). That is not Tulvingian procedural — it's really *declarative semantic knowledge about user preferences*. The naming is convenient but theoretically loose. Phase 5 should flag this; Phase 6 can leave the naming alone (it has user familiarity) but shouldn't build further features on the premise that NeuroMem's "procedural" memory captures implicit know-how.

**Mapping.**
| Tulving layer | NeuroMem component | Grade |
| --- | --- | --- |
| Episodic (autonoetic) | `EpisodicMemory` + `created_at` + `last_accessed` metadata; `get_memories_by_date` / `get_memories_in_range` | ✅ |
| Semantic (noetic) | `SemanticMemory`; `Consolidator` fact-extraction | ✅ |
| Procedural (Tulvingian) | — | ❌ (NeuroMem's `ProceduralMemory` is semantic-about-preferences) |
| Priming | — | ❌ |

**Engineering implication for Phase 6.** A true *procedural* memory layer would be something like cached tool-call patterns or cached reasoning traces that the agent re-applies without re-deriving — closer in spirit to Titans' test-time memory (§8 of Phase 1) or Letta's core-memory-as-prompt (§1). This is a research bet, not table stakes. For table stakes, keep NeuroMem's current "procedural = preferences" meaning and document the semantic drift explicitly.

---

## 2. Complementary Learning Systems (CLS) — fast × slow

**Citations.**
- McClelland, J.L., McNaughton, B.L., O'Reilly, R.C. (1995). "Why there are complementary learning systems in the hippocampus and neocortex: insights from the successes and failures of connectionist models of learning and memory." *Psychological Review*, 102(3):419–457.
- Kumaran, D., Hassabis, D., McClelland, J.L. (2016). "What learning systems do intelligent agents need? Complementary learning systems theory updated." *Trends in Cognitive Sciences*, 20(7):512–534 — the 2010s update for deep-RL.

**Claim.** Memory requires **two systems with different time constants** because fast learning with distributed representations causes *catastrophic interference* — new patterns overwrite old. CLS partitions: **hippocampus** learns fast using sparse, pattern-separated representations of individual episodes; **neocortex** learns slowly by interleaving many episodes into overlapping, generalising representations. **Replay** during sleep / offline periods transfers episodic patterns from hippocampus to neocortex gradually, allowing integration without interference.

**Why this matters for NeuroMem.** The central CLS prediction — *consolidation is slow and interleaved, not immediate* — is violated by every AI-memory SDK surveyed in Phase 1 including NeuroMem itself. NeuroMem's `Consolidator.consolidate()` fires every `consolidation_interval=10` turns with `days_threshold=0`. LLM fact-extraction is run on each batch of episodic items *without* interleaving with existing semantic items, *without* spaced retrieval, *without* a separate offline pass.

**Mapping.**
| CLS element | NeuroMem component | Grade |
| --- | --- | --- |
| Fast, sparse, episodic writes | `EpisodicMemory` + `VerbatimStore` + `brain/hippocampus/pattern_separation.py` | ✅ |
| Slow, distributed semantic | `SemanticMemory` backend | ◐ (the store is there; the *slow* part is not — consolidation is immediate) |
| Replay (offline hippocampus → neocortex) | — | ❌ (`brain.hippocampus.ripple_interval_minutes` in config, no consumer) |
| Interleaved learning to avoid interference | — | ❌ (consolidation considers only new episodic items, not existing semantic) |
| Catastrophic interference argument | — | ❌ (no test) |

**Engineering implication for Phase 6.** A **Replay/ConsolidationScheduler** is the single highest-leverage cognitive-science-grounded addition: a scheduled job (cron / Inngest / async worker) that (a) samples old semantic memories plus recent episodic items, (b) runs fact-extraction *interleaved over the mix*, (c) respects a configurable cadence (hours/days), and (d) updates existing semantic memories rather than always producing new ones. This is the *only* mechanism in Phase 1's survey that nobody else ships — meaning it's a possible differentiator, not just catch-up.

---

## 3. Hippocampal indexing theory — index ≠ content

**Citations.**
- Teyler, T.J., DiScenna, P. (1986). "The hippocampal memory indexing theory." *Behavioral Neuroscience*, 100(2):147–154.
- Teyler, T.J., Rudy, J.W. (2007). "The hippocampal indexing theory and episodic memory: updating the index." *Hippocampus*, 17(12):1158–1169.

**Claim.** The hippocampus stores *indices* — sparse pointers — to neocortical patterns, not the content itself. Recall is the index triggering re-activation of the distributed neocortical trace. Consolidation is the gradual shift from index-dependent to index-independent retrieval as the neocortical pattern strengthens.

**Engineering analogue.** This is *exactly* the vector-DB-plus-content-store split most RAG systems use, whether or not they know it. The vector is the "index"; the content blob is the "cortical pattern." The distinction that classic RAG misses is the *index reorganisation* over time — the hippocampal index is updated, strengthened, or dropped based on whether the cortical pattern has "taken."

**Mapping.**
| Indexing-theory element | NeuroMem component | Grade |
| --- | --- | --- |
| Sparse hippocampal index | `brain.hippocampus.pattern_separation.py` `SparseCode` | ✅ |
| Distributed cortical content | Backend-stored `MemoryItem.content` + embedding | ✅ |
| Index update based on cortical integration | — | ❌ (sparse codes are write-once; no update rule ties sparsity back to semantic consolidation) |

**Engineering implication for Phase 6.** The sparse code that `PatternSeparator.separate` produces is stored in `item.metadata["sparse_code"]` and then never read by any downstream component. This is a dangling signal. Two options: (a) use sparse codes as a retrieval-time similarity channel (sparse overlap as an extra term in the blend), or (b) remove sparse-code generation entirely until it's wired up. Phase 6 should pick one; the current state is worst-of-both (cost without benefit).

---

## 4. Pattern separation (DG) and pattern completion (CA3)

**Citations.**
- Yassa, M.A., Stark, C.E.L. (2011). "Pattern separation in the hippocampus." *Trends in Neurosciences*, 34(10):515–525.
- McClelland, J.L., Goddard, N.H. (1996). "Considerations arising from a complementary learning systems perspective on hippocampus and neocortex." *Hippocampus*, 6(6):654–665.
- Hopfield, J.J. (1982). "Neural networks and physical systems with emergent collective computational abilities." *PNAS*, 79(8):2554–2558 — the classical attractor-network basis for pattern completion.

**Claim.** The dentate gyrus (DG) performs **pattern separation**: it produces maximally decorrelated sparse codes of overlapping inputs so that similar-but-distinct episodes do not interfere. CA3, a recurrent network, performs **pattern completion**: it converges partial cues to the nearest stored attractor, enabling retrieval from fragment.

**Mapping.**
| DG/CA3 element | NeuroMem component | Grade |
| --- | --- | --- |
| DG expansion + k-WTA sparsification | `PatternSeparator` — sparse Achlioptas RP, ReLU, k-WTA at 5% sparsity | ✅ (this is a sound, biologically-plausible implementation) |
| Per-user index isolation | `PatternSeparator` seed = `md5(user_id)` | ✅ |
| CA3 recurrent attractor dynamics | `brain/hippocampus/pattern_completion.py` | ◐ (file re-weights candidates; it is *not* a recurrent attractor net — see Phase 0 §7) |
| Pattern completion from partial cue | — | ❌ (currently the bi-encoder + rerank pipeline handles partial-cue retrieval; CA3-style attractor dynamics are not used) |

**Engineering implication for Phase 6.** A true Hopfield/attractor implementation is research-grade and probably not worth the cost given that cross-encoder reranking + HyDE already handle partial-cue retrieval adequately. **The honest position is to rename `PatternCompleter` to something less theoretically-loaded** (e.g., `AttractorReranker`) rather than pretend to implement CA3 dynamics. Truth-in-naming has Phase-5 cost; silent drift has Phase-6 cost because every roadmap item referencing "pattern completion" then carries theoretical baggage it can't cash.

---

## 5. Systems consolidation & replay

**Citations.**
- Buzsáki, G. (1989). "Two-stage model of memory trace formation: a role for 'noisy' brain states." *Neuroscience*, 31(3):551–570.
- Wilson, M.A., McNaughton, B.L. (1994). "Reactivation of hippocampal ensembles during sleep." *Science*, 265:676–679.
- Ji, D., Wilson, M.A. (2007). "Coordinated memory replay in visual cortex and hippocampus during sleep." *Nature Neuroscience*, 10(1):100–107.
- Liu, Y., Dolan, R.J., Kurth-Nelson, Z., Behrens, T.E.J. (2019). "Human replay spontaneously reorganizes experience." *Cell*, 178(3):640–652 — confirms replay in humans via MEG.

**Claim.** During **sharp-wave ripples** (50–100 ms, ~150–200 Hz oscillations in CA3/CA1 during sleep or quiet wakefulness), sequences of place cells reactivate in compressed time. Replay is temporally coordinated between hippocampus and neocortex; the same sequences are replayed in both, supporting the two-stage CLS transfer.

**Mapping.**
| Replay element | NeuroMem component | Grade |
| --- | --- | --- |
| Trigger (offline / low-activity period) | — | ❌ (no trigger defined) |
| Sequence reactivation (compressed replay) | — | ❌ |
| Coordinated hippocampus/neocortex update | — | ❌ |
| Config knobs for replay cadence | `brain.hippocampus.ripple_interval_minutes`, `ripple_batch_size` | ◐ (declared, unconsumed) |

**Engineering implication for Phase 6.** This is the concrete, empirically-grounded version of §2's "Replay/ConsolidationScheduler." A replay job should:
1. Trigger during low-activity windows (e.g., no `observe` calls in N minutes, or cron-scheduled at low traffic hours).
2. Sample a *sequence* of recent episodic memories (not one at a time) — mimicking compressed replay.
3. Re-run consolidation over the sequence with existing semantic items interleaved.
4. Update, not just add.

This is the highest-priority Phase-6 H2 item because it is (a) grounded in primary neuroscience, (b) absent from every Phase-1 competitor, (c) implementable with existing infrastructure (`MaintenanceWorker` / Inngest `cron`), and (d) config stubs already in the codebase.

---

## 6. Forgetting: Ebbinghaus decay + retrieval-induced forgetting + interference

**Citations.**
- Ebbinghaus, H. (1885). *Über das Gedächtnis: Untersuchungen zur experimentellen Psychologie*. Original exponential retention `b = 100k/((log t)^c + k)` with `c=1.25`, `k=1.84`. Modern simplified `R = e^(−t/S)` widely used.
- Murre, J.M.J., Dros, J. (2015). "Replication and analysis of Ebbinghaus' forgetting curve." *PLoS ONE*, 10(7):e0120644.
- Anderson, M.C., Bjork, R.A., Bjork, E.L. (1994). "Remembering can cause forgetting: retrieval dynamics in long-term memory." *JEP:LMC*, 20(5):1063–1087.
- Underwood, B.J. (1957). "Interference and forgetting." *Psychological Review*, 64(1):49–60 — interference theory (proactive and retroactive).

**Claim.** Three distinct forgetting mechanisms operate:
1. **Decay** — passive weakening over time in the absence of rehearsal (Ebbinghaus curve).
2. **Retrieval-induced forgetting (RIF)** — actively retrieving item A *inhibits* related items B, C from the same category. This is *selective inhibition*, not symmetric decay.
3. **Interference** — proactive (old blocks new) and retroactive (new blocks old).

**Engineering importance.** (1) is what NeuroMem implements and what every memory SDK implements. (2) and (3) are absent from the field. RIF in particular makes a very specific empirical prediction: *retrieving item X in category Y should temporarily reduce retrievability of other Y-items*. This is the opposite of what NeuroMem currently does — `DecayEngine.reinforce` bumps the accessed item, and `apply_hybrid_boosts` promotes related items via keyword overlap. No mechanism *suppresses* neighbours of a retrieved item.

**Mapping.**
| Forgetting element | NeuroMem component | Grade |
| --- | --- | --- |
| Ebbinghaus-style exponential decay | `DecayEngine.calculate_decay` — `e^(−adjusted_decay_rate·days)`, adjusted by reinforcement and salience | ✅ |
| Flashbulb exception (arousal override) | `DecayEngine` + `amygdala.EmotionalTagger` `metadata["flashbulb"]` | ✅ |
| Retrieval-induced forgetting | — | ❌ |
| Interference theory (proactive / retroactive) | — | ❌ |
| Forgetting as a first-class API (Larimar-style) | `NeuroMem.forget(memory_id)` hard-deletes; no selective-forget guarantees | ◐ |

**Engineering implication for Phase 6.** RIF and selective forgetting are H3 research bets — they require category/cluster definitions and the selectivity payoff is unclear on current benchmarks. The more actionable gap is **privacy-forgetting**: Larimar-style "forget with guarantees" (§9 Phase 1) is a table-stakes feature for enterprise deployments that NeuroMem doesn't have. A `forget(memory_id, scope="all")` that sweeps verbatim chunks, episodic, semantic, and the graph's `_entity_index` simultaneously is H1.

---

## 7. Reconsolidation — retrieval makes memories labile

**Citations.**
- Nader, K., Schafe, G.E., LeDoux, J.E. (2000). "Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval." *Nature*, 406(6797):722–726. **The landmark paper — widely replicated.**
- Lee, J.L.C. (2009). "Reconsolidation: maintaining memory relevance." *Trends in Neurosciences*, 32(8):413–420 — synthesises the *updating* view.
- Sevenster, D., Beckers, T., Kindt, M. (2013). "Prediction error governs pharmacologically induced amnesia for learned fear." *Science*, 339(6121):830–833 — prediction-error as trigger.

**Claim.** A retrieved memory becomes *labile* for a window (hours in rodents), during which protein synthesis is required to re-stabilise it. This means retrieval is not read-only: **retrieved memories can be updated, augmented, or weakened.** The mechanism is gated by **prediction error** — if retrieval produces surprise (the re-encountered context doesn't match the stored trace), reconsolidation engages; if there's no error, the memory restabilises unchanged.

**Mapping.**
| Reconsolidation element | NeuroMem component | Grade |
| --- | --- | --- |
| Retrieval marks memory as update-eligible | `ReconsolidationPolicy.should_reconsolidate` — requires `retrieval_count ≥ 3` and new context `> 1.5×` content length | ◐ (has a heuristic; not prediction-error-driven) |
| Labile-window update | `ReconsolidationPolicy.merge_context` — naïve string append | ◐ |
| Prediction-error gate | — | ❌ (no comparison of retrieved content vs. actual observed content) |
| Restabilisation (no-op when unchanged) | Implicit — no merge if no change | ✅ |

**Engineering implication for Phase 6.** NeuroMem already names `ReconsolidationPolicy` — the cognitive grounding is claimed. The *implementation* is weak: the trigger is a heuristic, and the merge is string concatenation. A prediction-error-gated reconsolidation would compare retrieved content to the new observation via embedding cosine; a mismatch above a threshold triggers an LLM-arbitrated update (Mem0-paper-style add/update/delete). This is H2: cognitive grounding is real, prior art exists (Mem0's update/delete decisions), and the current implementation is a straw-man.

---

## 8. Working memory — Baddeley + Cowan

**Citations.**
- Baddeley, A.D., Hitch, G. (1974). "Working memory." In *The Psychology of Learning and Motivation*, 8:47–89. Introduces phonological loop, visuospatial sketchpad, central executive.
- Baddeley, A.D. (2000). "The episodic buffer: a new component of working memory?" *Trends in Cognitive Sciences*, 4(11):417–423 — the fourth component.
- Cowan, N. (2001). "The magical number 4 in short-term memory: a reconsideration of mental storage capacity." *Behavioral and Brain Sciences*, 24(1):87–114.
- Miller, G.A. (1956). "The magical number seven, plus or minus two." *Psychological Review*, 63(2):81–97 — superseded, cited for context.

**Claim.** Working memory is not a single store but (a) a *central executive* that allocates attention, (b) modality-specific buffers (phonological, visuospatial), and (c) an *episodic buffer* that integrates these with long-term memory. Capacity is roughly **four chunks** under the focus of attention (Cowan), not seven (Miller). Working memory is *long-term memory in the focus of attention*, not a separate store.

**Mapping.**
| Working-memory element | NeuroMem component | Grade |
| --- | --- | --- |
| Cowan-4 capacity | `brain.prefrontal.working_memory.WorkingMemoryBuffer` capacity=4 | ✅ |
| Attention-gated write (score comparison) | `WorkingMemoryBuffer.gate_write` — replaces min if new score > min | ✅ |
| Persistence across sessions | `BrainStateStore` JSON sidecar | ✅ |
| Modality-specific buffers | — | ❌ (multimodal encoders exist in `multimodal/`, but no modality-specific WM) |
| Central executive (attention allocator) | — | ❌ |
| Episodic buffer (integrates WM with LTM) | — | ◐ (`SessionMemory` + `WorkingMemoryBuffer` overlap partially but aren't integrated) |
| Working memory as peer memory layer (surfaced to the agent) | — | ❌ (`MemoryType.WORKING` exists but no persistence layer writes it) |

**Engineering implication for Phase 6.** Three distinct items:
1. **Unify `SessionMemory` and `WorkingMemoryBuffer`.** Currently they're both "working memory" but unlinked. H1 consolidation.
2. **Surface working memory as a first-class context-assembly input.** Right now `get_working_memory()` is a spectator API; the retrieved WM items don't influence `RetrievalEngine.score`. H1 — add WM membership as a score component.
3. **Episodic buffer.** A mechanism that binds retrieved LTM items with current WM and session turn — Baddeley (2000) explicitly describes this as the missing glue. In NeuroMem terms: a context-assembler that packages WM + top-k LTM + current session for the LLM. H2 — overlaps with Phase 4 context engineering.

---

## 9. Schema theory — gist extraction and integration

**Citations.**
- Bartlett, F.C. (1932). *Remembering: a study in experimental and social psychology*. Cambridge University Press — "War of the Ghosts," schema-driven reconstruction.
- Piaget, J. (1952). *The origins of intelligence in children* — assimilation vs. accommodation.
- Tse, D., Langston, R.F., Kakeyama, M., Bethus, I., Spooner, P.A., Wood, E.R., Witter, M.P., Morris, R.G.M. (2007). "Schemas and memory consolidation." *Science*, 316(5821):76–82 — shows rapid consolidation of schema-congruent facts vs. slow consolidation of schema-incongruent ones.
- Ghosh, V.E., Gilboa, A. (2014). "What is a memory schema? A historical perspective on current neuroscience literature." *Neuropsychologia*, 53:104–114.

**Claim.** A **schema** is a structured cluster of related knowledge. New information *congruent with an existing schema* consolidates faster (Tse et al. 2007). New information that is *incongruent* either accommodates (schema updates) or produces a separate schema. Schemas are cortical, not hippocampal — they are the *generalised* end-state of CLS consolidation.

**Mapping.**
| Schema-theory element | NeuroMem component | Grade |
| --- | --- | --- |
| Schema = cluster of related memories | `MemoryGraph.get_clusters` (Union-Find) | ✅ (mechanism) |
| Schema congruence boosts consolidation speed | `brain.neocortex.SchemaIntegrator.compute_salience_boost` adds a boost if the embedding is close to running schema centroids | ✅ |
| Schema-congruent memories interleaved with schema during consolidation | — | ❌ (consolidation ignores existing semantic items) |
| Accommodation (schema update on incongruent info) | — | ❌ |
| Persistent schemas (not just session-local centroids) | `BrainStateStore` persists centroids | ✅ |

**Engineering implication for Phase 6.** The `SchemaIntegrator` is a more biologically faithful version of what HippoRAG does with PPR on entity graphs — both operationalise "integrate with what's already related." Two H2 items:
1. **Tie `SchemaIntegrator.schema_centroids` into `MemoryGraph.get_clusters`** so that schema identity is a *persisted graph community*, not a transient centroid.
2. **Use schema congruence as a consolidation gate** (Tse et al. prediction) — congruent episodic items consolidate sooner than incongruent ones. This is a direct prediction the field does not yet test.

---

## 10. Priming

**Citation.** Tulving, E., Schacter, D.L. (1990). "Priming and human memory systems." *Science*, 247(4940):301–306.

**Claim.** Prior exposure to a stimulus facilitates later processing of that stimulus or related stimuli, even in the absence of conscious recall. Priming is non-declarative.

**Mapping.**
| Priming | NeuroMem | Grade |
| --- | --- | --- |
| Exposure-based facilitation | — | ❌ |

**Engineering implication for Phase 6.** Not a near-term item. The closest practical analogue is "prefer cached embeddings for recently-observed queries," which is just a cache. Priming as a first-class mechanism is H3 research-bet territory.

---

## 11. Hierarchical Temporal Memory (HTM)

**Citations.**
- Hawkins, J., Ahmad, S., Cui, Y. (2017). "A theory of how columns in the neocortex enable learning the structure of the world." *Frontiers in Neural Circuits*, 11:81.
- Ahmad, S., Hawkins, J. (2016). "How do neurons operate on sparse distributed representations? A mathematical theory of sparsity, neurons and active dendrites." arXiv:1601.00720.

**Claim.** Neocortex uses **sparse distributed representations** (~2% active out of ~2048 units) for all computation. Sparsity makes representations robust to corruption, enables semantic-similarity-as-overlap, and supports continuous learning without catastrophic interference.

**Mapping.**
| HTM element | NeuroMem | Grade |
| --- | --- | --- |
| Sparse distributed representations | `SparseCode` from `PatternSeparator` | ✅ mechanism |
| Temporal memory (sequence learning) | — | ❌ |
| Spatial pooler (competitive SDR selection) | — | ◐ (`PatternSeparator` k-WTA approximates this step) |

**Engineering implication for Phase 6.** Per §3 above, the sparse codes are currently an unused signal. If we wire them in (§3 recommends this), HTM-style SDR overlap becomes a cheap third similarity channel alongside embedding cosine and BM25. Low-cost experiment on benchmarks. But only worth running *after* the sparse code is actually consumed somewhere — otherwise it's a zero-value write.

---

## 12. Emotional memory — amygdala modulation

**Citations.**
- Phelps, E.A. (2004). "Human emotion and memory: interactions of the amygdala and hippocampal complex." *Current Opinion in Neurobiology*, 14(2):198–202.
- Brown, R., Kulik, J. (1977). "Flashbulb memories." *Cognition*, 5(1):73–99 — original flashbulb concept.
- McGaugh, J.L. (2000). "Memory — a century of consolidation." *Science*, 287(5451):248–251.

**Claim.** The amygdala modulates hippocampal consolidation of emotionally-arousing events. High-arousal events produce **flashbulb memories** — exceptionally durable, detailed, but not infallible. Emotional salience acts as a *consolidation gain* rather than a separate store.

**Mapping.**
| Emotional-memory element | NeuroMem | Grade |
| --- | --- | --- |
| Arousal/valence tagging | `brain.amygdala.EmotionalTagger.tag()` | ✅ |
| Flashbulb exception (immune to decay) | `DecayEngine.calculate_decay` respects `metadata["flashbulb"]` | ✅ |
| Arousal-based salience adjustment | `EmotionalTagger.adjusted_salience` | ✅ |
| Cross-check: flashbulb accuracy decays over time even though subjective confidence stays high (Talarico & Rubin 2003) | — | ❌ |

**Engineering implication for Phase 6.** `EmotionalTagger` is the most faithfully implemented brain region in NeuroMem relative to the primary literature. No Phase-6 work needed here beyond a single correctness note (Talarico & Rubin): the *subjective vividness* of flashbulb memories does not predict accuracy. If NeuroMem ever surfaces flashbulb status to end-users, the UX should not imply "this memory is verified true" — only "this memory is durable."

---

## 13. Temporal-difference (TD) learning

**Citations.**
- Schultz, W., Dayan, P., Montague, P.R. (1997). "A neural substrate of prediction and reward." *Science*, 275(5306):1593–1599 — dopaminergic prediction-error signal.
- Sutton, R.S., Barto, A.G. (2018). *Reinforcement Learning: An Introduction*, 2nd ed. — textbook TD(0).

**Claim.** Dopaminergic neurons signal **reward prediction error** (actual − expected reward). Repeated updates shift value estimates toward true expected return. Basal ganglia are the neural substrate for action-value learning.

**Mapping.**
| TD element | NeuroMem | Grade |
| --- | --- | --- |
| Value per (state, action) | `brain.basal_ganglia.TDLearner` — value per (cluster_id, task_type) | ✅ |
| Learning rate α, discount γ | TDLearner(α=0.1, γ=0.9) | ✅ |
| Reward from user feedback | `NeuroMem.reinforce(memory_id, reward)` → `BrainSystem.reinforce` → `TDLearner.update` | ✅ |
| Bootstrapping (V(s') in the update) | — | ◐ (TD(0) is implemented but there's no "next state" concept in a memory retrieval context; the update is effectively Monte-Carlo-0) |

**Engineering implication for Phase 6.** TD learning only pays off when reward signals are routinely provided. Unless an agent is actively `reinforce`-ing, the TD values sit at their priors. The immediate opportunity is **plumbing implicit reward signals**: a memory that is retrieved and then quoted in the final response could auto-receive `reward=+1`; a memory retrieved and explicitly discarded via conflict resolution could receive `-1`. This turns the TD layer from a manual API into an automatic learner. H2.

---

## 14. Memory vs. attention vs. context

**Citation.** Cowan, N. (1999). "An embedded-processes model of working memory." In *Models of working memory*.

**Claim.** Working memory is "long-term memory in the focus of attention." The attention mechanism — bottom-up salience + top-down goal-directed — determines *what fraction* of long-term memory is active at any moment. This is the theoretical lineage that Transformer attention claims to echo.

**Engineering implication for the whole SDK.** The distinction between "memory" and "context-assembly-for-the-LLM" collapses under Cowan's framing — *retrieval is attention-allocation into a rolling buffer*. NeuroMem's `ContextManager` (L0–L3 layers) is a context-assembler. The `WorkingMemoryBuffer` is also a context-selector. They do not share an interface. Phase 6 should unify these: a single `ContextBudgetPlanner` that decides — given a query, current WM, token budget — *which memories from which layers go into the prompt*. This is the missing glue between NeuroMem's retrieval output and the LLM's actual context window.

---

## 15. Three-column master mapping

| Cognitive mechanism | NeuroMem component | Gap / implication |
| --- | --- | --- |
| Tulving episodic | `EpisodicMemory` + timestamps | ✅ complete |
| Tulving semantic | `SemanticMemory` + `Consolidator` | ✅ complete |
| Tulving procedural (true non-declarative) | — (NeuroMem's "procedural" is semantic-about-preferences) | Naming drift; document the meaning shift in Phase 5 |
| Tulving priming | — | H3 research bet; not near-term |
| CLS fast-episodic | `EpisodicMemory` + `VerbatimStore` + DG separator | ✅ complete |
| CLS slow-semantic (slow!) | `SemanticMemory` store is there but consolidation fires every 10 turns at `days_threshold=0` | **Phase-6 H2**: Replay/ConsolidationScheduler with offline trigger, sequence-replay, and interleaved updates |
| CLS replay | Config fields unconsumed | Same item |
| Hippocampal indexing (sparse index → content) | `SparseCode` stored but unused | **Phase-6 H1**: wire sparse codes as an optional similarity channel or strip them |
| Pattern separation (DG) | `PatternSeparator` — Achlioptas RP + k-WTA, seeded per user | ✅ complete |
| Pattern completion (CA3 attractor) | `PatternCompleter` re-weights candidates, not a Hopfield net | **Phase-5**: rename to avoid claiming attractor dynamics; Phase-6 leaves alone |
| Systems consolidation (sleep replay) | None | **Phase-6 H2**: same Replay/ConsolidationScheduler; this is the marquee differentiator |
| Ebbinghaus decay | `DecayEngine.calculate_decay` with reinforcement+salience adjustment | ✅ complete (modulo double-count bug from Phase 0 §10) |
| Retrieval-induced forgetting | — | H3; requires category/cluster definitions |
| Interference (proactive/retroactive) | — | H3 |
| Reconsolidation (prediction-error gated) | `ReconsolidationPolicy` heuristic + naïve string merge | **Phase-6 H2**: embed-cosine prediction error + LLM-arbitrated merge (Mem0-style) |
| Working memory (Cowan-4) | `WorkingMemoryBuffer` with attention-gated write | ✅ partial — not wired into retrieval score or context assembly |
| Working-memory modality buffers | — | H3 |
| Episodic buffer (WM↔LTM glue) | `SessionMemory` + `WorkingMemoryBuffer` overlap but don't share state | **Phase-6 H1**: unify |
| Central executive (attention allocator) | — | **Phase-6 H2**: `ContextBudgetPlanner` |
| Schema theory (congruence → faster consolidation) | `SchemaIntegrator` + centroids | **Phase-6 H2**: tie centroids to `MemoryGraph.get_clusters`; use congruence as a consolidation gate |
| HTM SDR overlap | `SparseCode` exists, unused | Same as indexing item |
| Amygdala modulation / flashbulb | `EmotionalTagger` + decay exception | ✅ complete |
| TD learning on retrieval | `TDLearner` manual via `NeuroMem.reinforce` | **Phase-6 H2**: auto-plumb reward from response-use and conflict-deprecation |
| Attention-as-context-assembly | `ContextManager` L0–L3 exists separately from WM | **Phase-6 H2**: unify under `ContextBudgetPlanner` |

---

## 16. The "missing layers" proposal (input to Phase 6)

Based on §§1–14, three conceptual layers are absent from NeuroMem and each has a concrete cognitive-theory grounding:

### 16.1 Replay / Consolidation Scheduler (CLS §2 + Replay §5)
**What.** An offline process that samples (a) recent episodic items plus (b) a sample of existing semantic items, runs interleaved fact-extraction, and updates existing semantic items in place rather than always appending.
**Why.** Every system in Phase 1 consolidates immediately. CLS predicts this causes interference and over-specific semantic memories. A slow, interleaved consolidation is both a theoretical improvement and a marketing differentiator.
**Config stubs already present.** `brain.hippocampus.ripple_interval_minutes`, `ripple_batch_size`.
**Phase-6 horizon.** H2 (1–3 months).

### 16.2 Context Budget Planner (Cowan §8, §14)
**What.** A single component that takes a query + current WM slots + token budget, then decides — via explicit policy — which memories from which layers (WM, session, episodic, semantic, procedural, verbatim) get packed into the LLM context. Replaces both the current `ContextManager` (L0–L3) and the disconnected `WorkingMemoryBuffer` output.
**Why.** Cowan's framing collapses working memory into attention. The SDK currently has *two* context-assembly surfaces (`ContextManager`, `WorkingMemoryBuffer`) that don't talk. Users do the budget math themselves today.
**Phase-6 horizon.** H1 → H2 (H1 for the unification; H2 for budget-optimisation policies).

### 16.3 Prediction-Error-Gated Reconsolidation (§7)
**What.** On retrieval of memory M for query Q, compare M.content against the *new observation context* for Q via embedding cosine; above a threshold (prediction error), trigger LLM-arbitrated update with `add / update / no-op / contradict` decisions — the Mem0 paper's write schema, applied at reconsolidation time rather than first-write time.
**Why.** NeuroMem already names `ReconsolidationPolicy`. The current implementation is a heuristic. Prediction-error-gating is a direct primary-literature import.
**Phase-6 horizon.** H2 (1–3 months).

### 16.4 (Optional H3) Larimar-style "forget with guarantees"
**What.** A forget operation that sweeps all surfaces: episodic, semantic, procedural, verbatim chunks, graph links, entity index, brain sparse codes, WM slots, reconsolidation caches. With a verification pass that confirms no residual trace.
**Why.** Privacy/compliance table stakes for enterprise deployment. Grounded in §9 Phase-1 Larimar work.
**Phase-6 horizon.** H1 (0–4 weeks) for the sweep; H3 for the guarantee proof.

---

## 17. What Phase 2 explicitly does *not* support

Phase 6 proposals that would fail cognitive-grounding review:

- **"Procedural memory" as implicit skill caching.** NeuroMem's procedural layer is semantic-about-preferences. Don't build features on the premise it's Tulvingian procedural; document the meaning shift instead.
- **"Pattern completion" as Hopfield attractor.** The current implementation is candidate re-weighting. Do not justify Phase-6 work by claiming we have true attractor dynamics — the rerank+HyDE pipeline does partial-cue completion pragmatically, which is what matters.
- **"Sparse distributed representations improve retrieval" — untested.** We produce sparse codes that nothing consumes. Either wire them in and measure, or stop computing them.
- **Any "because the brain does it" claim without a 1997-or-later citation.** Brain-faithfulness is a framing, not a theorem.

---

## 18. Exit criterion for Phase 2

Every Phase-6 roadmap item must name a subsection of this document as its **cognitive-theory grounding** (the "Cognitive grounding" field in the mission-brief §6 template). Items that cannot be grounded in §§1–13 are out of scope unless they are pure Phase-1 ports with no cognitive claim (in which case they carry "engineering catch-up" framing, not brain-faithfulness).

---

## 19. Primary citations (consolidated)

- Tulving (1972) — episodic/semantic.
- Tulving (1985) — autonoetic consciousness.
- Tulving & Schacter (1990) — priming.
- Baddeley & Hitch (1974) — working memory.
- Baddeley (2000) — episodic buffer.
- Cowan (2001) — magical number 4.
- Ebbinghaus (1885) — forgetting curve.
- Murre & Dros (2015) — Ebbinghaus replication.
- Anderson, Bjork, Bjork (1994) — retrieval-induced forgetting.
- Underwood (1957) — interference theory.
- Nader, Schafe, LeDoux (2000) — reconsolidation.
- Lee (2009) — reconsolidation updating.
- Sevenster, Beckers, Kindt (2013) — prediction-error gate.
- McClelland, McNaughton, O'Reilly (1995) — CLS.
- Kumaran, Hassabis, McClelland (2016) — CLS update.
- Teyler & DiScenna (1986) — hippocampal indexing.
- Teyler & Rudy (2007) — indexing updated.
- Yassa & Stark (2011) — pattern separation.
- McClelland & Goddard (1996) — DG/CA3 computational.
- Hopfield (1982) — attractor networks.
- Buzsáki (1989) — two-stage memory / sharp waves.
- Wilson & McNaughton (1994) — sleep replay in rodent hippocampus.
- Ji & Wilson (2007) — coordinated cortico-hippocampal replay.
- Liu, Dolan, Kurth-Nelson, Behrens (2019) — human MEG replay.
- Bartlett (1932) — schema.
- Piaget (1952) — assimilation/accommodation.
- Tse et al. (2007) — schema congruence accelerates consolidation.
- Ghosh & Gilboa (2014) — schema neuroscience review.
- Phelps (2004) — amygdala–hippocampus interaction.
- Brown & Kulik (1977) — flashbulb memories.
- McGaugh (2000) — a century of consolidation.
- Talarico & Rubin (2003) — flashbulb vividness vs. accuracy.
- Hawkins, Ahmad, Cui (2017) — HTM columns.
- Ahmad & Hawkins (2016) — SDR math.
- Schultz, Dayan, Montague (1997) — dopaminergic TD.
- Sutton & Barto (2018) — RL textbook.
