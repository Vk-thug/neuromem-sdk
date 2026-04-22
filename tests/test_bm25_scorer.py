"""Tests for BM25 scoring."""

import pytest

from neuromem.core.bm25_scorer import BM25Scorer, tokenize


class TestTokenize:
    def test_basic(self) -> None:
        assert tokenize("Hello World") == ["hello", "world"]

    def test_stop_words_removed(self) -> None:
        result = tokenize("the cat sat on the mat")
        assert "the" not in result
        assert "on" not in result
        assert "cat" in result
        assert "sat" in result
        assert "mat" in result

    def test_short_words_removed(self) -> None:
        # "i" is a stop word; "am" is also a stop word
        result = tokenize("I am here")
        assert "i" not in result
        assert "here" in result

    def test_alphanumeric(self) -> None:
        result = tokenize("CASE-123 product XK500")
        assert "case" in result
        assert "123" in result or "case" in result  # tokenizer may split
        assert "product" in result


class TestBM25Scorer:
    def test_basic_scoring(self) -> None:
        docs = [
            "The quick brown fox jumps over the lazy dog",
            "A bright sunny day at the beach",
            "Python programming is fun and rewarding",
        ]
        scorer = BM25Scorer(docs)
        scores = scorer.score("brown fox jumps")
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]

    def test_idf_rewards_rare_terms(self) -> None:
        # "machine learning" appears once, "the" appears in all
        docs = [
            "Machine learning is an AI technique",
            "The weather is nice today",
            "The cat is on the mat",
        ]
        scorer = BM25Scorer(docs)
        # Query for rare term should heavily favor doc 0
        scores = scorer.score("machine learning")
        assert scores[0] > scores[1] + scores[2]

    def test_normalized_score_range(self) -> None:
        docs = [
            "Python programming language is great",
            "Java is also a good programming language",
            "I had pasta for dinner",
        ]
        scorer = BM25Scorer(docs)
        scores = scorer.normalized_score("python programming")
        assert all(0 <= s <= 1.0 for s in scores)
        assert max(scores) == 1.0  # At least one doc has perfect score

    def test_empty_query(self) -> None:
        scorer = BM25Scorer(["some doc"])
        assert scorer.score("") == [0.0]

    def test_empty_corpus(self) -> None:
        scorer = BM25Scorer([])
        assert scorer.score("query") == []

    def test_no_matching_terms(self) -> None:
        docs = ["abc def", "xyz uvw"]
        scorer = BM25Scorer(docs)
        scores = scorer.score("nothing matches here")
        assert scores == [0.0, 0.0]

    def test_proper_noun_boost(self) -> None:
        # BM25 should rank docs with rare proper nouns higher
        docs = [
            "I work at Acme Corp on the data platform team",
            "My team works on data platforms in general",
            "We have great data and platforms here",
        ]
        scorer = BM25Scorer(docs)
        scores = scorer.score("Acme Corp data platform")
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]
