"""
Tests for query parser, templates, and temporal summaries.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from neuromem.core.query import MemoryQuery
from neuromem.memory.templates import apply_template, detect_template, TEMPLATE_NAMES
from neuromem.memory.summaries import TemporalSummarizer
from neuromem.core.types import MemoryItem, MemoryType


class TestQueryParser:
    def test_simple_text_query(self):
        q = MemoryQuery("python frameworks")
        assert q.text_query == "python frameworks"
        assert q.filters == {}

    def test_type_filter(self):
        q = MemoryQuery("type:semantic python")
        assert q.filters["memory_type"] == "semantic"
        assert q.text_query == "python"

    def test_tag_filter(self):
        q = MemoryQuery("tag:topic:ai machine learning")
        assert q.filters["tag_prefix"] == "topic:ai"
        assert q.text_query == "machine learning"

    def test_confidence_filter(self):
        q = MemoryQuery("confidence:>0.8")
        assert q.filters["confidence_op"] == ">"
        assert q.filters["confidence_val"] == 0.8

    def test_date_filters(self):
        q = MemoryQuery("after:2024-01-01 before:2024-12-31")
        assert q.filters["after"] == datetime(2024, 1, 1)
        assert q.filters["before"] == datetime(2024, 12, 31)

    def test_intent_filter(self):
        q = MemoryQuery("intent:preference")
        assert q.filters["intent"] == "preference"

    def test_sentiment_filter(self):
        q = MemoryQuery("sentiment:positive")
        assert q.filters["sentiment"] == "positive"

    def test_exact_phrase(self):
        q = MemoryQuery('"exact phrase" other text')
        assert "exact phrase" in q.exact_phrases
        assert q.text_query == "other text"

    def test_combined_query(self):
        q = MemoryQuery("type:semantic tag:preference confidence:>0.8 after:2024-01-01 python")
        assert q.filters["memory_type"] == "semantic"
        assert q.filters["tag_prefix"] == "preference"
        assert q.filters["confidence_val"] == 0.8
        assert q.text_query == "python"

    def test_empty_query(self):
        q = MemoryQuery("")
        assert q.text_query == ""
        assert q.filters == {}

    def test_filters_only(self):
        q = MemoryQuery("type:episodic intent:question")
        assert q.text_query == ""
        assert q.filters["memory_type"] == "episodic"
        assert q.filters["intent"] == "question"


class TestQueryMatching:
    @pytest.fixture
    def sample_memory(self):
        return MemoryItem(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            content="User likes Python for machine learning",
            embedding=[0.0] * 10,
            memory_type=MemoryType.SEMANTIC,
            salience=0.8,
            confidence=0.9,
            created_at=datetime(2024, 6, 15),
            last_accessed=datetime(2024, 6, 15),
            decay_rate=0.01,
            reinforcement=3,
            inferred=False,
            editable=True,
            tags=["topic:python", "topic:ai", "intent:preference"],
            metadata={"intent": "preference", "sentiment": "positive"},
        )

    def test_type_match(self, sample_memory):
        q = MemoryQuery("type:semantic")
        assert q.matches_memory(sample_memory)

    def test_type_mismatch(self, sample_memory):
        q = MemoryQuery("type:episodic")
        assert not q.matches_memory(sample_memory)

    def test_tag_prefix_match(self, sample_memory):
        q = MemoryQuery("tag:topic:")
        assert q.matches_memory(sample_memory)

    def test_tag_exact_match(self, sample_memory):
        q = MemoryQuery("tag:topic:python")
        assert q.matches_memory(sample_memory)

    def test_confidence_gt(self, sample_memory):
        q = MemoryQuery("confidence:>0.8")
        assert q.matches_memory(sample_memory)

    def test_confidence_lt(self, sample_memory):
        q = MemoryQuery("confidence:<0.5")
        assert not q.matches_memory(sample_memory)

    def test_date_after(self, sample_memory):
        q = MemoryQuery("after:2024-01-01")
        assert q.matches_memory(sample_memory)

    def test_date_before(self, sample_memory):
        q = MemoryQuery("before:2024-01-01")
        assert not q.matches_memory(sample_memory)

    def test_intent_match(self, sample_memory):
        q = MemoryQuery("intent:preference")
        assert q.matches_memory(sample_memory)

    def test_exact_phrase_match(self, sample_memory):
        q = MemoryQuery('"Python for machine"')
        assert q.matches_memory(sample_memory)

    def test_exact_phrase_no_match(self, sample_memory):
        q = MemoryQuery('"Java for testing"')
        assert not q.matches_memory(sample_memory)

    def test_exact_phrase_case_insensitive(self, sample_memory):
        """Exact match should be case-insensitive (Fix 5)."""
        q = MemoryQuery('"PYTHON"')
        assert q.exact_phrases == ["PYTHON"]
        assert q.matches_memory(sample_memory)

    def test_exact_phrase_parsing(self):
        """Verify quoted phrase is extracted correctly."""
        q = MemoryQuery('"PostgreSQL"')
        assert q.exact_phrases == ["PostgreSQL"]
        assert q.text_query == ""

    def test_combined_match(self, sample_memory):
        q = MemoryQuery("type:semantic tag:topic:ai confidence:>0.5")
        assert q.matches_memory(sample_memory)


class TestTemplates:
    def test_template_names_exist(self):
        assert "decision" in TEMPLATE_NAMES
        assert "preference" in TEMPLATE_NAMES
        assert "fact" in TEMPLATE_NAMES
        assert "goal" in TEMPLATE_NAMES
        assert "feedback" in TEMPLATE_NAMES

    def test_apply_decision_template(self):
        result = apply_template("decision", "Use PostgreSQL", "Good choice!")
        assert "Decision:" in result["content"]
        assert "intent:decision" in result["tags"]
        assert result["metadata"]["intent"] == "decision"

    def test_apply_preference_template(self):
        result = apply_template("preference", "I prefer Python", "Noted!")
        assert "Preference:" in result["content"]
        assert result["salience_boost"] > 0

    def test_apply_unknown_template(self):
        result = apply_template("nonexistent", "Hello", "Hi")
        assert "User:" in result["content"]
        assert result["tags"] == []

    def test_detect_preference(self):
        assert detect_template("I prefer using Python") == "preference"

    def test_detect_decision(self):
        assert detect_template("I decided to use PostgreSQL") == "decision"

    def test_detect_goal(self):
        assert (
            detect_template("I am planning to build an ML pipeline and aiming to finish by Friday")
            == "goal"
        )

    def test_detect_feedback(self):
        assert detect_template("My feedback is the API could improve") == "feedback"

    def test_detect_fact(self):
        assert detect_template("My name is Alice and I work at Acme") == "fact"

    def test_detect_general(self):
        assert detect_template("Hello there") == "general"


class TestTemporalSummarizer:
    @pytest.fixture
    def sample_memories(self):
        user_id = str(uuid.uuid4())
        now = datetime.now()
        return [
            MemoryItem(
                id=str(uuid.uuid4()),
                user_id=user_id,
                content=f"Memory {i}",
                embedding=[0.0] * 10,
                memory_type=MemoryType.EPISODIC,
                salience=0.5 + (i * 0.1),
                confidence=0.8,
                created_at=now - timedelta(hours=i),
                last_accessed=now,
                decay_rate=0.05,
                reinforcement=1,
                inferred=False,
                editable=True,
                tags=[f"topic:topic_{i % 3}"],
                metadata={"sentiment": "positive" if i % 2 == 0 else "neutral"},
            )
            for i in range(5)
        ]

    def test_daily_summary(self, sample_memories):
        summarizer = TemporalSummarizer()
        result = summarizer.daily_summary(sample_memories)
        assert "date" in result
        assert result["memory_count"] == 5
        assert "key_topics" in result
        assert "sentiment_distribution" in result
        assert result["avg_salience"] > 0

    def test_daily_summary_empty(self):
        summarizer = TemporalSummarizer()
        result = summarizer.daily_summary([])
        assert result["memory_count"] == 0

    def test_weekly_digest(self, sample_memories):
        summarizer = TemporalSummarizer()
        result = summarizer.weekly_digest(sample_memories)
        assert result["total_memories"] == 5
        assert "daily_counts" in result
        assert "top_topics" in result

    def test_weekly_digest_empty(self):
        summarizer = TemporalSummarizer()
        result = summarizer.weekly_digest([])
        assert result["total_memories"] == 0

    def test_topic_timeline(self, sample_memories):
        summarizer = TemporalSummarizer()
        timeline = summarizer.topic_timeline(sample_memories, "topic:topic_0")
        assert isinstance(timeline, list)
        for entry in timeline:
            assert "date" in entry
            assert "content" in entry


class TestNeuroMemSearch:
    """Integration test for NeuroMem.search()."""

    @pytest.fixture
    def neuromem_instance(self, tmp_path):
        config_content = """
