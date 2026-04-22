"""
Query expansion for broader semantic recall.

When a query is short or uses uncommon vocabulary, single-shot embedding
retrieval may miss the right answer because the embedding doesn't activate
the same regions as the document. Query expansion mitigates this by:

1. Generating multiple paraphrases of the query
2. Embedding each paraphrase separately
3. Averaging the embeddings (or pooling results)

For benchmark mode, we use HEURISTIC expansion (no LLM) to keep latency low.

Special handling for AGGREGATIVE queries ("how many X"): generate variations
that match individual instances of X, since the count requires finding
multiple separate sessions each mentioning X.
"""

from __future__ import annotations

import re
from typing import List, Tuple


def is_conditional_query(query: str) -> bool:
    """
    Detect 2-hop conditional queries like:
      "What is X of someone who has Y=Z?"
      "What is X of the person with Y?"
      "What is X for someone whose Y is Z?"
      "What X does someone with Y have?"

    These need 2-hop retrieval: find the entity matching the constraint,
    then find the target attribute of that entity.
    """
    if not query:
        return False
    q = query.lower().strip()
    # Must start with a question word
    if not q.startswith(("what ", "who ", "where ", "when ", "how ", "which ")):
        return False
    # Must contain an entity-relation pattern
    patterns = (
        "of someone",
        "of the person",
        "of the one",
        "for someone",
        "for the person",
        "for the one",
        "whose ",
        "of the individual",
        "does someone",
        "does the person",
        "does the one",
        "the person who",
        "someone who",
        "someone with",
        "person with",
    )
    return any(p in q for p in patterns)


