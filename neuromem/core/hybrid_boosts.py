"""
Hybrid retrieval boost signals for post-retrieval re-ranking.

Implements four boost signals inspired by MemPalace's hybrid v4 scoring:
1. Keyword overlap — non-stop-word overlap between query and document
2. Quoted phrase — exact substring match for "quoted phrases" in queries
3. Person name — proper noun detection and matching
4. Temporal proximity — date reference parsing and distance-based boosting

Each boost independently increases the score of matching results.
Applied after initial vector similarity ranking to refine ordering.
"""

from __future__ import annotations

import re
import string
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from neuromem import constants

# Common title-case words that are NOT person names
NOT_NAMES = frozenset(
    {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "The",
        "This",
        "That",
        "These",
        "Those",
        "What",
        "When",
        "Where",
        "Which",
        "Who",
        "How",
        "Why",
        "Can",
        "Could",
        "Would",
        "Should",
        "Will",
        "Have",
        "Has",
        "Had",
        "Are",
        "Were",
        "Was",
        "Been",
        "Being",
        "Does",
        "Did",
        "Do",
        "I",
        "My",
        "We",
        "Our",
        "You",
        "Your",
        "He",
        "She",
        "It",
        "They",
        "Their",
        "Its",
        "Also",
        "Just",
        "Very",
        "Really",
        "About",
        "Some",
        "Any",
        "Not",
        "But",
        "And",
        "For",
        "With",
        "From",
        "Into",
    }
)

# Temporal patterns: (regex, days_offset, window_days)
TEMPORAL_PATTERNS: List[Tuple[re.Pattern, int, int]] = [
    (re.compile(r"\byesterday\b", re.I), 1, 1),
    (re.compile(r"\blast\s+week\b", re.I), 7, 3),
    (re.compile(r"\blast\s+month\b", re.I), 30, 10),
    (re.compile(r"\blast\s+year\b", re.I), 365, 30),
    (re.compile(r"\b(\d+)\s+days?\s+ago\b", re.I), None, None),  # group(1) = days
    (re.compile(r"\b(\d+)\s+weeks?\s+ago\b", re.I), None, None),  # group(1) = weeks
    (re.compile(r"\b(\d+)\s+months?\s+ago\b", re.I), None, None),  # group(1) = months
    (re.compile(r"\ba\s+week\s+ago\b", re.I), 7, 3),
    (re.compile(r"\ba\s+month\s+ago\b", re.I), 30, 10),
    (re.compile(r"\ba\s+few\s+days\s+ago\b", re.I), 3, 2),
    (re.compile(r"\ba\s+few\s+weeks\s+ago\b", re.I), 21, 7),
    (re.compile(r"\brecently\b", re.I), 7, 7),
]


