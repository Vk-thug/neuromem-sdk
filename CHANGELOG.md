# Changelog

All notable changes to NeuroMem SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
