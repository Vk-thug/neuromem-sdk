"""
Tests for hybrid retrieval boost signals (Phase 3 of v0.4.0).
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from neuromem.core.hybrid_boosts import (
    apply_hybrid_boosts,
    compute_keyword_overlap,
    compute_temporal_boost,
    extract_keywords,
    extract_person_names,
    extract_quoted_phrases,
    parse_temporal_offset,
)


# ── Keyword Extraction ──


class TestExtractKeywords:
    def test_basic(self) -> None:
        kw = extract_keywords("What is the capital of France?")
        assert "capital" in kw
        assert "france" in kw
        assert "what" not in kw  # stop word
        assert "the" not in kw

    def test_short_words_excluded(self) -> None:
        kw = extract_keywords("I am at home")
        assert "home" in kw
        assert "am" not in kw  # < 3 chars

    def test_empty(self) -> None:
        assert extract_keywords("") == []


class TestExtractQuotedPhrases:
    def test_double_quotes(self) -> None:
        phrases = extract_quoted_phrases('What did she say about "yoga classes"?')
        assert "yoga classes" in phrases

    def test_single_quotes_multi_word(self) -> None:
        phrases = extract_quoted_phrases("What about 'abstract art'?")
        assert "abstract art" in phrases

    def test_single_word_quotes_excluded(self) -> None:
        phrases = extract_quoted_phrases("She said 'hello'")
        assert len(phrases) == 0  # Single-word single quotes excluded

    def test_no_quotes(self) -> None:
        assert extract_quoted_phrases("No quotes here") == []


class TestExtractPersonNames:
    def test_basic(self) -> None:
        names = extract_person_names("I talked to Sarah about yoga")
        assert "Sarah" in names

    def test_excludes_days_months(self) -> None:
        names = extract_person_names("I saw Monday and January")
        assert "Monday" not in names
        assert "January" not in names

    def test_excludes_sentence_start(self) -> None:
        names = extract_person_names("The weather is nice")
        assert "The" not in names

    def test_multiple_names(self) -> None:
        names = extract_person_names("I met with Alice and Bob today")
        assert "Alice" in names
        assert "Bob" in names


# ── Temporal Parsing ──


class TestParseTemporalOffset:
    def test_yesterday(self) -> None:
        result = parse_temporal_offset("What happened yesterday?")
        assert result == (1, 1)

    def test_last_week(self) -> None:
        result = parse_temporal_offset("What did I say last week?")
        assert result is not None
        assert result[0] == 7

    def test_n_days_ago(self) -> None:
        result = parse_temporal_offset("What did I say 3 days ago?")
        assert result is not None
        assert result[0] == 3

    def test_n_weeks_ago(self) -> None:
        result = parse_temporal_offset("About 2 weeks ago I mentioned...")
        assert result is not None
        assert result[0] == 14

    def test_recently(self) -> None:
        result = parse_temporal_offset("What did I recently say?")
        assert result is not None
        assert result[0] == 7

    def test_no_temporal(self) -> None:
        assert parse_temporal_offset("What is the capital of France?") is None


class TestComputeTemporalBoost:
    def test_exact_match(self) -> None:
        query_date = datetime(2024, 3, 15)
        # "yesterday" from query_date = March 14
        boost = compute_temporal_boost(
            "yesterday",
            "2024/03/14",
            query_date=query_date,
        )
        assert boost == 1.0

    def test_within_window(self) -> None:
        query_date = datetime(2024, 3, 15)
        boost = compute_temporal_boost(
            "yesterday",
            "2024/03/14",
            query_date=query_date,
        )
        assert boost > 0.0

    def test_no_temporal_reference(self) -> None:
        boost = compute_temporal_boost("What is your name?", "2024/03/14")
        assert boost == 0.0

    def test_no_timestamp(self) -> None:
        boost = compute_temporal_boost("yesterday", "")
        assert boost == 0.0


# ── Keyword Overlap ──


class TestComputeKeywordOverlap:
    def test_full_overlap(self) -> None:
        assert compute_keyword_overlap(["yoga", "class"], "I went to a yoga class") == 1.0

    def test_partial_overlap(self) -> None:
        assert compute_keyword_overlap(["yoga", "swim"], "I went to yoga") == 0.5

    def test_no_overlap(self) -> None:
        assert compute_keyword_overlap(["yoga"], "I went swimming") == 0.0

    def test_empty_keywords(self) -> None:
        assert compute_keyword_overlap([], "Some text") == 0.0


# ── Full Boost Pipeline ──


def _make_item(content: str, metadata: dict = None) -> SimpleNamespace:
    """Create a mock item with content and metadata."""
    return SimpleNamespace(content=content, metadata=metadata or {})


class TestApplyHybridBoosts:
    def test_keyword_boost(self) -> None:
        # Long content gets linear keyword boost. Query has 4 keywords;
        # yoga doc matches all 4, weather doc matches none.
        yoga_content = (
            "I love yoga meditation practice routines. It helps me relax "
            "after a long day at work. I've been practicing yoga for five "
            "years now and it has really improved my flexibility and mental "
            "clarity. My favorite styles are hatha and vinyasa meditation." * 2
        )
        weather_content = (
            "The forecast is nice today and I'm going for a walk in the park. "
            "The sun is shining and there's a gentle breeze. I love days "
            "like this when I can enjoy the outdoors and sunshine." * 2
        )
        items = [
            (_make_item(yoga_content), 0.5),
            (_make_item(weather_content), 0.6),
        ]
        boosted = apply_hybrid_boosts(items, "Tell me about yoga meditation practice routines")
        # "yoga" item should be boosted above "weather" item
        assert boosted[0][0].content == yoga_content

    def test_quoted_phrase_boost(self) -> None:
        items = [
            (_make_item("She likes abstract art and painting"), 0.4),
            (_make_item("She went to the art gallery"), 0.5),
        ]
        boosted = apply_hybrid_boosts(items, 'What does she think about "abstract art"?')
        assert boosted[0][0].content == "She likes abstract art and painting"

    def test_person_name_boost(self) -> None:
        items = [
            (_make_item("Sarah mentioned she likes hiking"), 0.4),
            (_make_item("Someone enjoys outdoor activities"), 0.5),
        ]
        boosted = apply_hybrid_boosts(items, "What did Sarah say about hobbies?")
        assert boosted[0][0].content == "Sarah mentioned she likes hiking"

    def test_no_boost_without_signals(self) -> None:
        items = [
            (_make_item("First item"), 0.5),
            (_make_item("Second item"), 0.6),
        ]
        boosted = apply_hybrid_boosts(items, "a b c")
        # Order preserved when no signals match
        assert boosted[0][1] >= boosted[1][1]

    def test_score_capped_at_one(self) -> None:
        items = [
            (_make_item("Sarah yoga abstract art painting"), 0.9),
        ]
        # All boosts fire — should cap at 1.0
        boosted = apply_hybrid_boosts(
            items, 'What did Sarah say about "abstract art" and yoga?'
        )
        assert boosted[0][1] <= 1.0

    def test_empty_items(self) -> None:
        assert apply_hybrid_boosts([], "some query") == []

    def test_empty_query(self) -> None:
        items = [(_make_item("content"), 0.5)]
        result = apply_hybrid_boosts(items, "")
        assert result == items

    def test_temporal_boost_with_metadata(self) -> None:
        query_date = datetime(2024, 3, 15)
        items = [
            (_make_item("Old session content", {"timestamp": "2024/01/01"}), 0.5),
            (_make_item("Recent session content", {"timestamp": "2024/03/14"}), 0.4),
        ]
        boosted = apply_hybrid_boosts(
            items, "What happened yesterday?", query_date=query_date
        )
        # Recent item should get temporal boost
        assert boosted[0][0].content == "Recent session content"

    def test_multiple_signals_compound(self) -> None:
        """Multiple matching signals should compound boosts."""
        items = [
            (_make_item("Sarah mentioned yoga last Tuesday"), 0.3),
            (_make_item("Generic content about exercise"), 0.5),
        ]
        boosted = apply_hybrid_boosts(items, "What did Sarah say about yoga?")
        # Both keyword ("yoga") and person name ("Sarah") boosts should fire
        sarah_item = [b for b in boosted if "Sarah" in b[0].content][0]
        assert sarah_item[1] > 0.3 + 0.30  # At least keyword boost fired

    def test_short_content_moderate_overlap_gets_boost(self) -> None:
        """Short content (~100-300 chars) with 20-40% overlap MUST get boosted.

        This is the MemBench bug: previously, short content required >=50%
        overlap to get ANY boost (quadratic-only path), which zeroed-out
        nearly every turn in MemBench (~150 char turns with ~30% overlap).
        Regression guard: a short turn with partial overlap should rank
        ABOVE a short turn with ZERO overlap at the same base score.
        """
        relevant = _make_item(
            "[User] My brother has an associate degree. [Assistant] Got it."
        )
        distractor = _make_item(
            "[User] The weather is very nice today. [Assistant] Enjoy the sun."
        )
        items = [
            (distractor, 0.5),
            (relevant, 0.5),  # Same base score — boost must break the tie
        ]
        boosted = apply_hybrid_boosts(
            items, "What is the age of someone with an Associate Degree?"
        )
        # Relevant turn must be ranked first after boost
        assert "associate degree" in boosted[0][0].content.lower()
        assert boosted[0][1] > boosted[1][1]

    def test_predicate_overlap_outweighs_name_only_match(self) -> None:
        """Topic words (predicate) should outweigh person-name-only matches.

        For query "What is the age of the brother with an Associate Degree?",
        a turn with "Associate Degree" should outrank a turn with just "brother".
        This is the double-counting predicate boost in action.
        """
        name_only = _make_item("[User] My brother plays tennis.")
        topic_match = _make_item("[User] My cousin has an Associate Degree.")
        items = [
            (name_only, 0.5),
            (topic_match, 0.5),
        ]
        boosted = apply_hybrid_boosts(
            items, "What is the age of the brother with an Associate Degree?"
        )
        # The topic-word match should rank ABOVE the name-only match
        assert "associate degree" in boosted[0][0].content.lower()
