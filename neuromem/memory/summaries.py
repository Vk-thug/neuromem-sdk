"""
Temporal memory summaries for NeuroMem.

Generates time-based memory summaries like Obsidian's Daily Notes
concept but for AI agent memory.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import Counter
from neuromem.core.types import MemoryItem
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


class TemporalSummarizer:
    """
    Generate time-based memory summaries.

    Provides daily and weekly digests with topic analysis,
    sentiment distribution, and key facts extraction.
    """

    def daily_summary(
        self, memories: List[MemoryItem], date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a daily summary from memories.

        Args:
            memories: List of memories for the day
            date: Date for the summary (defaults to today)

        Returns:
            Summary dict with topics, facts, sentiment, etc.
        """
        if date is None:
            date = datetime.now(timezone.utc)

        date_str = date.strftime("%Y-%m-%d")

        if not memories:
            return {
                "date": date_str,
                "summary": "No memories recorded.",
                "memory_count": 0,
                "key_topics": [],
                "sentiment_distribution": {},
            }

        # Extract topics from tags
        all_tags = []
        for mem in memories:
            all_tags.extend(mem.tags)
        topic_tags = [t for t in all_tags if t.startswith("topic:")]
        topic_counts = Counter(topic_tags)
        key_topics = [t.replace("topic:", "") for t, _ in topic_counts.most_common(5)]

        # Sentiment distribution
        sentiments = []
        for mem in memories:
            sent = mem.metadata.get("sentiment", "neutral")
            if isinstance(sent, dict):
                sent = sent.get("sentiment", "neutral")
            sentiments.append(sent or "neutral")
        sentiment_dist = dict(Counter(sentiments))

        # Intent distribution
        intents = []
        for mem in memories:
            intent = mem.metadata.get("intent", "unknown")
            intents.append(intent or "unknown")
        intent_dist = dict(Counter(intents))

        # High-salience facts
        high_salience = sorted(memories, key=lambda m: m.salience, reverse=True)
        key_facts = [m.content[:100] for m in high_salience[:3]]

        # Simple heuristic summary
        summary = f"Recorded {len(memories)} memories"
        if key_topics:
            summary += f" about {', '.join(key_topics[:3])}"
        summary += "."

        return {
            "date": date_str,
            "summary": summary,
            "memory_count": len(memories),
            "key_topics": key_topics,
            "key_facts": key_facts,
            "sentiment_distribution": sentiment_dist,
            "intent_distribution": intent_dist,
            "avg_salience": sum(m.salience for m in memories) / len(memories),
            "avg_confidence": sum(m.confidence for m in memories) / len(memories),
        }

    def weekly_digest(
        self,
        memories: List[MemoryItem],
        week_start: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate a weekly digest with trend analysis.

        Args:
            memories: List of memories for the week
            week_start: Start of the week (defaults to current week)

        Returns:
            Weekly digest with daily breakdown and trends
        """
        if week_start is None:
            now = datetime.now(timezone.utc)
            week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if not memories:
            return {
                "week_start": week_start.strftime("%Y-%m-%d"),
                "total_memories": 0,
                "daily_counts": {},
                "top_topics": [],
                "summary": "No memories recorded this week.",
            }

        # Group by day
        daily_groups: Dict[str, List[MemoryItem]] = {}
        for mem in memories:
            day_key = mem.created_at.strftime("%Y-%m-%d")
            if day_key not in daily_groups:
                daily_groups[day_key] = []
            daily_groups[day_key].append(mem)

        daily_counts = {day: len(mems) for day, mems in daily_groups.items()}

        # Top topics across the week
        all_tags = []
        for mem in memories:
            all_tags.extend(t for t in mem.tags if t.startswith("topic:"))
        topic_counts = Counter(all_tags)
        top_topics = [t.replace("topic:", "") for t, _ in topic_counts.most_common(5)]

        # Most active day
        most_active_day = max(daily_counts, key=daily_counts.get) if daily_counts else "N/A"

        summary = f"Week of {week_start.strftime('%Y-%m-%d')}: {len(memories)} total memories across {len(daily_groups)} days."
        if top_topics:
            summary += f" Top topics: {', '.join(top_topics[:3])}."

        return {
            "week_start": week_start.strftime("%Y-%m-%d"),
            "total_memories": len(memories),
            "daily_counts": daily_counts,
            "top_topics": top_topics,
            "most_active_day": most_active_day,
            "summary": summary,
        }

    def topic_timeline(self, memories: List[MemoryItem], topic_prefix: str) -> List[Dict[str, Any]]:
        """
        Timeline of memories about a specific topic.

        Args:
            memories: All memories to filter
            topic_prefix: Topic tag prefix (e.g., 'topic:ai')

        Returns:
            List of timeline entries sorted by date
        """
        matching = [m for m in memories if any(t.startswith(topic_prefix) for t in m.tags)]

        matching.sort(key=lambda m: m.created_at)

        return [
            {
                "date": m.created_at.strftime("%Y-%m-%d %H:%M"),
                "content": m.content[:150],
                "salience": m.salience,
                "memory_type": (
                    m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
                ),
            }
            for m in matching
        ]
