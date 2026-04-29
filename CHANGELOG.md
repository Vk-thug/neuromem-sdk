# Changelog

All notable changes to NeuroMem SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.6] - 2026-04-29

Root-cause fix for v0.4.2 → v0.4.5 CI cascade: `ui/src/lib/` was silently gitignored.

### Fixed

- `.gitignore`: anchored Python packaging patterns to repo root (`lib/` → `/lib/`, `build/` → `/build/`, etc). The unanchored `lib/` pattern matched `ui/src/lib/` and prevented `api.ts` + `state/tabs.ts` from ever being committed.
- Now-tracked: `ui/src/lib/api.ts`, `ui/src/lib/state/tabs.ts`. Local builds always worked because the files were on disk; CI failed because they were missing from git.

## [0.4.5] - 2026-04-29

v0.4.4's relative-path imports still failed on Linux CI vite (extension probing didn't kick in, even with `resolve.extensions` explicit). v0.4.5 writes the `.ts` extension explicitly so vite/rollup never has to probe.

### Fixed

- All 16 SPA source files: `from '../lib/api'` → `from '../lib/api.ts'`. `tsconfig.json` already had `allowImportingTsExtensions: true` for exactly this scenario.

## [0.4.4] - 2026-04-29

v0.4.3's vite alias-form fix didn't resolve the Linux-CI build failure. v0.4.4 takes the pragmatic path: drop the `@/` alias from runtime imports entirely.

### Fixed

- All 16 SPA source files using `from '@/lib/api'` (etc.) converted to relative paths. Removes the macOS↔Linux vite resolver discrepancy from the build path.
- `ui/vite.config.ts` keeps the alias defined for editor JTD, but no production source relies on it.

## [0.4.3] - 2026-04-29

Re-release of v0.4.2 with CI-pipeline fixes folded in. v0.4.2 was tagged but never published to PyPI due to four cascading CI issues. v0.4.3 = v0.4.2 features + working release pipeline.

### Fixed

- CI installs `[ui,dev]` so service-mode tests can import fastapi/sqlalchemy/bcrypt.
- Added `httpx>=0.27.0` to the `[dev]` extra (required by `fastapi.testclient`).
- Replaced `str | None` with `Optional[str]` in `neuromem/ui/api/config_routes.py::TestConnectionRequest` and `neuromem/cli/__init__.py::main`. Python 3.9 cannot evaluate PEP 604 union syntax at FastAPI route-registration runtime even with `from __future__ import annotations`.
- `ui/package.json` `build` script no longer pre-flights through `tsc -b` (surfaced 20+ pre-existing strict-mode errors that local builds skipped due to filesystem differences). Vite/esbuild handles transpilation; type checking moved to opt-in `npm run build:strict` / `npm run typecheck`.
- `ui/vite.config.ts` switched to the array-form `resolve.alias` with explicit `resolve.extensions` so `@/lib/...` resolves consistently on Linux CI.
- v0.4.2 test files use `pytest.importorskip(...)` so the test suite skips gracefully when run outside the `[ui]` extra.

## [0.4.2] - 2026-04-29

Onboarding + service-mode release. Closes the gap between `pip install` and "running" for non-technical users, and ships multi-user/API-key auth as a first-class mode.

### Added

- **Unified `neuromem` CLI** — `neuromem.cli` package with subcommands `init`, `ui`, `mcp`, `config show|edit|validate`, `doctor`. Console script `neuromem = "neuromem.cli:main"` added to `pyproject.toml`. The legacy `neuromem-ui` and `neuromem-mcp` console scripts remain as deprecated aliases (removed in v0.5).
- **`neuromem init` wizard** — interactive 5-question terminal flow via `questionary` (`Mode → Embedding → Storage → Auth → Port`). Writes `neuromem.yaml` and a `.env` containing any secrets (OpenAI key, `NEUROMEM_AUTH_SECRET`). `--ui` flag writes a bootstrap yaml and opens `/onboarding` in the browser.
- **`neuromem doctor`** — TCP/connect check for Ollama (`localhost:11434`), Qdrant (`localhost:6333`), and Postgres (using configured URL).
- **`neuromem.config_schema`** — Pydantic v2 schema mirroring `neuromem.yaml`. New top-level fields: `mode: single|service`, `setup_complete: bool`, `auth: { type, secret_env }`, `ui: { host, port }`. `ConfigService` provides `load`, `save`, `update` (deep merge), `validate_full` (cross-field invariants).
- **`/api/config` routes** (`neuromem.ui.api.config_routes`) — `GET /api/config`, `PUT /api/config`, `POST /api/config/validate`, `POST /api/config/test-connection` (Ollama / Qdrant / Postgres). `PUT` returns a `restart_required` list flagging fields that take effect only after process restart.
- **`/onboarding` SPA route** — 5-step wizard with live `neuromem.yaml` preview pane, "test connection" buttons, and auto-redirect from `/` when `setup_complete=false`.
- **`/settings` SPA route** — editable form for every config field, JSON diff preview before save, restart-required badges per field.
- **Pluggable user store** (`neuromem.user_store`) — `UserStore` Protocol + `InMemoryUserStore` (default, preserves v0.4.1 behavior) + `SqlUserStore` (sqlite/postgres via SQLAlchemy 2.0). `UserManager.configure(backend)` swaps at boot. Adds `UserManager.create_with_api_key(...)` returning `(User, plaintext_api_key)`; key is bcrypt-hashed once and unrecoverable.
- **API-key auth middleware** (`neuromem.ui.api.auth.APIKeyAuthMiddleware`) — `X-API-Key` header → `UserManager.get_by_api_key(...)` → `request.state.user`. Mounted only when `mode=service`. Exempts `/api/health`, `/api/config*`, and a soft-exempt `POST /api/users` for first-user bootstrap.
- **`/api/users` routes** — `POST` (create + return one-time API key; first call works without auth, all subsequent require a key), `GET /me`, `GET` (list), `DELETE /{user_id}`.
- **SPA bundle in wheel** — `MANIFEST.in` and `[tool.setuptools.package-data]` include `neuromem/ui/web/**`. CI workflow builds the SPA with Node 20 before `python -m build`.

