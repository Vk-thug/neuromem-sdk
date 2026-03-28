# NeuroMem Benchmark Suite

Head-to-head comparison of NeuroMem against Mem0, LangMem, Zep, and other memory systems on the **LoCoMo benchmark** (ACL 2024).

## Quick Start

```bash
# Install dependencies
pip install -r benchmarks/requirements.txt

# Quick test (1 conversation, no LLM judge, ~2 min)
python -m benchmarks --quick --verbose

# NeuroMem vs all systems
python -m benchmarks --systems neuromem mem0 langmem \
  --embedding-provider openai --embedding-model text-embedding-3-small \
  --answer-provider openai --answer-model gpt-4o-mini --no-judge

# Include Zep (requires ZEP_API_KEY)
export ZEP_API_KEY=your_key_here
python -m benchmarks --systems neuromem mem0 langmem zep

# Head-to-head: NeuroMem vs Mem0
python -m benchmarks --systems neuromem mem0

# Latency benchmark
python -m benchmarks --latency --systems neuromem mem0 langmem

# Dataset statistics
python -m benchmarks --dataset-stats
```

## Supported Systems

| System | Package | Requirements |
|--------|---------|-------------|
| **neuromem** | local SDK | OpenAI API key |
| **mem0** | `mem0ai` | OpenAI API key |
| **langmem** | `langmem` | OpenAI API key |
| **zep** | `zep-cloud` | `ZEP_API_KEY` from app.getzep.com |

## Benchmark: LoCoMo

The [LoCoMo](https://github.com/snap-research/locomo) dataset (ACL 2024) contains 10 extended multi-session conversations with 1,986 QA pairs across 5 categories:

| Category | Count | Description |
|----------|-------|-------------|
| 1. Single-hop | 282 | Answer from a single dialogue turn |
| 2. Temporal | 321 | Time-related questions |
| 3. Open-ended | 96 | Requires reasoning across turns |
| 4. Multi-hop | 841 | Answer spans multiple turns |
| 5. Adversarial | 446 | Unanswerable/false premise |

## Metrics

| Metric | What it measures |
|--------|-----------------|
| **Exact Match (EM)** | Binary match after normalization |
| **Token F1** | Word overlap between prediction and ground truth |
| **Answer Containment** | Whether ground truth appears within prediction |
| **Retrieval Hit Rate** | Whether search results contain the answer |
| **LLM Judge (1-5)** | GPT-4o/Ollama scores answer quality |
| **Store Latency** | P50/P95 for memory storage |
| **Search Latency** | P50/P95 for memory retrieval |

## Configuration

### Embedding Providers

```bash
# Ollama (local, default)
--embedding-provider ollama --embedding-model nomic-embed-text

# OpenAI
--embedding-provider openai --embedding-model text-embedding-3-small
```

### Storage Backends

```bash
# In-memory (default, fast but no persistence)
--backend memory

# Qdrant (production-grade)
--backend qdrant --qdrant-host localhost --qdrant-port 6333
```

### Ingestion Modes

```bash
# Raw dialogue turns (most granular, slow)
--ingestion-mode turns

# Pre-extracted observations/facts (recommended)
--ingestion-mode observations

# Session summaries (fastest, least granular)
--ingestion-mode summaries
```

### Answer Generation

```bash
# Ollama (local, default)
--answer-provider ollama --answer-model qwen2.5-coder:7b

# OpenAI
--answer-provider openai --answer-model gpt-4o-mini
```

## Architecture

```
benchmarks/
├── datasets/
│   └── locomo_loader.py     # Downloads + parses LoCoMo-10
├── adapters/
│   ├── base.py              # MemorySystemAdapter protocol
│   ├── neuromem_adapter.py  # NeuroMem SDK
│   ├── mem0_adapter.py      # Mem0 (mem0ai)
│   ├── langmem_adapter.py   # LangMem (LangGraph InMemoryStore)
│   └── zep_adapter.py       # Zep Cloud (requires ZEP_API_KEY)
├── evaluators/
│   ├── metrics.py           # EM, F1, containment, BenchmarkMetrics
│   └── llm_judge.py         # LLM-as-a-Judge (Ollama/OpenAI)
├── runners/
│   ├── locomo_runner.py     # Main QA benchmark
│   └── latency_runner.py    # P50/P95 latency
├── results/                 # JSON output (gitignored)
└── run_benchmark.py         # CLI entry point
```

## Published Scores (for comparison)

| System | LoCoMo Score | Source |
|--------|-------------|--------|
| SuperLocalMemory V3 | 87.7% | Self-reported |
| Zep | ~75-85% | Self-reported |
| Letta (MemGPT) | 74.0% | Mem0 paper |
| Mem0 Graph | 68.5% | Mem0 paper |
| Mem0 Dense | 66.9% | Mem0 paper |
| LangMem | 58.1% | Mem0 paper |
| OpenAI Memory | 52.9% | Mem0 paper |