neuromem:
  model:
    embedding: text-embedding-3-large
  storage:
    database:
      type: memory
  memory:
    decay_enabled: true
    consolidation_interval: 10
  async:
    enabled: false
  retrieval:
    hybrid_enabled: false
"""
        config_path = tmp_path / "test.yaml"
        config_path.write_text(config_content)
        from neuromem import NeuroMem

        memory = NeuroMem.from_config(str(config_path), user_id=str(uuid.uuid4()))
        yield memory
        memory.close()

    def test_search_empty(self, neuromem_instance):
        results = neuromem_instance.search("type:semantic python")
        assert results == []

    def test_search_text_only(self, neuromem_instance):
        neuromem_instance.observe("I like Python", "Great!")
        results = neuromem_instance.search("Python")
        assert isinstance(results, list)

    def test_search_filter_only(self, neuromem_instance):
        neuromem_instance.observe("test", "response")
        results = neuromem_instance.search("type:episodic")
        assert isinstance(results, list)

    def test_daily_summary_integration(self, neuromem_instance):
        neuromem_instance.observe("Hello", "Hi there!")
        summary = neuromem_instance.daily_summary()
        assert isinstance(summary, dict)
        assert "memory_count" in summary

    def test_weekly_digest_integration(self, neuromem_instance):
        neuromem_instance.observe("Hello", "Hi there!")
        digest = neuromem_instance.weekly_digest()
        assert isinstance(digest, dict)
        assert "total_memories" in digest

    def test_daily_summary_string_date(self, neuromem_instance):
        """Issue 2: daily_summary must accept string dates."""
        neuromem_instance.observe("Hello", "Hi there!")
        summary = neuromem_instance.daily_summary(date="2026-03-29")
        assert isinstance(summary, dict)
        assert summary["date"] == "2026-03-29"

    def test_weekly_digest_string_date(self, neuromem_instance):
        """Issue 2: weekly_digest must accept string dates."""
        neuromem_instance.observe("Hello", "Hi there!")
        digest = neuromem_instance.weekly_digest(week_start="2026-03-24")
        assert isinstance(digest, dict)
        assert "total_memories" in digest

    def test_get_memories_by_date_string(self, neuromem_instance):
        """Issue 2: controller.get_memories_by_date must accept string dates."""
        neuromem_instance.observe("Hello", "Hi there!")
        memories = neuromem_instance.controller.get_memories_by_date("2026-03-29")
        assert isinstance(memories, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
