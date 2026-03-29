"""
Memory query parser for NeuroMem.

Provides Obsidian-like structured query syntax for searching memories.

Syntax:
    type:semantic                    -> filter by memory type
    tag:topic:ai                     -> filter by tag prefix
    confidence:>0.8                  -> numeric comparison
    after:2024-01-01                 -> date filter
    before:2024-12-31                -> date filter
    intent:preference                -> property filter
    sentiment:positive               -> property filter
    "exact phrase"                   -> exact text match in content
    remaining text                   -> embedding similarity search

Example:
    'type:semantic tag:preference confidence:>0.8 python frameworks'
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Operator patterns
_OPERATOR_RE = re.compile(
    r"(type|tag|confidence|salience|after|before|intent|sentiment|source):(\S+)"
)
_QUOTED_RE = re.compile(r'"([^"]+)"')
_NUMERIC_CMP_RE = re.compile(r"^([><]=?)?(\d+\.?\d*)$")


class MemoryQuery:
    """
    Parse structured memory queries into filters + text query.

    Usage:
        query = MemoryQuery('type:semantic tag:preference after:2024-01-01 python')
        print(query.filters)     # {'memory_type': 'semantic', 'tag_prefix': 'preference', ...}
        print(query.text_query)  # 'python'
    """

    def __init__(self, query_string: str):
        self.raw = query_string.strip()
        self.filters: Dict[str, Any] = {}
        self.text_query: str = ""
        self.exact_phrases: List[str] = []
        self._parse()

    def _parse(self) -> None:
        """Parse query string into structured filters + text query."""
        remaining = self.raw

        # Extract quoted exact phrases first
        for match in _QUOTED_RE.finditer(remaining):
            self.exact_phrases.append(match.group(1))
        remaining = _QUOTED_RE.sub("", remaining)

        # Extract operator:value pairs
        for match in _OPERATOR_RE.finditer(remaining):
            operator = match.group(1)
            value = match.group(2)
            self._apply_operator(operator, value)
        remaining = _OPERATOR_RE.sub("", remaining)

        # Whatever is left is the text query for embedding search
        self.text_query = " ".join(remaining.split()).strip()

    def _apply_operator(self, operator: str, value: str) -> None:
        """Apply a single operator:value pair to filters."""
        if operator == "type":
            self.filters["memory_type"] = value

        elif operator == "tag":
            self.filters["tag_prefix"] = value

        elif operator == "confidence":
            parsed = self._parse_numeric_comparison(value)
            if parsed:
                self.filters["confidence_op"] = parsed[0]
                self.filters["confidence_val"] = parsed[1]

        elif operator == "salience":
            parsed = self._parse_numeric_comparison(value)
            if parsed:
                self.filters["salience_op"] = parsed[0]
                self.filters["salience_val"] = parsed[1]

        elif operator == "after":
            try:
                self.filters["after"] = datetime.fromisoformat(value)
            except ValueError:
                logger.warning(f"Invalid date format for 'after': {value}")

        elif operator == "before":
            try:
                self.filters["before"] = datetime.fromisoformat(value)
            except ValueError:
                logger.warning(f"Invalid date format for 'before': {value}")

        elif operator == "intent":
            self.filters["intent"] = value

        elif operator == "sentiment":
            self.filters["sentiment"] = value

        elif operator == "source":
            self.filters["source"] = value

    @staticmethod
    def _parse_numeric_comparison(value: str) -> Optional[tuple]:
        """Parse a numeric comparison like '>0.8', '>=0.5', '0.7'."""
        match = _NUMERIC_CMP_RE.match(value)
        if match:
            op = match.group(1) or "=="
            num = float(match.group(2))
            return (op, num)
        return None

    def matches_memory(self, memory: Any) -> bool:
        """
        Check if a memory item matches the parsed query filters.

        Args:
            memory: MemoryItem to check

        Returns:
            True if memory matches all filters
        """
        # Type filter
        if "memory_type" in self.filters:
            mem_type = (
                memory.memory_type.value
                if hasattr(memory.memory_type, "value")
                else str(memory.memory_type)
            )
            if mem_type != self.filters["memory_type"]:
                return False

        # Tag prefix filter
        if "tag_prefix" in self.filters:
            prefix = self.filters["tag_prefix"]
            if not any(t.startswith(prefix) for t in memory.tags):
                return False

        # Confidence filter
        if "confidence_op" in self.filters:
            if not self._compare(
                memory.confidence, self.filters["confidence_op"], self.filters["confidence_val"]
            ):
                return False

        # Salience filter
        if "salience_op" in self.filters:
            if not self._compare(
                memory.salience, self.filters["salience_op"], self.filters["salience_val"]
            ):
                return False

        # Date filters
        if "after" in self.filters:
            if memory.created_at < self.filters["after"]:
                return False
        if "before" in self.filters:
            if memory.created_at >= self.filters["before"]:
                return False

        # Intent filter (from metadata)
        if "intent" in self.filters:
            mem_intent = memory.metadata.get("intent", "")
            if mem_intent != self.filters["intent"]:
                return False

        # Sentiment filter (from metadata)
        if "sentiment" in self.filters:
            mem_sentiment = memory.metadata.get("sentiment", "")
            if mem_sentiment != self.filters["sentiment"]:
                return False

        # Exact phrase filter
        for phrase in self.exact_phrases:
            if phrase.lower() not in memory.content.lower():
                return False

        return True

    @staticmethod
    def _compare(value: float, op: str, threshold: float) -> bool:
        """Apply a numeric comparison."""
        if op == ">":
            return value > threshold
        elif op == ">=":
            return value >= threshold
        elif op == "<":
            return value < threshold
        elif op == "<=":
            return value <= threshold
        elif op == "==":
            return abs(value - threshold) < 0.001
        return True