def split_conditional_query(query: str) -> Tuple[str, str]:
    """
    Split a 2-hop conditional query into (target_attribute, constraint).

    Examples:
      "What is the contact number for the person with a PhD in education?"
        -> ("contact number", "PhD in education")

      "What position does someone who has rock climbing as a hobby hold?"
        -> ("position", "rock climbing as a hobby")

    Returns (target, constraint). If split fails, returns (query, query).
    """
    q = query.strip().rstrip("?")

    # Pattern 1: "What is the X of/for someone/person with Y"
    m = re.search(
        r"what\s+is\s+(?:the\s+)?(.+?)\s+(?:of|for)\s+(?:someone|the\s+person|the\s+one|the\s+individual)\s*(?:who\s+)?(?:has|with|whose|is)\s+(.+)",
        q,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Pattern 2: "What X does someone with Y have/do/hold"
    m = re.search(
        r"what\s+(.+?)\s+does\s+(?:someone|the\s+person)\s+(?:who\s+)?(?:has|with)\s+(.+?)(?:\s+(?:have|do|hold|own))?$",
        q,
        re.IGNORECASE,
    )
    if m:
        target = m.group(1).strip()
        constraint = m.group(2).strip()
        return target, constraint

    return query, query


# Question-type heuristics (regex pattern -> list of paraphrase templates)
QUESTION_PATTERNS: list = [
    # "What X did Y..." -> "Y X", "Y had X"
    (
        re.compile(r"what\s+(\w+)\s+(?:did|do|does|has|have)\s+(\w+)", re.I),
        ["{1} {0}", "{1} has {0}", "{1}'s {0}"],
    ),
    # "What is the X of Y?" -> "Y X", "Y has X"
    (
        re.compile(r"what\s+is\s+(?:the\s+)?(\w+)\s+of\s+(\w+)", re.I),
        ["{1} {0}", "{1} {0} is", "{1}'s {0}"],
    ),
    # "Where did I X?" -> "I X at", "the place where I X"
    (
        re.compile(r"where\s+did\s+(?:i|you)\s+(\w+)", re.I),
        ["{0} at", "I {0} at", "the place I {0}"],
    ),
    # "How X is my Y?" -> "my Y X"
    (
        re.compile(r"how\s+(\w+)\s+is\s+my\s+(\w+)", re.I),
        ["my {1} {0}", "my {1}'s {0}", "{1} {0}"],
    ),
    # "When did I X?" -> "I X on", "I X at"
    (
        re.compile(r"when\s+did\s+(?:i|you)\s+(\w+)", re.I),
        ["I {0} on", "I {0} at", "the day I {0}"],
    ),
    # "Who X my Y?" -> "my Y was X by"
    (
        re.compile(r"who\s+(\w+)\s+my\s+(\w+)", re.I),
        ["my {1} {0}", "{0} my {1}"],
    ),
]


def is_aggregative_query(query: str) -> bool:
    """
    Detect if a query is asking for a COUNT or aggregation across items.

    Aggregative queries like "how many X" need BREADTH in retrieval
    (multiple matching sessions) rather than DEPTH (one best answer).

    Note: "how much time" is NOT aggregative — it asks for a single duration.
    "how many X" IS aggregative — needs counting across sessions.
    """
    if not query:
        return False
    q = query.lower().strip()
    # Strong aggregative patterns — these definitely need breadth
    strong_patterns = (
        "how many",
        "how often",
        "how frequently",
        "count of",
        "number of",
        "total number",
        "list all",
        "list everything",
        "every time",
        "each time",
    )
    if any(p in q for p in strong_patterns):
        # Exclude "how many X do I need" type questions (single-answer)
        if "how many" in q and ("do i need" in q or "should i" in q):
            return False
        return True
    return False


def expand_aggregative_query(query: str) -> List[str]:
    """
    Expand an aggregative query into variations that match individual
    instances. For example:

      "How many projects have I led?" ->
        - "How many projects have I led?"          (original)
        - "a project I am leading"                 (singular instance)
        - "working on a project"                   (activity)
        - "leading a project"                      (activity + keyword)

      "How many doctors did I visit?" ->
        - "How many doctors did I visit?"          (original)
        - "visiting a doctor"
        - "my doctor appointment"
        - "saw a doctor"
    """
    if not query:
        return [query]

    q = query.strip()
    q_lower = q.lower()
    expansions = [q]
    seen = {q_lower}

    # Pattern 1: "How many X did I Y?" -> "a X I Y", "X Y"
    import re

    m = re.search(
        r"how many (\w+(?:\s+\w+)?)\s+(?:have|has|did|do|does|are)\s+(?:i|we|you)\s+(\w+)", q_lower
    )
    if m:
        noun, verb = m.groups()
        for exp in [f"a {noun} I {verb}", f"{verb} a {noun}", f"my {noun}"]:
            if exp not in seen:
                expansions.append(exp)
                seen.add(exp)

    # Pattern 2: "How many X" without verb -> "X I had", "my X"
    m2 = re.search(r"how many (\w+(?:\s+\w+)?)\s*(?:am|are|is|was)?", q_lower)
    if m2:
        noun = m2.group(1)
        for exp in [f"my {noun}", f"a {noun}", f"{noun} I had"]:
            if exp not in seen:
                expansions.append(exp)
                seen.add(exp)

    return expansions[:5]


def expand_query(query: str, max_expansions: int = 3) -> List[str]:
    """
    Generate paraphrases of a query for query expansion.

    Returns the original query first, followed by up to max_expansions
    heuristic paraphrases. The total list (original + expansions) can
    be embedded individually and merged for retrieval.

    Args:
        query: Original query string.
        max_expansions: Maximum number of paraphrases to generate.

    Returns:
        List with the original query first, then heuristic expansions.
    """
    expansions: List[str] = [query]
    seen = {query.lower().strip()}

    for pattern, templates in QUESTION_PATTERNS:
        match = pattern.search(query)
        if match:
            groups = match.groups()
            for template in templates:
                try:
                    expanded = template.format(*groups)
                    norm = expanded.lower().strip()
                    if norm and norm not in seen:
                        expansions.append(expanded)
                        seen.add(norm)
                        if len(expansions) > max_expansions:
                            return expansions
                except (IndexError, KeyError):
                    continue

    return expansions


def average_embeddings(embeddings: List[List[float]]) -> List[float]:
    """Average a list of embedding vectors."""
    if not embeddings:
        return []
    if len(embeddings) == 1:
        return embeddings[0]

    dim = len(embeddings[0])
    averaged = [0.0] * dim
    for emb in embeddings:
        for i, val in enumerate(emb):
            averaged[i] += val

    n = len(embeddings)
    return [v / n for v in averaged]