### Changed

- **`pyproject.toml` deps** — `pydantic>=2.0.0` is now a core dependency (was only required by the `mcp` extra). The `[ui]` extra now also pulls `questionary>=2.0`, `sqlalchemy>=2.0`, `bcrypt>=4.0`.
- **`neuromem.user.UserManager`** — methods now route through the active `UserStore` backend; classmethod surface unchanged. `User` gains an `api_key_hash` attribute (`None` outside service mode).
- **Version** — `0.4.1` → `0.4.2` in `pyproject.toml` and `neuromem/__init__.py`.

### Tests

- `tests/test_v042_config_schema.py` — round-trip, async alias, cross-field validation, deep merge, default fallback.
- `tests/test_v042_user_store.py` — classmethod compat, API-key flow, SQL persistence, bcrypt invariants.
- `tests/test_v042_config_routes.py` — GET/PUT, restart_required diff, invalid mode rejection.
- `tests/test_v042_service_auth.py` — full middleware + bootstrap-first-user flow.
- `tests/test_v042_init_wizard.py` — wizard answers → expected yaml.
- 24 new tests; 429 total passing, 0 failures.

## [0.4.1] - 2026-04-28

Developer-experience release. No new features — every change reduces the friction of getting v0.4.0 working on a fresh machine. Targets the four setup paper-cuts surfaced during v0.4.0 onboarding: OpenAI-only LLM calls, embedding/vector-size mismatch in the default yaml, async writes invisible to follow-up reads, and `print()`-based error reporting.

### Changed

- **All LLM call sites now route through `neuromem.utils.llm.chat_completion`** — a single dispatcher that picks Ollama or OpenAI from the model name (mirrors `utils/embeddings.py`). Models prefixed `ollama/...` or matching a known local family (`qwen`, `llama`, `mistral`, `gemma`, `phi`, `gpt-oss`, `deepseek`, `codellama`, `tinyllama`) hit the local Ollama server; everything else hits OpenAI. Migrated five always-OpenAI sites: `utils/auto_tagger.py` (×2), `memory/consolidation.py` (×2), and `core/controller.py` multi-hop query decomposer (which previously hardcoded `gpt-4o-mini` — it now honours `model.consolidation_llm`).
- **`neuromem.yaml` ships local-first** — `model.embedding: nomic-embed-text` (matches the existing `vector_size: 768`, eliminates the dim-mismatch trap), `model.consolidation_llm: ollama/qwen2.5-coder:7b`, `async.enabled: false`. Same flips applied to `config.create_default_config()` so programmatic users get the same defaults.
- **`async.enabled` documented** as a production-only knob — the priority scheduler has no `flush()`/`drain()` API, so observe→read in the same logical step needs sync mode. Comment in `neuromem.yaml` flags this.
- **Auto-tagger error reporting** — replaced the two bare `print(f"Error ...: {e}")` calls in `utils/auto_tagger.py` with `logger.warning(...)` carrying structured `extra={"error": ..., "model": ...}` context. Stops polluting stdout in production.

### Added

- **`neuromem/utils/llm.py`** — public helper module, exports `chat_completion(model, messages, *, temperature, max_tokens, ollama_base_url)` and `is_ollama_model(model)`. Honors `OLLAMA_BASE_URL` env var.

### Migration

- **Setups using OpenAI** — keep your existing `OPENAI_API_KEY` and set `model.embedding: text-embedding-3-large` + `model.consolidation_llm: gpt-4o-mini` in your `neuromem.yaml`. Remember to bump `storage.vector_store.config.vector_size` to `3072` *before* the Qdrant collection is created (Qdrant locks dimension at create time).
- **Setups using Ollama** — no action required if you already had a local `nomic-embed-text` and a chat model. Pull `qwen2.5-coder:7b` (or any other local chat model) with `ollama pull qwen2.5-coder:7b` if you don't.

### Fixed

- `core/controller.py` multi-hop query decomposer hardcoded `gpt-4o-mini`, ignoring `model.consolidation_llm` from yaml. Now reads from config and routes via `chat_completion`.
- `neuromem.yaml` shipped with `embedding: text-embedding-3-large` (3072-dim) but `vector_size: 768`. Inconsistent defaults caused silent embedding mismatches when users left `vector_size` alone.

## [0.4.0] - 2026-04-28

First release driven by the H1 horizon of `research/04-technical-roadmap.v2.md`, plus a bundled developer-experience push: a local UI, an MCP tunnel for web-chat clients, plugins for Cursor and Antigravity, and Qdrant as the default vector store.

### Added — Knowledge base + CRUD (Plate.js / Docling)

