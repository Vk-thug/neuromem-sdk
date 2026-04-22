"""
BM25 scoring for hybrid retrieval.

BM25 is a more principled keyword scoring than simple overlap because it:
1. Weights rare terms higher (IDF) — proper nouns and specific keywords matter more
2. Saturates term frequency (k1 parameter) — multiple matches get diminishing returns
3. Length-normalizes documents (b parameter) — long docs aren't penalized excessively

Used as a re-ranking signal alongside vector similarity to fix cases where
embeddings miss precise lexical matches (e.g., proper nouns, dates, IDs).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List

# Default BM25 parameters (Robertson et al. recommended values)
DEFAULT_K1 = 1.5  # Term frequency saturation
DEFAULT_B = 0.75  # Length normalization

# Stop words to exclude from tokenization
_BM25_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "their",
        "this",
        "that",
        "these",
        "those",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "and",
        "or",
        "but",
        "not",
        "no",
        "yes",
        "what",
        "when",
        "where",
        "how",
        "why",
        "who",
        "which",
        "if",
    }
)


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase non-stop words (3+ chars)."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())
    return [w for w in words if len(w) >= 2 and w not in _BM25_STOP_WORDS]


class BM25Scorer:
    """
    BM25 scorer for a corpus of documents.

    Build once per query batch:
        scorer = BM25Scorer(documents)
        for query in queries:
            scores = scorer.score(query)
    """

    def __init__(
        self,
        documents: List[str],
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.tokenized_docs: List[List[str]] = [tokenize(d) for d in documents]
        self.doc_lengths: List[int] = [len(td) for td in self.tokenized_docs]
        self.avg_doc_length: float = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )
        self.n_docs = len(documents)

        # Compute IDF for each unique term
        self.idf: Dict[str, float] = self._compute_idf()

    def _compute_idf(self) -> Dict[str, float]:
        """Compute inverse document frequency for each term."""
        df: Counter = Counter()
        for tokens in self.tokenized_docs:
            for term in set(tokens):
                df[term] += 1

        idf = {}
        for term, freq in df.items():
            # Add 1 to numerator and denominator to avoid log(0)
            # and use the BM25+ formulation for non-negative scores
            idf[term] = math.log((self.n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

        return idf

    def score(self, query: str) -> List[float]:
        """
        Compute BM25 score for each document against the query.

        Returns:
            List of scores, one per document, in the same order as documents.
        """
        query_terms = tokenize(query)
        if not query_terms:
            return [0.0] * self.n_docs

        scores: List[float] = []
        for doc_idx, tokens in enumerate(self.tokenized_docs):
            if not tokens:
                scores.append(0.0)
                continue

            doc_len = self.doc_lengths[doc_idx]
            term_freqs = Counter(tokens)
            score = 0.0

            for term in query_terms:
                if term not in self.idf:
                    continue
                tf = term_freqs.get(term, 0)
                if tf == 0:
                    continue

                idf = self.idf[term]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1)
                )
                score += idf * numerator / denominator

            scores.append(score)

        return scores

    def normalized_score(self, query: str) -> List[float]:
        """
        BM25 scores normalized to [0, 1] for use as a boost signal.

        Divides by the maximum score in the result set.
        """
        scores = self.score(query)
        if not scores:
            return scores
        max_score = max(scores)
        if max_score == 0.0:
            return scores
        return [s / max_score for s in scores]
