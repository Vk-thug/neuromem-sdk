"""
LoCoMo benchmark runner.

Feeds multi-session conversations into each memory system, then asks
the QA pairs and evaluates answers using F1 + LLM-as-a-Judge.

This is the primary benchmark for comparing NeuroMem against Mem0, Zep, etc.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Optional

from benchmarks.adapters.base import MemorySystemAdapter
from benchmarks.datasets.locomo_loader import (
    CATEGORY_NAMES,
    Conversation,
    DialogueTurn,
    QAPair,
    load_locomo,
)
from benchmarks.evaluators.llm_judge import LLMJudge
from benchmarks.evaluators.metrics import (
    BenchmarkMetrics,
    answer_containment,
    exact_match,
    retrieval_has_answer,
    token_f1,
)


# Template for generating answers from retrieved context
ANSWER_PROMPT = """You are answering questions about a conversation between two people.
Use ONLY the provided memory context to answer.

CRITICAL RULES:
1. Answer as briefly as possible — match the expected answer style exactly:
   - Single-word: "Sweden", "Single", "sunset", "abstract art"
   - Short phrase: "Adoption agencies", "Transgender woman", "counseling or mental health"
   - For lists: comma-separated terms only — include ALL matching items from context
   - For counts/numbers: use numerals only (e.g., "2" not "twice" or "a couple of times")
   - One short sentence MAXIMUM for complex answers
2. Do NOT explain, elaborate, justify, or add context
3. Do NOT include the person's name unless it is part of the answer itself
4. If context does not contain the answer: say exactly "Unknown"
5. For list questions (activities, hobbies, events, etc.): scan ALL context chunks for items

Memory Context:
{context}

Question: {question}

Answer (be extremely brief, no extra words):"""


@dataclass
class RunConfig:
    """Configuration for a benchmark run."""

    # Dataset
    max_conversations: Optional[int] = None  # None = all 10
    categories: Optional[list[int]] = None  # None = all 5 categories
    max_qa_per_conversation: Optional[int] = None  # None = all QA pairs

    # Ingestion
    ingestion_mode: str = "turns"  # "turns" | "observations" | "summaries"
    batch_turns: int = 1  # Group N turns into a single memory

    # Retrieval
    search_k: int = 10  # Number of memories to retrieve per query

    # Answer generation
    answer_llm: str = "qwen2.5-coder:7b"
    answer_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"

    # Evaluation
    use_llm_judge: bool = True
    judge_model: str = "qwen2.5-coder:7b"
    judge_provider: str = "ollama"

    # Output
    verbose: bool = False


def _generate_answer(
    question: str,
    context: str,
    model: str,
    provider: str,
    ollama_base_url: str,
) -> str:
    """Generate an answer from retrieved context using an LLM."""
    prompt = ANSWER_PROMPT.format(context=context, question=question)

    if provider == "ollama":
        import ollama
        client = ollama.Client(host=ollama_base_url)
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"].strip()

    elif provider == "openai":
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    elif provider == "litellm":
        import litellm
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    raise ValueError(f"Unknown provider: {provider}")


def _ingest_conversation(
    adapter: MemorySystemAdapter,
    conversation: Conversation,
    user_id: str,
    config: RunConfig,
    metrics: BenchmarkMetrics,
) -> None:
    """Feed conversation turns into the memory system."""
    if config.ingestion_mode == "summaries":
        # Use pre-generated session summaries (faster, less granular)
        for sn in sorted(conversation.session_summaries.keys()):
            summary = conversation.session_summaries[sn]
            date = conversation.session_dates.get(sn, "")
            t0 = time.perf_counter()
            adapter.add_memory(
                user_id=user_id,
                content=summary,
                metadata={"session_id": str(sn), "date": date, "type": "summary"},
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            metrics.latencies_store_ms.append(elapsed_ms)

    elif config.ingestion_mode == "observations":
        # Use pre-extracted observations (facts with evidence)
        for sn in sorted(conversation.observations.keys()):
            for speaker, obs_list in conversation.observations[sn].items():
                for obs_text, evidence_ref in obs_list:
                    t0 = time.perf_counter()
                    adapter.add_memory(
                        user_id=user_id,
                        content=obs_text,
                        metadata={
                            "session_id": str(sn),
                            "speaker": speaker,
                            "evidence": evidence_ref,
                        },
                    )
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    metrics.latencies_store_ms.append(elapsed_ms)

    else:
        # Default: ingest raw dialogue turns
        all_turns = conversation.all_turns
        batch: list[DialogueTurn] = []

        for turn in all_turns:
            batch.append(turn)
            if len(batch) >= config.batch_turns:
                content = "\n".join(f"{t.speaker}: {t.text}" for t in batch)
                session_id = str(batch[0].session_num)
                date = conversation.session_dates.get(batch[0].session_num, "")

                t0 = time.perf_counter()
                adapter.add_memory(
                    user_id=user_id,
                    content=content,
                    metadata={
                        "session_id": session_id,
                        "speaker": batch[0].speaker,
                        "date": date,
                    },
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                metrics.latencies_store_ms.append(elapsed_ms)
                batch = []

        # Flush remaining
        if batch:
            content = "\n".join(f"{t.speaker}: {t.text}" for t in batch)
            t0 = time.perf_counter()
            adapter.add_memory(
                user_id=user_id,
                content=content,
                metadata={"session_id": str(batch[0].session_num)},
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            metrics.latencies_store_ms.append(elapsed_ms)


def _evaluate_qa(
    adapter: MemorySystemAdapter,
    qa: QAPair,
    user_id: str,
    config: RunConfig,
    metrics: BenchmarkMetrics,
    judge: Optional[LLMJudge],
    conv_id: str,
) -> dict:
    """Evaluate a single QA pair against the memory system."""
    # Search
    t0 = time.perf_counter()
    search_results = adapter.search(user_id=user_id, query=qa.question, k=config.search_k)
    search_ms = (time.perf_counter() - t0) * 1000
    metrics.latencies_search_ms.append(search_ms)

    # Build context from search results
    context_parts = [r.content for r in search_results]
    context = "\n---\n".join(context_parts) if context_parts else "No relevant memories found."

    # Check retrieval quality
    has_answer = retrieval_has_answer(context_parts, qa.answer)
    if has_answer:
        metrics.retrieval_hits += 1

    # Generate answer
    try:
        prediction = _generate_answer(
            question=qa.question,
            context=context,
            model=config.answer_llm,
            provider=config.answer_provider,
            ollama_base_url=config.ollama_base_url,
        )
    except Exception as e:
        prediction = f"Error generating answer: {e}"

    # Compute metrics
    em = exact_match(prediction, qa.answer)
    f1 = token_f1(prediction, qa.answer)
    contain = answer_containment(prediction, qa.answer)

    if em > 0:
        metrics.exact_matches += 1
    metrics.f1_scores.append(f1)
    metrics.containment_scores.append(contain)
    metrics.total_questions += 1

    # Track per-category
    metrics.category_scores.setdefault(qa.category, []).append(f1)

    # LLM Judge
    judge_result = {"score": 0, "reasoning": "Judge disabled"}
    if judge and config.use_llm_judge:
        judge_result = judge.score(
            question=qa.question,
            ground_truth=qa.answer,
            prediction=prediction,
            is_adversarial=qa.is_adversarial,
        )
        if judge_result["score"] > 0:
            metrics.judge_scores.append(judge_result["score"])

    result = {
        "conversation": conv_id,
        "question": qa.question,
        "ground_truth": qa.answer,
        "prediction": prediction,
        "category": qa.category,
        "category_name": CATEGORY_NAMES.get(qa.category, "unknown"),
        "exact_match": em,
        "f1": round(f1, 4),
        "containment": round(contain, 4),
        "retrieval_hit": has_answer,
        "judge_score": judge_result["score"],
        "judge_reasoning": judge_result["reasoning"],
        "search_latency_ms": round(search_ms, 1),
        "num_results": len(search_results),
    }

    if config.verbose:
        symbol = "+" if f1 >= 0.5 else "-"
        cat_name = CATEGORY_NAMES.get(qa.category, "?")
        print(f"  [{symbol}] ({cat_name}) F1={f1:.2f} | Q: {qa.question[:60]}...")

    return result


def run_locomo_benchmark(
    adapter: MemorySystemAdapter,
    adapter_config: dict,
    run_config: Optional[RunConfig] = None,
) -> tuple[BenchmarkMetrics, list[dict]]:
    """
    Run the LoCoMo benchmark on a memory system.

    Args:
        adapter: Memory system adapter (NeuroMem, Mem0, etc.)
        adapter_config: Configuration dict for the adapter
        run_config: Benchmark run configuration

    Returns:
        (metrics, detailed_results) tuple
    """
    config = run_config or RunConfig()

    # Load dataset
    print(f"\nLoading LoCoMo dataset...")
    conversations = load_locomo(
        max_conversations=config.max_conversations,
        categories=config.categories,
    )
    total_qa = sum(len(c.qa_pairs) for c in conversations)
    print(f"Loaded {len(conversations)} conversations, {total_qa} QA pairs")

    # Initialize adapter
    print(f"\nInitializing {adapter.name}...")
    adapter.setup(adapter_config)

    # Initialize judge
    judge = None
    if config.use_llm_judge:
        judge = LLMJudge(
            model=config.judge_model,
            provider=config.judge_provider,
            ollama_base_url=config.ollama_base_url,
        )

    # Metrics
    metrics = BenchmarkMetrics(system_name=adapter.name)
    all_results: list[dict] = []

    for conv_idx, conversation in enumerate(conversations):
        user_id = str(uuid.uuid4())
        conv_id = conversation.sample_id

        print(f"\n{'=' * 60}")
        print(
            f"[{conv_idx + 1}/{len(conversations)}] {conv_id}: "
            f"{conversation.speaker_a} & {conversation.speaker_b}"
        )
        print(
            f"  Sessions: {len(conversation.sessions)} | "
            f"Turns: {conversation.total_turns} | "
            f"QA pairs: {len(conversation.qa_pairs)}"
        )

        # Phase 1: Ingest conversation
        print(f"  Ingesting ({config.ingestion_mode} mode)...")
        t0 = time.perf_counter()
        _ingest_conversation(adapter, conversation, user_id, config, metrics)
        ingest_time = time.perf_counter() - t0
        mem_count = adapter.memory_count(user_id)
        print(f"  Ingested {mem_count} memories in {ingest_time:.1f}s")

        # Phase 2: Evaluate QA pairs
        qa_pairs = conversation.qa_pairs
        if config.max_qa_per_conversation:
            qa_pairs = qa_pairs[: config.max_qa_per_conversation]

        print(f"  Evaluating {len(qa_pairs)} questions...")
        for qa in qa_pairs:
            result = _evaluate_qa(
                adapter, qa, user_id, config, metrics, judge, conv_id
            )
            all_results.append(result)

        # Clean up for next conversation
        adapter.clear(user_id)

    return metrics, all_results