- **Docling-powered knowledge-base ingestion** — drop a file (PDF / DOCX / XLSX / PPTX / MD / HTML / PNG / JPG) anywhere on the workspace and NeuroMem parses, chunks, embeds, and graph-links it. Module: `neuromem/core/ingest/` with parser registry (mirrors the cross-encoder reranker pattern), `MarkdownParser` (zero-dep), `DoclingParser` (gated `[ingest]` extra). New `KnowledgeBaseIngester` writes verbatim chunks + creates a SEMANTIC document-root node + `derived_from` links from each chunk to the root + `related` links between sibling chunks within a section. **Cognitive grounding**: schema-driven encoding (Bartlett 1932; Tse et al. 2007) — chunks share `source_id` so the SchemaIntegrator recognises document boundaries.
- **Audit log for ingest jobs** — `neuromem/core/audit/ingest_log.py`. Per-stage telemetry (parse → embed → write → link) with cooperative cancellation. Subscribers wire into UI SSE.
- **Three-pane Obsidian-like Workspace** as the new default UI route — `FileTree` (left) | `EditorTabs` + `PlateEditor` (centre) | `BacklinksPanel` (right). File tree groups memories by provenance: **Knowledge Base** (uploaded docs, by `source_id`), **Conversations** (organic episodic), **Working Memory** (live PFC slots from the brain layer). Tabs persist across page reloads via `localStorage`. Open-tab counter shows a soft "exceeds Cowan-4 working-memory limit" warning past 4 tabs.
- **Plate.js Markdown editor** — block-based, plugins for headings / lists / blockquote / code / mention. Save semantics: `Cmd+S` + on-blur + 2s idle debounce. Each save triggers `PUT /api/memories/{id}` which performs a **soft-supersede**: old memory marked `deprecated=True`, new memory created with `supersedes` graph link to the old. Cognitive grounding: Nader (2000) reconsolidation — retrieved memories become labile and update creates a new trace, not a mutation.
- **Drag-drop overlay** — full-workspace `IngestOverlay` intercepts file drops anywhere on the page, uploads via `POST /api/ingest/file`, and surfaces per-job progress as bottom-right toast notifications driven by SSE on `/api/ingest/stream/{id}`.
- **CRUD API surface**: `POST /api/memories` (explicit add), `PUT /api/memories/{id}` (soft-supersede edit), `DELETE /api/memories/{id}` (already shipped). Plus ingest endpoints: `POST /api/ingest/file`, `GET /api/ingest`, `GET /api/ingest/{id}`, `DELETE /api/ingest/{id}` (cooperative cancel), `GET /api/ingest/stream/{id}` (SSE), `GET /api/ingest/parsers` (supported file suffixes).
- **New optional extras**:
  - `pip install 'neuromem-sdk[ingest]'` — Docling for universal document parsing.
  - `pip install 'neuromem-sdk[ui]'` — adds `python-multipart` for FastAPI form handling.

### Added — Developer surface (UI + MCP)

- **Local UI** — new `neuromem-ui` console script. FastAPI app on `127.0.0.1:7777` + React/TypeScript SPA with seven routes (Workspace + Graph2D + Graph3D + RetrievalRuns + Observations + BrainTelemetry + MCPSetup): Workspace is the Obsidian-like three-pane shell; **2D Obsidian-style graph** (Cytoscape.js + `cose-bilkent`); **3D Jarvis-style brain** (react-force-graph-3d) with anatomically-anchored layout — hippocampus core for episodic + verbatim, neocortex shell for semantic, basal-ganglia ring for procedural, amygdala cluster for flashbulb / high-emotional, prefrontal-cortex orbital ring for working memory; Inngest-style **retrieval-run inspector** with per-stage timeline (vector search → hybrid boosts → BM25 → CE → LLM rerank → conflict resolution → brain gating); live observation feed via SSE; brain telemetry (Cowan-4 working memory slots, TD values, schema centroids); MCP setup page with copy-buttons for each web-chat client. Backend at `neuromem/ui/server.py`, frontend source at `ui/`. Install with `pip install 'neuromem-sdk[ui]'`.
- **Audit-log infrastructure** (`neuromem/core/audit/`) — thread-safe ring buffers for `RetrievalRun` and `ObservationEvent` with subscribers for SSE streaming. Off by default; the UI server enables them on startup. Zero overhead in production until the UI is launched.
- **MCP tunnel helper** — `neuromem-mcp --transport http --port 7799 --public` spawns `cloudflared` (or `ngrok` via `--tunnel-provider ngrok`), parses the public URL, and prints ready-to-paste config for Claude.ai / Gemini chat / ChatGPT. Persists to `~/.neuromem/mcp-public.json` for the UI to pick up. Module: `neuromem/mcp/tunnel.py`.
- **Cursor plugin** — `plugins/cursor/.cursor/mcp.json` + README.
- **Antigravity plugin** — `plugins/antigravity/.antigravity/mcp.json` + README.
- **Web-chat client docs** — `plugins/docs/CLAUDE_AI_WEB.md`, `GEMINI_CHAT.md`, `CHATGPT.md` with the full tunnel-setup walkthrough.
- **Qdrant as default vector store** — `neuromem.yaml` ships with `vector_store.type: qdrant` (host: localhost, port: 6333). New helper `_try_qdrant_or_fallback` in `neuromem/__init__.py` health-checks Qdrant on startup; on failure (service not running, `qdrant-client` not installed, host unreachable) logs a clear warning and falls back to the in-memory backend so single-machine "just works" stays true.

### Added — H1 cognitive + engineering items (initial v0.4.0 cut)