def extract_keywords(text: str) -> List[str]:
    """Extract non-stop-word tokens (3+ chars) from text."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in constants.RETRIEVAL_STOP_WORDS]


def extract_quoted_phrases(text: str) -> List[str]:
    """Extract phrases enclosed in single or double quotes."""
    phrases: List[str] = []
    # Double quotes
    phrases.extend(re.findall(r'"([^"]+)"', text))
    # Single quotes (but not apostrophes — require 2+ words)
    for match in re.findall(r"'([^']+)'", text):
        if " " in match.strip():
            phrases.append(match.strip())
    return phrases


def extract_person_names(text: str) -> List[str]:
    """
    Extract likely person names from text.

    Heuristic: capitalized words that aren't common title-case words,
    days, months, or sentence starters.
    """
    words = text.split()
    names: List[str] = []
    for i, word in enumerate(words):
        clean = word.strip(string.punctuation)
        if not clean or len(clean) < 2:
            continue
        if clean[0].isupper() and clean not in NOT_NAMES:
            # Skip sentence-initial words (position 0, or after . ! ?)
            if i == 0:
                continue
            if i > 0 and words[i - 1].rstrip() and words[i - 1].rstrip()[-1] in ".!?":
                continue
            names.append(clean)
    return names


def parse_temporal_offset(text: str) -> Optional[Tuple[int, int]]:
    """
    Parse temporal reference from query text.

    Returns:
        (days_offset, window_days) or None if no temporal reference found.
    """
    for pattern, days_offset, window_days in TEMPORAL_PATTERNS:
        m = pattern.search(text)
        if m:
            if days_offset is not None:
                return (days_offset, window_days)
            # Dynamic patterns with captured group
            try:
                value = int(m.group(1))
            except (IndexError, ValueError):
                continue
            if "week" in pattern.pattern:
                return (value * 7, max(3, value))
            elif "month" in pattern.pattern:
                return (value * 30, max(10, value * 5))
            else:
                return (value, max(1, value // 3))
    return None


def compute_keyword_overlap(query_keywords: List[str], doc_text: str) -> float:
    """Compute fraction of query keywords found in document."""
    if not query_keywords:
        return 0.0
    doc_lower = doc_text.lower()
    hits = sum(1 for kw in query_keywords if kw in doc_lower)
    return hits / len(query_keywords)


def compute_temporal_boost(
    query_text: str,
    doc_timestamp: Optional[str],
    query_date: Optional[datetime] = None,
) -> float:
    """
    Compute temporal proximity boost.

    Returns a value in [0.0, 1.0] based on how close the document's
    timestamp is to the temporal reference in the query.
    """
    offset = parse_temporal_offset(query_text)
    if offset is None or not doc_timestamp:
        return 0.0

    days_offset, window_days = offset
    if query_date is None:
        query_date = datetime.now()

    target_date = query_date - timedelta(days=days_offset)

    # Parse document timestamp
    doc_date = None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d (%a) %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            doc_date = datetime.strptime(doc_timestamp.strip()[:19], fmt)
            break
        except (ValueError, AttributeError):
            continue

    if doc_date is None:
        return 0.0

    delta_days = abs((doc_date - target_date).days)

    if delta_days <= window_days:
        return 1.0
    elif delta_days <= window_days * 3:
        return 1.0 - (delta_days - window_days) / (window_days * 2)
    return 0.0


def apply_hybrid_boosts(
    items_with_scores: List[Tuple[object, float]],
    query_text: str,
    keyword_weight: float = constants.HYBRID_KEYWORD_OVERLAP_WEIGHT,
    quoted_phrase_boost: float = constants.HYBRID_QUOTED_PHRASE_BOOST,
    person_name_boost: float = constants.HYBRID_PERSON_NAME_BOOST,
    temporal_boost_max: float = constants.HYBRID_TEMPORAL_BOOST,
    query_date: Optional[datetime] = None,
) -> List[Tuple[object, float]]:
    """
    Apply hybrid boost signals to re-rank retrieval results.

    Each item is a (MemoryItem, score) tuple. The score is adjusted
    upward based on matching signals, then re-sorted.

    Args:
        items_with_scores: List of (item, score) tuples from initial ranking.
        query_text: The original query text.
        keyword_weight: Weight for keyword overlap boost.
        quoted_phrase_boost: Boost for exact quoted phrase match.
        person_name_boost: Boost for person name match.
        temporal_boost_max: Max boost for temporal proximity.
        query_date: Reference date for temporal queries (defaults to now).

    Returns:
        Re-ranked list of (item, boosted_score) tuples.
    """
    if not items_with_scores or not query_text:
        return items_with_scores

    # Pre-extract signals from query
    keywords = extract_keywords(query_text)
    quoted_phrases = extract_quoted_phrases(query_text)
    person_names = extract_person_names(query_text)

    # Predicate keywords — keywords MINUS person names. This is MemPalace's
    # core MemBench insight: person names appear in many turns (e.g. "my
    # brother ..." appears in 10+ turns per conversation), so they're weak
    # discriminators. The "predicate" words (nouns/verbs naming the fact
    # itself — "degree", "birthday", "occupation", "contact") are the
    # strong signals. Boosting on predicate-only overlap focuses scoring
    # on topic words.
    person_name_lower = {n.lower() for n in person_names}
    predicate_keywords = [kw for kw in keywords if kw not in person_name_lower]

    boosted: List[Tuple[object, float]] = []

    for item, score in items_with_scores:
        content = getattr(item, "content", "")
        metadata = getattr(item, "metadata", {}) or {}
        boost = 0.0

        # Signal 1: Keyword overlap with length-aware scaling.
        # - Long content (500+ chars): linear boost — full weight on overlap.
        # - Short content: linear boost at reduced weight (0.7x). Previous
        #   implementation required >=50% overlap to apply ANY boost on short
        #   content, which zero'd out all MemBench turns (typically ~100-300
        #   chars with 20-40% overlap). That let the cross-encoder dominate
        #   and crushed MemBench recall. Now short turns with moderate overlap
        #   get a proportional boost — matching MemPalace's approach.
        if keywords:
            overlap = compute_keyword_overlap(keywords, content)
            content_len = len(content)
            if content_len >= 500:
                boost += keyword_weight * overlap
            else:
                # Linear but slightly discounted to avoid boosting single-word
                # matches on short distractors. At overlap=0.2 on a 150-char
                # turn, boost = 0.50 * 0.7 * 0.2 = 0.07 — meaningful but not
                # overwhelming.
                boost += keyword_weight * 0.7 * overlap

        # Signal 1b: Predicate-only keyword overlap (MemPalace's trick).
        # Scored separately from full keyword overlap so non-name topic words
        # are double-counted — the SAME topic word gets the base boost AND
        # the predicate boost. This is intentional: it makes topic-word
        # matches dominate over name-only matches in multi-hop queries like
        # "What is the age of someone with an Associate Degree?" where the
        # answer turn contains "Associate Degree" but no name from the query.
        if predicate_keywords and predicate_keywords != keywords:
            pred_overlap = compute_keyword_overlap(predicate_keywords, content)
            if pred_overlap > 0:
                # Half the base keyword weight, applied universally regardless
                # of content length. At weight 0.25 and pred_overlap=0.5,
                # adds 0.125 to score — a meaningful but bounded signal.
                boost += (keyword_weight * 0.5) * pred_overlap

        # Signal 2: Quoted phrase exact match
        if quoted_phrases:
            content_lower = content.lower()
            for phrase in quoted_phrases:
                if phrase.lower() in content_lower:
                    boost += quoted_phrase_boost
                    break  # One match is enough

        # Signal 3: Person name match
        if person_names:
            content_lower = content.lower()
            for name in person_names:
                if name.lower() in content_lower:
                    boost += person_name_boost
                    break

        # Signal 4: Temporal proximity
        if temporal_boost_max > 0:
            timestamp = metadata.get("timestamp", metadata.get("date", ""))
            if timestamp:
                t_boost = compute_temporal_boost(query_text, timestamp, query_date)
                boost += temporal_boost_max * t_boost

        # Apply boost to score (capped at 1.0)
        new_score = min(1.0, score + boost)
        boosted.append((item, new_score))

    # Re-sort by boosted score descending
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted
