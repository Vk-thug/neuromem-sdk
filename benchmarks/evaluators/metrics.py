"""
Evaluation metrics for memory system benchmarks.

Implements:
- Exact Match (EM)
- Token-level F1 score
- Precision@k / Recall@k for retrieval
- Aggregation utilities
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field


# ── Lightweight stemmer (no NLTK dependency) ──
# Handles the most common English suffixes that cause F1 mismatches
# in benchmark evaluation (e.g., "dance" vs "dancing", "adopted" vs "adoption").
# Uses a two-pass approach: first strip inflectional suffixes (ing/ed/s),
# then strip derivational suffixes (tion/ment/ness).

_INFLECTIONAL_RULES: list[tuple[str, str, int]] = [
    # (suffix, replacement, min_stem_length)
    ("ying", "y", 2),       # studying -> study
    ("eing", "e", 2),       # agreeing -> agree
    ("cing", "ce", 2),      # dancing -> dance
    ("ging", "ge", 2),      # changing -> change
    ("ving", "ve", 2),      # living -> live
    ("pting", "pt", 2),     # adopting -> adopt (matches adoption -> adopt)
    ("ating", "ate", 2),    # creating -> create (via ate)
    ("nting", "nt", 2),     # painting -> paint, hunting -> hunt
    ("sting", "st", 2),     # listing -> list, testing -> test
    ("lting", "lt", 2),     # melting -> melt
    ("rting", "rt", 2),     # starting -> start
    ("ting", "te", 2),      # writing -> write (default: assume silent-e)
    ("ling", "le", 2),      # bundling -> bundle
    ("ning", "n", 2),       # running -> run
    ("ping", "p", 2),       # shopping -> shop
    ("ming", "m", 2),       # swimming -> swim
    ("bing", "b", 2),       # grabbing -> grab
    ("ding", "d", 2),       # adding -> add
    ("ring", "r", 2),       # occurring -> occur
    ("sing", "se", 2),      # rising -> rise
    ("zing", "ze", 2),      # organizing -> organize
    ("ings", "", 3),        # paintings -> paint (via 'ing' next)
    ("ing", "", 3),         # painting -> paint
    ("ied", "y", 2),        # studied -> study
    ("ced", "ce", 2),       # danced -> dance
    ("ged", "ge", 2),       # changed -> change
    ("ved", "ve", 2),       # lived -> live
    ("pted", "pt", 2),      # adopted -> adopt (matches adoption -> adopt)
    ("ated", "ate", 2),     # created -> create
    ("nted", "nt", 2),      # painted -> paint, hunted -> hunt
    ("sted", "st", 2),      # listed -> list, tested -> test
    ("lted", "lt", 2),      # melted -> melt
    ("rted", "rt", 2),      # started -> start
    ("ted", "te", 2),       # cited -> cite (default: assume silent-e)
    ("led", "le", 2),       # bundled -> bundle
    ("ned", "n", 2),        # planned -> plan
    ("ped", "p", 2),        # stopped -> stop
    ("med", "m", 2),        # named -> name (actually nam, then name_)
    ("bed", "b", 2),        # grabbed -> grab
    ("ded", "d", 2),        # added -> add
    ("red", "r", 2),        # occurred -> occur
    ("sed", "se", 2),       # raised -> raise
    ("zed", "ze", 2),       # organized -> organize
    ("ed", "", 3),          # walked -> walk
    ("ies", "y", 2),        # stories -> story
    ("es", "", 3),          # boxes -> box
    ("s", "", 3),           # cats -> cat
]

_DERIVATIONAL_RULES: list[tuple[str, str, int]] = [
    ("ational", "ate", 2),  # relational -> relate
    ("ation", "ate", 2),    # creation -> create
    ("ption", "pt", 3),     # adoption -> adopt
    ("tion", "", 3),        # action -> act
    ("sion", "", 3),        # discussion -> discuss
    ("ment", "", 3),        # agreement -> agree
    ("ness", "", 3),        # happiness -> happi
    ("ence", "", 3),        # difference -> differ
    ("ance", "", 3),        # importance -> import
    ("ful", "", 3),         # beautiful -> beauti
    ("less", "", 3),        # careless -> care
    ("ally", "al", 3),      # typically -> typical
    ("ly", "", 3),          # quickly -> quick
    ("er", "", 3),          # teacher -> teach
]


def _simple_stem(word: str) -> str:
    """Apply lightweight suffix-stripping stemmer to a single word."""
    if len(word) <= 3:
        return word

    # Pass 1: inflectional suffixes (ing, ed, s)
    for suffix, replacement, min_stem in _INFLECTIONAL_RULES:
        if word.endswith(suffix) and len(word) - len(suffix) >= min_stem:
            return word[: -len(suffix)] + replacement

    # Pass 2: derivational suffixes (tion, ment, ness, etc.)
    for suffix, replacement, min_stem in _DERIVATIONAL_RULES:
        if word.endswith(suffix) and len(word) - len(suffix) >= min_stem:
            return word[: -len(suffix)] + replacement

    return word


def normalize_answer(text: str) -> str:
    """
    Normalize answer text for comparison.

    Strips articles, punctuation, extra whitespace, and lowercases.
    Matches the normalization used in SQuAD and LoCoMo evaluations.
    """
    text = str(text).lower()
    # Remove articles
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    # Collapse whitespace
    text = " ".join(text.split())
    return text.strip()


def normalize_answer_stemmed(text: str) -> str:
    """Normalize answer text with stemming for more lenient token matching."""
    normalized = normalize_answer(text)
    return " ".join(_simple_stem(w) for w in normalized.split())


def exact_match(prediction: str | int | float, ground_truth: str | int | float) -> float:
    """Binary exact match after normalization."""
    return 1.0 if normalize_answer(str(prediction)) == normalize_answer(str(ground_truth)) else 0.0


def token_f1(prediction: str, ground_truth: str) -> float:
    """
    Token-level F1 score between prediction and ground truth.

    Uses stemming so that surface-form differences like "dance" vs "dancing"
    or "adopted" vs "adoption" don't cause spurious F1=0.00 scores.
    This better reflects actual answer quality rather than penalizing
    morphological variation.
    """
    pred_tokens = normalize_answer_stemmed(prediction).split()
    gold_tokens = normalize_answer_stemmed(ground_truth).split()

    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0

    common = set(pred_tokens) & set(gold_tokens)
    num_common = sum(min(pred_tokens.count(t), gold_tokens.count(t)) for t in common)

    if num_common == 0:
        return 0.0

    precision = num_common / len(pred_tokens)
    recall = num_common / len(gold_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def token_precision(prediction: str, ground_truth: str) -> float:
    """Token-level precision."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(ground_truth).split()

    if not pred_tokens:
        return 0.0 if gold_tokens else 1.0

    common = set(pred_tokens) & set(gold_tokens)
    num_common = sum(min(pred_tokens.count(t), gold_tokens.count(t)) for t in common)
    return num_common / len(pred_tokens)


def token_recall(prediction: str, ground_truth: str) -> float:
    """Token-level recall."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(ground_truth).split()

    if not gold_tokens:
        return 1.0
    if not pred_tokens:
        return 0.0

    common = set(pred_tokens) & set(gold_tokens)
    num_common = sum(min(pred_tokens.count(t), gold_tokens.count(t)) for t in common)
    return num_common / len(gold_tokens)


def retrieval_has_answer(
    search_results: list[str],
    ground_truth: str,
) -> bool:
    """Check if any search result contains the ground truth answer."""
    normalized_gt = normalize_answer_stemmed(ground_truth)
    gt_tokens = set(normalized_gt.split())

    if not gt_tokens:
        return True

    for result in search_results:
        normalized = normalize_answer_stemmed(result)
        result_tokens = set(normalized.split())
        # Check if most ground truth tokens appear in the result
        overlap = len(gt_tokens & result_tokens) / len(gt_tokens)
        if overlap >= 0.6:
            return True

    return False


def answer_containment(prediction: str, ground_truth: str) -> float:
    """
    Check if the ground truth answer is contained within the prediction.

    More lenient than exact match — the prediction may contain extra text
    as long as the answer is present. Uses stemming for morphological tolerance.
    """
    pred_norm = normalize_answer_stemmed(prediction)
    gt_norm = normalize_answer_stemmed(ground_truth)

    if gt_norm in pred_norm:
        return 1.0

    # Check token-level containment
    gt_tokens = gt_norm.split()
    pred_norm_text = pred_norm
    contained = sum(1 for t in gt_tokens if t in pred_norm_text)
    return contained / len(gt_tokens) if gt_tokens else 1.0


def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """
    Recall-any@k: 1.0 if any relevant ID appears in top-k retrieved, else 0.0.

    Used by LongMemEval, ConvoMem, and MemBench to measure retrieval quality
    without requiring LLM answer generation.
    """
    if not relevant_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    return 1.0 if top_k & relevant_ids else 0.0


def recall_all_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """Recall-all@k: 1.0 if ALL relevant IDs appear in top-k retrieved."""
    if not relevant_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    return 1.0 if relevant_ids <= top_k else 0.0


def recall_fraction_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """Fractional recall@k: fraction of relevant IDs found in top-k."""
    if not relevant_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    found = len(relevant_ids & top_k)
    return found / len(relevant_ids)


def _dcg(relevances: list[float], k: int) -> float:
    """Discounted Cumulative Gain."""
    import math

    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)
    return score


def ndcg_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """
    Normalized Discounted Cumulative Gain at k.

    Measures ranking quality — rewards systems that place relevant items higher.
    """
    relevances = [1.0 if rid in relevant_ids else 0.0 for rid in retrieved_ids[:k]]
    ideal = sorted(relevances, reverse=True)
    idcg = _dcg(ideal, k)
    if idcg == 0.0:
        return 0.0
    return _dcg(relevances, k) / idcg


@dataclass
class RetrievalBenchmarkMetrics:
    """Metrics for retrieval-focused benchmarks (LongMemEval, ConvoMem, MemBench)."""

    system_name: str
    benchmark_name: str
    total_questions: int = 0

    # R@k and NDCG@k for multiple k values
    recall_any_at_k: dict[int, list[float]] = field(default_factory=dict)
    recall_all_at_k: dict[int, list[float]] = field(default_factory=dict)
    ndcg_at_k: dict[int, list[float]] = field(default_factory=dict)

    # Per-category tracking (category_name -> k -> scores)
    category_recall: dict[str, dict[int, list[float]]] = field(default_factory=dict)

    # Latencies
    latencies_store_ms: list[float] = field(default_factory=list)
    latencies_search_ms: list[float] = field(default_factory=list)

    def add_result(
        self,
        retrieved_ids: list[str],
        relevant_ids: set[str],
        k_values: tuple[int, ...] = (1, 3, 5, 10),
        category: str = "",
    ) -> None:
        """Record one query result across all k values."""
        self.total_questions += 1
        for k in k_values:
            self.recall_any_at_k.setdefault(k, []).append(
                recall_at_k(retrieved_ids, relevant_ids, k)
            )
            self.recall_all_at_k.setdefault(k, []).append(
                recall_all_at_k(retrieved_ids, relevant_ids, k)
            )
            self.ndcg_at_k.setdefault(k, []).append(
                ndcg_at_k(retrieved_ids, relevant_ids, k)
            )
            if category:
                cat_dict = self.category_recall.setdefault(category, {})
                cat_dict.setdefault(k, []).append(
                    recall_at_k(retrieved_ids, relevant_ids, k)
                )

    def avg_recall_any(self, k: int) -> float:
        scores = self.recall_any_at_k.get(k, [])
        return sum(scores) / len(scores) if scores else 0.0

    def avg_recall_all(self, k: int) -> float:
        scores = self.recall_all_at_k.get(k, [])
        return sum(scores) / len(scores) if scores else 0.0

    def avg_ndcg(self, k: int) -> float:
        scores = self.ndcg_at_k.get(k, [])
        return sum(scores) / len(scores) if scores else 0.0

    def category_avg_recall(self, category: str, k: int) -> float:
        scores = self.category_recall.get(category, {}).get(k, [])
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def avg_store_latency_ms(self) -> float:
        return (
            sum(self.latencies_store_ms) / len(self.latencies_store_ms)
            if self.latencies_store_ms
            else 0.0
        )

    @property
    def avg_search_latency_ms(self) -> float:
        return (
            sum(self.latencies_search_ms) / len(self.latencies_search_ms)
            if self.latencies_search_ms
            else 0.0
        )

    def to_dict(self) -> dict:
        result: dict = {
            "system": self.system_name,
            "benchmark": self.benchmark_name,
            "total_questions": self.total_questions,
        }
        for k in sorted(self.recall_any_at_k.keys()):
            result[f"R@{k}"] = round(self.avg_recall_any(k) * 100, 1)
            result[f"R_all@{k}"] = round(self.avg_recall_all(k) * 100, 1)
            result[f"NDCG@{k}"] = round(self.avg_ndcg(k) * 100, 1)
        if self.category_recall:
            result["categories"] = {}
            for cat in sorted(self.category_recall.keys()):
                result["categories"][cat] = {
                    f"R@{k}": round(self.category_avg_recall(cat, k) * 100, 1)
                    for k in sorted(self.category_recall[cat].keys())
                }
        result["avg_store_latency_ms"] = round(self.avg_store_latency_ms, 1)
        result["avg_search_latency_ms"] = round(self.avg_search_latency_ms, 1)
        return result


@dataclass
class BenchmarkMetrics:
    """Aggregated metrics for a benchmark run."""

    system_name: str
    total_questions: int = 0
    exact_matches: int = 0
    f1_scores: list[float] = field(default_factory=list)
    containment_scores: list[float] = field(default_factory=list)
    judge_scores: list[float] = field(default_factory=list)
    retrieval_hits: int = 0  # How many times search results contained the answer
    latencies_store_ms: list[float] = field(default_factory=list)
    latencies_search_ms: list[float] = field(default_factory=list)

    # Per-category tracking
    category_scores: dict[int, list[float]] = field(default_factory=dict)

    @property
    def em_score(self) -> float:
        return self.exact_matches / self.total_questions if self.total_questions else 0.0

    @property
    def avg_f1(self) -> float:
        return sum(self.f1_scores) / len(self.f1_scores) if self.f1_scores else 0.0

    @property
    def avg_containment(self) -> float:
        return (
            sum(self.containment_scores) / len(self.containment_scores)
            if self.containment_scores
            else 0.0
        )

    @property
    def avg_judge_score(self) -> float:
        return (
            sum(self.judge_scores) / len(self.judge_scores)
            if self.judge_scores
            else 0.0
        )

    @property
    def retrieval_hit_rate(self) -> float:
        return self.retrieval_hits / self.total_questions if self.total_questions else 0.0

    @property
    def avg_store_latency_ms(self) -> float:
        return (
            sum(self.latencies_store_ms) / len(self.latencies_store_ms)
            if self.latencies_store_ms
            else 0.0
        )

    @property
    def p95_store_latency_ms(self) -> float:
        if not self.latencies_store_ms:
            return 0.0
        sorted_l = sorted(self.latencies_store_ms)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def avg_search_latency_ms(self) -> float:
        return (
            sum(self.latencies_search_ms) / len(self.latencies_search_ms)
            if self.latencies_search_ms
            else 0.0
        )

    @property
    def p95_search_latency_ms(self) -> float:
        if not self.latencies_search_ms:
            return 0.0
        sorted_l = sorted(self.latencies_search_ms)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    def category_avg_f1(self, category: int) -> float:
        scores = self.category_scores.get(category, [])
        return sum(scores) / len(scores) if scores else 0.0

    def to_dict(self) -> dict:
        return {
            "system": self.system_name,
            "total_questions": self.total_questions,
            "exact_match": round(self.em_score * 100, 1),
            "avg_f1": round(self.avg_f1 * 100, 1),
            "avg_containment": round(self.avg_containment * 100, 1),
            "avg_judge_score": round(self.avg_judge_score, 2),
            "retrieval_hit_rate": round(self.retrieval_hit_rate * 100, 1),
            "avg_store_latency_ms": round(self.avg_store_latency_ms, 1),
            "p95_store_latency_ms": round(self.p95_store_latency_ms, 1),
            "avg_search_latency_ms": round(self.avg_search_latency_ms, 1),
            "p95_search_latency_ms": round(self.p95_search_latency_ms, 1),
            "category_f1": {
                cat: round(self.category_avg_f1(cat) * 100, 1)
                for cat in sorted(self.category_scores.keys())
            },
        }