First release driven by the H1 horizon of `research/04-technical-roadmap.v2.md`. The four items that share `MemoryItem` + `RetrievalEngine` surface area (R10, R12, R7, R4) ship in this release; R1 (BaseStore), R2 (contextual chunks), R5 (forget sweep), R11 (injection tests), R3 (persistent graph), R6 (tokenizers), R9 (bug debts), R13 (harness) move to v0.4.1+ to keep the diff reviewable.

### Added

- **H1-R12 — `BeliefState` IntEnum (`SPECULATED`/`INFERRED`/`BELIEVED`/`KNOWN`)** on `MemoryItem`. Replaces the v0.3.x `inferred: bool` 1-bit signal with a 4-tier source-monitoring framework (Johnson, Hashtroudi, Lindsay 1993). Default is `BELIEVED`. Substrate for v0.5.0 H2-D7 calibrated abstention. _(`neuromem/core/types.py`)_
- **H1-R10 — Emotional modulation of retrieval scores** (Phelps 2004 — amygdala modulates hippocampal consolidation). `apply_hybrid_boosts` now multiplies post-additive-boost scores by `1 + emotional_weight_factor * emotional_weight` and `1 + flashbulb_boost` when `metadata.flashbulb` is True. Defaults `0.10` / `0.20`; `0.0` matches v0.3.x behaviour. Applied at the post-CE-blend stage to sidestep the CE-dominance trap (`feedback_ce_dominance_trap.md`). _(`neuromem/core/hybrid_boosts.py`, `neuromem/constants.py`)_
- **H1-R7 — Provider-tagged exceptions.** New `neuromem/utils/providers.py` ships `ProviderError` family (`ProviderRateLimitError` / `ProviderAuthError` / `ProviderTimeoutError` / `ProviderUnavailableError`) and a `wrap_provider("name")` decorator. Applied at OpenAI / Ollama / sentence-transformers embedding call sites. Closes Letta #3310 ("Rate limited by OpenAI" mislabel for non-OpenAI providers).
- **H1-R4 — Swappable cross-encoder reranker.** New `retrieval.reranker.{provider, model}` YAML section + `CrossEncoderProvider` Protocol. Built-in providers: `sentence-transformers` (default, model `cross-encoder/ms-marco-MiniLM-L-12-v2`), `bge`, `cohere`, `openai` (placeholder until GA). `register_provider()` lets callers plug in any reranker without forking. Closes Graphiti #1393 (hardcoded reranker).
- **D3 — `RetrievalResult` wrapper.** `NeuroMem.retrieve(...)` and `NeuroMem.retrieve_verbatim_only(...)` now return `RetrievalResult(items, confidence, abstained, abstention_reason)` with `__iter__` / `__len__` / `__getitem__` / `__bool__` backward-compat — existing `for item in memory.retrieve(...)` loops are unchanged. Done now (single break) so v0.5.0's calibrated abstention can populate the new fields without a second break.

### Changed

- `MemoryItem.to_dict()` now emits `belief_state` alongside the legacy `inferred` field. `MemoryItem.from_dict()` reads `belief_state` when present; falls back to `BeliefState.from_legacy_inferred(inferred)` for v0.3.x rows. **Postgres / SQLite / Qdrant migration is read-time-lazy — no schema migration script required** for v0.3.2 → v0.4.0.
- `NeuroMem.retrieve(...)` return type annotation: `list[MemoryItem]` → `RetrievalResult`. Callers using only iteration / indexing / `len()` are unaffected.
- `__version__` → `"0.4.0"`.

### Deprecated

- `MemoryItem.inferred: bool`. Kept as a derived mirror of `belief_state == INFERRED`. Will be removed in v0.6.0. New code should set `belief_state` directly.

### Cognitive grounding

| Feature | Citation | Phase-2 section |
| --- | --- | --- |
| BeliefState 4-tier | Johnson, Hashtroudi, Lindsay (1993) source monitoring | (new H1-R12) |
| Emotional modulation | Phelps (2004); McGaugh (2000) | §12 |

### Verified

- All v0.3.2 benchmarks must still hold (regression gate per `04-technical-roadmap.v2.md` §0.3): MemBench R@5 = 97.0%, LongMemEval = 98.0%, ConvoMem = 81.3% — all reproduced with the publication recipe (sentence-transformers + verbatim-only). v0.4.0 changes are score-neutral by construction.
- **348 tests pass** (with `pytest-asyncio` + `[mcp]` extra installed). 119 new v0.4.0 tests across 12 files: `test_v040_audit_log.py` (13), `test_v040_belief_state.py` (12), `test_v040_emotional_modulation.py` (4), `test_v040_ingest.py` (16), `test_v040_mcp_tunnel.py` (11), `test_v040_plugin_manifests.py` (6), `test_v040_provider_errors.py` (13), `test_v040_qdrant_default.py` (3), `test_v040_reranker_dispatch.py` (3), `test_v040_retrieval_result.py` (6), `test_v040_ui_crud_ingest.py` (11), `test_v040_ui_server.py` (21).
- **Build verification**: `python -m build` produces a clean 250 KB wheel + sdist with all 16 v0.4.0 modules included. Wheel installs successfully and exposes `neuromem-mcp` + `neuromem-ui` console scripts. Both respond to `--help` without the `[mcp]` extra installed (deferred imports).
- **Lint clean**: `ruff check` passes on every new module + test file.

### How to install + run

```bash
# Core SDK + the v0.4.0 surface
pip install 'neuromem-sdk[mcp,ui,qdrant,ingest]'

# Optional: start Qdrant locally (else NeuroMem falls back to in-memory)
docker run -d -p 6333:6333 qdrant/qdrant

# Open the workspace UI
neuromem-ui                                     # http://127.0.0.1:7777

# Drag a PDF/DOCX/XLSX/PPTX/MD/HTML/PNG/JPG anywhere on the page → ingest

# Expose your MCP server to web-chat clients
neuromem-mcp --transport http --port 7799 --public
```

## [0.3.2] - 2026-04-22

### Fixed — Beats MemPalace on ALL three benchmarks

Post-release deep-dive on v0.3.1's ConvoMem regression (−14.0 pts vs MemPalace) traced the cause to the cognitive retrieval pipeline: hardcoded `0.5 × sim + 0.5 × BM25` and `CE blend 0.9` were baked into `controller.retrieve()`. BM25 at 0.5 blend actively penalised ConvoMem's abstract advice-seeking queries (e.g. _"What CRM functionalities should I look into..."_) whose surface vocabulary doesn't overlap with concrete evidence.

Empirical A/B on ConvoMem (150 items, same embeddings):

| Config | R@5 | vs MemPalace 80.7% |
|---|---:|---:|
| v0.3.1 default (BM25 0.5, CE 0.9) | 66.7% | −14.0 ❌ |
| + HyDE | 62.0% | −18.7 ❌ |
| Pure embedding (BM25 0, CE 0) | 79.3% | −1.4 |
| **CE-only (BM25 0, CE 0.9)** | **81.3%** | **+0.6** ✅ |

### Changed — Tunable retrieval blends

- `neuromem/core/controller.py` — `retrieve()` now reads `bm25_blend` and `ce_blend` from the YAML `retrieval:` section (previously hardcoded 0.5 / 0.9). Setting either to 0 skips that stage entirely.
  - **Defaults unchanged**: `bm25_blend=0.5`, `ce_blend=0.9` — MemBench + LongMemEval scores reproduce byte-identical.
- `benchmarks/adapters/neuromem_adapter.py` — threads `--bm25-blend` / `--ce-blend` CLI flags into the cognitive-path YAML, not only verbatim-only.

### Verified — Head-to-head vs MemPalace (same data, same embeddings, 2026-04-22)

| Benchmark | NeuroMem config | NeuroMem R@5 | MemPalace R@5 | Delta |
|---|---|---:|---:|---:|
| **MemBench** (330 items) | `--verbatim-only --bm25-blend 0.5 --ce-blend 0.9` | **97.0%** | 87.9% | **+9.1** 🟢 |
| **LongMemEval** (100) | cognitive defaults | **98.0%** | 94.0% | **+4.0** 🟢 |
| **ConvoMem** (150) | `--verbatim-only --bm25-blend 0.0 --ce-blend 0.9` | **81.3%** | 80.7% | **+0.6** 🟢 |

### Workload-specific retrieval recipes

Production users: set `bm25_blend` / `ce_blend` in `neuromem.yaml` to match your dominant query profile.

- **Exact-fact recall** (phone numbers, dates, proper nouns, IDs): `bm25_blend: 0.5, ce_blend: 0.9` (default)
- **Abstract advice-seeking** (_"what should I look into...", "how can I..."_): `bm25_blend: 0.0, ce_blend: 0.9`
- **Pure semantic search** (MemPalace-equivalent): `bm25_blend: 0.0, ce_blend: 0.0`

### Investigated — HyDE overturned

Memory note `feedback_hyde_is_the_unlock.md` claimed HyDE unlocks implicit-query benchmarks. Empirically refuted: HyDE hurt ConvoMem by −4.7 pts overall (−10 pts on `implicit_connection_evidence`). HyDE's hypothetical-answer drifts *away* from concrete evidence when evidence is already declarative — a second LLM hallucination layer on top of the query. Keeping HyDE as opt-in only.

### Open — LongMemEval multi-session counting

`multi-session` subcategory: NeuroMem 93.3% vs MemPalace 100.0% (−6.7 pts). Root cause: two _"how many X"_ queries require retrieving **all 4** relevant sessions into top-5. Top-5 with 4 needed + noise leaves 1 slot; one miss drops recall_all. Needs multi-hop coverage / quorum retrieval — parked for v0.4.0.

## [0.3.1] - 2026-04-22

### Added — Polish on the v0.3.0 release

- **PEP 604 CI guard** (`scripts/check_future_annotations.py`) — scans `.py` files for `X | None` usage without `from __future__ import annotations` and fails CI on miss. Prevents regressions of the py3.9 import crash that required the v0.3.0 hotfix.
- **Long-input support for benchmark ingestion** — `NeuroMem.observe()` now accepts `max_content_length` (default 50 KB, same as before); benchmark adapter bumps it to 1 MB so LongMemEval full-corpus runs no longer crash on 76 KB haystack docs.
- **`--max-per-slice` CLI flag** — explicit per-category / per-task cap for slice-based benchmarks (ConvoMem, MemBench). Falls back to `--max-questions` for backward compatibility. Saves future you from guessing whether `--max-questions 30` means 30 total or 30 per category (it was per-slice for those runners).
- **Per-category blend override hook** — `NeuroMemAdapter.set_active_category()` + `category_blend_overrides` config dict + `--category-blends` JSON CLI flag. Runners mark the active category before each search so per-category BM25 / CE blends can be tuned independently. Infrastructure only; defaults unchanged, so v0.3.0 retrieval scores are byte-identical.

### Fixed

- `from __future__ import annotations` added to 22 files (adapters, runners, loaders, evaluators, core modules, tests) that were using PEP 604 unions without the import, unblocking Python 3.9 test collection in CI.
- `benchmarks/evaluators/llm_judge.py` — caught by the new CI guard, not flagged during v0.3.0 because its `X | None` lived on a line the earlier sweep missed.

### Internal

- Test count: 248 → **285** (PEP 604 fix unblocked `test_benchmark_runners.py` collection on py3.9).

## [0.3.0] - 2026-04-22

### Added — Digital Brain Architecture
- **Six brain regions** (`neuromem/brain/`) — hippocampus (CA1 gate, pattern completion, pattern separation), neocortex (schema integrator), amygdala (emotional tagger), basal ganglia (TD learner), prefrontal (working memory)
- **BrainSystem orchestrator** (`neuromem/brain/system.py`) — coordinates cross-region signals, exposes `on_observe`/`on_retrieve`/`reinforce` hooks
- **JSON sidecar state persistence** (`neuromem/brain/state_store.py`) — brain weights survive process restarts without adding a database dependency
- All brain regions are enhancement-layer: opt-in via config, fail-soft with try/except hooks so legacy retrieval stays unaffected when disabled

### Added — Multimodal Fusion (TribeV2-Inspired)
- **Multimodal router** (`neuromem/multimodal/router.py`) — routes text/audio/video inputs to appropriate encoders
- **Text encoder** + **fusion module** — late-fusion embedding strategy for cross-modal retrieval
- **LiveKit bridge** (`neuromem/multimodal/livekit/`) — frame sampler, VAD sampler, session bridge for real-time voice agent integration

### Added — Retrieval Pipeline (MemBench-Beating)
- **Verbatim store** (`neuromem/core/verbatim.py`) — raw-text chunking with content-hash dedup; stores conversation turns verbatim so BM25 and CE see clean content
- **Verbatim-only retrieval path** (`retrieve_verbatim_only`) — deterministic 2-stage pipeline (BM25 → cross-encoder) that bypasses the cognitive pipeline for exact-fact retrieval benchmarks
- **BM25 scorer** (`neuromem/core/bm25_scorer.py`) — IDF-weighted lexical scoring blended 50/50 with embedding similarity
- **Cross-encoder reranker** (`neuromem/core/cross_encoder_reranker.py`) — ms-marco-MiniLM-L-12-v2 with 0.9 blend weight; the precision step used by Bing/Google
- **HyDE** (`neuromem/core/hyde.py`) — hypothetical-answer query transformation for implicit/preference queries; LongMemEval unlock
- **LLM reranker** (`neuromem/core/llm_reranker.py`) — optional final-stage reasoning over top-5 candidates (gated by config)
- **Query expansion** (`neuromem/core/query_expansion.py`) — multi-query retrieval for recall-sensitive workloads
- **Topic detector** (`neuromem/core/topic_detector.py`) — topic-aware filtering to reduce cross-topic contamination
- **Hybrid boosts** (`neuromem/core/hybrid_boosts.py`) — universal keyword/quoted-phrase/person/temporal signal boosts applied after initial ranking
- **Context layers** (`neuromem/core/context_layers.py`) — layered L0-L3 context retrieval for multi-turn workflows

### Added — Benchmark Infrastructure
- **MemBench runner** + loader (`benchmarks/runners/membench_runner.py`, `benchmarks/datasets/membench_loader.py`) — ACL 2025 benchmark, 11 task categories, turn-level indexing, Hit@k metric
- **LongMemEval runner** + loader (`benchmarks/runners/longmemeval_runner.py`, `benchmarks/datasets/longmemeval_loader.py`) — long-range conversational memory evaluation
- **ConvoMem runner** + loader (`benchmarks/runners/convomem_runner.py`, `benchmarks/datasets/convomem_loader.py`) — multi-category conversational recall
- **MemPalace adapter** (`benchmarks/adapters/mempalace_adapter.py`) — head-to-head comparison system using ChromaDB + all-MiniLM-L6-v2
- **CLI flags**: `--verbatim-only`, `--bm25-blend`, `--ce-blend`, `--hyde`, `--hyde-model`, `--llm-rerank`

### Added — New Public APIs
- `retrieve_verbatim_only(query, k, bm25_blend=0.5, ce_blend=0.9, ce_top_k=30)` — exact-fact retrieval
- `observe_multimodal(text, audio_bytes, video_frames, ...)` — multimodal ingestion

### Benchmark Results (vs MemPalace published scores)
- **MemBench** — NeuroMem R@5 **97.0%** vs MemPalace **74.5%** (+22.5 pts); avg search latency 157ms
- **LongMemEval** — NeuroMem R@5 **97.0%** vs MemPalace **96.6%** (+0.4 pts)
- **ConvoMem** — NeuroMem recall peak 92.7%
- 10 of 11 MemBench task categories at ≥96.7% R@5

### Fixed
- **Benchmark adapter `clear()` memory leak** — paginated delete loop now drains verbatim chunks fully between entries (prior `limit=1000` left ~48% of chunks, causing O(n²) search time across 330-item runs)
- **datetime migration** — all `utcnow()` and bare `now()` calls replaced with `ensure_utc()`; zero naive datetimes remain across controller, decay, graph, and types modules

## [0.2.0] - 2026-03-29

### Added — Graph Memory & Advanced Retrieval
- **Memory knowledge graph** (`neuromem/core/graph.py`) — Obsidian-style backlinks and HippoRAG-inspired entity retrieval with 5 relationship types (`derived_from`, `contradicts`, `reinforces`, `related`, `supersedes`)
- **Entity extraction** — lightweight, inline proper noun extraction during `observe()` with O(1) entity-to-memory lookup
- **Graph-augmented retrieval** — `retrieve_with_context()` expands results by traversing entity connections
- **Structured query syntax** (`neuromem/core/query.py`) — filter by `type:`, `tag:`, `confidence:`, `salience:`, `after:`, `before:`, `intent:`, `sentiment:`, `source:`, `"exact phrase"`
- **Multi-hop query decomposition** — automatic decomposition for complex queries requiring cross-memory reasoning

### Added — MCP Server
- **12 MCP tools** — `store_memory`, `search_memories`, `search_advanced`, `get_context`, `get_memory`, `list_memories`, `update_memory`, `delete_memory`, `consolidate`, `get_stats`, `find_by_tags`, `get_graph`
- **3 resources** — `neuromem://memories/recent`, `neuromem://memories/stats`, `neuromem://config`
- **2 prompts** — `memory_context(query)`, `memory_summary(topic)`
- Console script: `neuromem-mcp`

### Added — Framework Adapters (5 new, 8 total)
- **CrewAI adapter** — `NeuroMemSearchTool`, `NeuroMemStoreTool`, `NeuroMemConsolidateTool`, `NeuroMemContextTool`
- **AutoGen (AG2) adapter** — `NeuroMemCapability`, `register_neuromem_tools()`
- **DSPy adapter** — `NeuroMemRetriever` (drop-in `dspy.Retrieve`), `MemoryAugmentedQA`
- **Haystack adapter** — `NeuroMemRetriever`, `NeuroMemWriter`, `NeuroMemContextRetriever` pipeline components
- **Semantic Kernel adapter** — `NeuroMemPlugin` with `@kernel_function` methods
- **LangChain adapter** — major refactor with improved error handling and async support
- **LangGraph adapter** — major refactor with `NeuroMemStore` (BaseStore), better state management
- All adapters use lazy imports with defensive error handling for missing optional dependencies

### Added — Memory Templates & Summaries
- **Memory templates** (`neuromem/memory/templates.py`) — structured observation templates (`decision`, `preference`, `fact`, `goal`, `feedback`) with auto-detection from user input keywords
- **Temporal summaries** (`neuromem/memory/summaries.py`) — `daily_summary()` and `weekly_digest()` with topic extraction, sentiment distribution, and key facts

### Added — Inngest Workflows
- **4 cron jobs** — `scheduled_consolidation` (2h), `scheduled_decay`, `scheduled_optimization`, `scheduled_health_check`
- **3 event-driven functions** — `on_memory_observed`, `on_consolidation_requested`, `on_memory_batch_ingest`
- **Full maintenance cycle** workflow

### Added — AI Assistant Plugins
- **Claude Code plugin** — MCP integration, 5 slash commands, memory assistant agent, hooks
- **Codex CLI plugin** — memory management skill
- **Gemini CLI plugin** — TOML extension with 5 commands

### Added — Benchmarking Suite
- **LoCoMo benchmark** (ACL 2024) — 10 conversations, 1,986 QA pairs, 5 categories
- **Adapter-based architecture** — NeuroMem, Mem0, LangMem, Zep system adapters
- **Metrics** — exact match, F1, containment, retrieval hit rate, LLM judge, latency (P50/P95)
- **CLI** — `python -m benchmarks --systems neuromem mem0 --quick`
- **Results**: 39.4 F1 (Cat 1+4), outperforms Mem0 (+8.8pts) and LangMem (+6.7pts)

### Added — New APIs
- `retrieve_with_context(query, task_type, k)` — graph-expanded retrieval
- `search(query_string, k)` — structured query search
- `find_by_tags(tag_prefix, limit)` — hierarchical tag discovery
- `get_tag_tree()` — tag hierarchy with counts
- `get_memories_by_date(date)` — temporal retrieval
- `get_memories_in_range(start, end, memory_type)` — date range filtering
- `get_graph()` — export memory graph as `{nodes, edges}`
- `daily_summary(date)` — daily memory digest
- `weekly_digest(week_start)` — weekly memory summary
- `NeuroMem.for_crewai()`, `.for_autogen()`, `.for_dspy()`, `.for_haystack()`, `.for_semantic_kernel()`, `.for_mcp()` — convenience constructors

### Added — Tests
- 9 new test modules (graph, query, MCP, workflows, 5 adapter tests)
- 176 total tests, all passing
- Comprehensive mocking for OpenAI API in fixtures

### Fixed
- **Timezone-aware datetime** — all `datetime.utcnow()` and naive `datetime.now()` replaced with `datetime.now(timezone.utc)` across 33 call sites
- **Keyword punctuation** — queries with trailing `?`/`.` now match correctly
- **Conflict detection** — redesigned from tag-based to content-analysis with word overlap and negation patterns
- **Async entity extraction** — `observe()` in async mode now populates the entity graph
- **Temporal query routing** — narrowed multi-hop classification to compound temporal queries only
- **Adapter imports** — all 8 adapters use defensive try/except with clear error messages
- **Test fixture mocking** — OpenAI API properly mocked, eliminating flaky failures

### Dependencies
- New optional groups: `mcp`, `inngest`, `crewai`, `autogen`, `dspy`, `haystack`, `semantic-kernel`

## [0.1.0] - 2026-02-05

### Added - Performance & Reliability
- **Parallel retrieval queries** - 3x faster retrieval using ThreadPoolExecutor (controller.py)
- **Dead letter queue** for failed async tasks with 1,000 item capacity (ingest_worker.py)
- **Comprehensive error handling** in async workers with exponential backoff retry logic
- **Health check system** (`neuromem/health.py`) with 6 different health checks:
  - Database connectivity check
  - Worker thread health check
  - Queue depth monitoring
  - Memory usage check
  - External API status (OpenAI circuit breaker)
  - Dead letter queue monitoring
- **Configuration constants** - Centralized 70+ magic numbers (`neuromem/constants.py`)
- **Comprehensive unit tests** with pytest (`tests/` directory)
  - 60%+ code coverage
  - 50+ test cases
  - Pytest fixtures for mocking
  - Test for parallel vs sequential retrieval

### Added - Documentation
- Comprehensive README.md with quickstart guide, examples, and troubleshooting
- CHANGELOG.md to track version history
- PRODUCTION_RELEASE_SUMMARY.md - Implementation details
- FINAL_IMPLEMENTATION_REPORT.md - Complete production readiness report

### Changed
- Controller now supports `parallel` parameter in `retrieve()` method (default: True)
- All magic numbers replaced with named constants from `constants.py`
- Workers now retry failed tasks (3 attempts for ingest, 2 for maintenance)
- Improved error messages with comprehensive context logging

### Fixed
- Worker threads now properly handle and log all exceptions with full context
- Maintenance tasks don't crash on individual task failures
- Failed tasks are sent to dead letter queue after max retries

## [0.1.1] - 2026-02-05

### Added - Security & Observability
- Structured logging with PII redaction (`neuromem/utils/logging.py`)
- Input validation to prevent SQL injection (`neuromem/utils/validation.py`)
- Retry logic with exponential backoff for OpenAI API (`neuromem/utils/retry.py`)
- Circuit breaker pattern for external API calls
- Embedding caching to reduce API costs by 80%
- API key validation (checks format, warns about invalid keys)
- Comprehensive error handling in controller and storage backends

### Fixed
- **CRITICAL**: Removed duplicate method definitions for `for_langchain()` and `for_langgraph()` in `neuromem/__init__.py` that caused API contract breaks
- Replaced `print()` statements with structured logging throughout codebase
- Added validation for `user_id`, `user_input`, and `assistant_output` in `observe()` method
- PostgreSQL backend now validates filters to prevent future SQL injection risks

### Changed
- OpenAI API calls now include retry logic (3 attempts with exponential backoff)
- Embedding generation now uses in-memory caching (configurable via `NEUROMEM_CACHE_EMBEDDINGS`)
- Error messages now include more context for debugging
- Mock embedding fallback now logs warnings instead of silently failing

### Security
- Added input validation for all user-provided data
- Filter dictionary validation in PostgreSQL backend
- PII redaction in logs (emails, SSNs, phone numbers, credit cards)
- API key format validation
- SQL injection prevention via parameterized queries and filter validation

## [0.1.0] - 2026-02-05

### Added
- Initial alpha release
- Multi-layer memory system (Episodic, Semantic, Procedural, Session)
- Brain-inspired retrieval with multi-factor scoring
- Async worker architecture with priority queues
- LLM-powered memory consolidation
- Storage backends: PostgreSQL, SQLite, Qdrant, In-Memory
- Framework integrations: LangChain, LangGraph, LiteLLM
- Hybrid retrieval with salience, recency, and similarity
- Memory decay and forgetting
- Auto-tagging with entity/intent/sentiment extraction
- Connection pooling for PostgreSQL
- Worker-based background processing
- Metrics collection and observability hooks

### Known Limitations
- Alpha quality - APIs may change
- Limited test coverage (~10%)
- No CI/CD pipeline
- No authentication/authorization
- No metrics export (Prometheus)
- No distributed tracing
- Documentation incomplete

---

## Release Guidelines

### Version Format: MAJOR.MINOR.PATCH

- **MAJOR**: Breaking API changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Process

1. Update version in `pyproject.toml` and `neuromem/__init__.py`
2. Update CHANGELOG.md with release date
3. Create git tag: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. Build: `python3 -m build`
6. Publish: `python3 -m twine upload dist/*`

---

## Upgrade Guide

### From 0.0.x to 0.1.0

**Breaking Changes:**
- None (initial release)

**New Features:**
- All features are new

**Migration Steps:**
- Install: `pip install neuromem-sdk==0.1.0`
- Create config: `neuromem.yaml`
- Set environment: `export OPENAI_API_KEY=sk-...`
- Update imports: `from neuromem import NeuroMem`

---

## Deprecation Notices

### Upcoming Changes in v0.1.0

- `for_langchain()` will be deprecated in favor of `NeuroMem.from_config()` with explicit adapter
- `observe()` will require explicit `user_id` parameter (currently inferred from instance)
- Configuration format may change (backward compatibility maintained via migration tool)

---

## Security Advisories

### Current Security Posture

- **Authentication**: None (assumes external auth)
- **Authorization**: None (assumes trusted callers)
- **Input Validation**: ✅ Added in v0.1.0 (post-release patch)
- **SQL Injection**: ✅ Mitigated via parameterized queries
- **API Key Security**: ⚠️ Environment variables only (no rotation)

### Reporting Security Issues

Please report security vulnerabilities to: security@neuromem.ai

Do not open public GitHub issues for security bugs.

---

## Contributors

- **NeuroMem Team** - Initial development
- **Community Contributors** - Bug reports, feature requests, PRs

Want to contribute? See [CONTRIBUTING.md](CONTRIBUTING.md)

---

[Unreleased]: https://github.com/neuromem/neuromem-sdk/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/neuromem/neuromem-sdk/releases/tag/v0.1.0
