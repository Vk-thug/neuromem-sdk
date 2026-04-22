"""
Local topic detection for metadata filtering.

Assigns one of ~20 topics to text content using keyword signal matching.
No LLM required — fast regex/keyword heuristics run in <1ms.

Topics are used for domain partitioning in retrieval: filtering to
relevant topics BEFORE vector search reduces noise and improves recall.
"""

from __future__ import annotations

# Topic → keyword signals (lowercase). Matched against content.
TOPIC_SIGNALS: dict[str, list[str]] = {
    "career_education": [
        "job",
        "work",
        "career",
        "office",
        "boss",
        "colleague",
        "promotion",
        "salary",
        "interview",
        "resume",
        "school",
        "university",
        "degree",
        "study",
        "class",
        "professor",
        "graduate",
        "intern",
        "major",
    ],
    "health_wellness": [
        "health",
        "doctor",
        "hospital",
        "medicine",
        "exercise",
        "gym",
        "yoga",
        "meditation",
        "therapy",
        "diet",
        "sleep",
        "mental health",
        "anxiety",
        "depression",
        "workout",
        "fitness",
        "vaccine",
        "surgery",
    ],
    "relationships": [
        "friend",
        "partner",
        "spouse",
        "husband",
        "wife",
        "girlfriend",
        "boyfriend",
        "dating",
        "relationship",
        "marriage",
        "wedding",
        "divorce",
        "family",
        "parent",
        "mother",
        "father",
        "sibling",
        "brother",
        "sister",
        "child",
        "kids",
        "baby",
    ],
    "hobbies_interests": [
        "hobby",
        "music",
        "art",
        "painting",
        "drawing",
        "guitar",
        "piano",
        "reading",
        "book",
        "movie",
        "film",
        "game",
        "sport",
        "hiking",
        "cooking",
        "baking",
        "gardening",
        "photography",
        "dance",
        "singing",
    ],
    "travel": [
        "travel",
        "trip",
        "vacation",
        "flight",
        "hotel",
        "airport",
        "country",
        "city",
        "beach",
        "mountain",
        "tourist",
        "passport",
        "visited",
        "abroad",
        "destination",
    ],
    "food_cooking": [
        "food",
        "restaurant",
        "recipe",
        "cook",
        "meal",
        "dinner",
        "lunch",
        "breakfast",
        "cuisine",
        "ingredient",
        "dessert",
        "coffee",
        "tea",
        "vegan",
        "vegetarian",
        "allergy",
    ],
    "technology": [
        "computer",
        "software",
        "code",
        "programming",
        "app",
        "website",
        "phone",
        "laptop",
        "internet",
        "database",
        "server",
        "cloud",
        "algorithm",
        "api",
        "machine learning",
        "ai",
    ],
    "finance": [
        "money",
        "budget",
        "savings",
        "investment",
        "stock",
        "bank",
        "mortgage",
        "rent",
        "tax",
        "insurance",
        "retirement",
        "crypto",
        "loan",
        "debt",
        "credit",
    ],
    "home_living": [
        "home",
        "house",
        "apartment",
        "room",
        "furniture",
        "decor",
        "renovation",
        "move",
        "neighbor",
        "landlord",
        "garden",
        "pet",
        "dog",
        "cat",
    ],
    "emotions_personal": [
        "feel",
        "feeling",
        "happy",
        "sad",
        "angry",
        "stressed",
        "excited",
        "worried",
        "afraid",
        "lonely",
        "grateful",
        "frustrated",
        "confused",
        "proud",
        "embarrassed",
        "overwhelmed",
    ],
    "preferences": [
        "prefer",
        "favorite",
        "like",
        "love",
        "enjoy",
        "hate",
        "dislike",
        "rather",
        "instead",
        "better",
        "best",
        "worst",
    ],
    "identity": [
        "my name",
        "i am",
        "i'm",
        "born in",
        "grew up",
        "nationality",
        "religion",
        "gender",
        "age",
        "birthday",
        "zodiac",
    ],
}


def detect_topic(text: str) -> str:
    """
    Detect the primary topic of a text using keyword signals.

    Args:
        text: Content to classify.

    Returns:
        Topic string (one of TOPIC_SIGNALS keys, or "general").
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for topic, keywords in TOPIC_SIGNALS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score

    if not scores:
        return "general"

    return max(scores, key=scores.get)


def detect_topics(text: str, max_topics: int = 3) -> list[str]:
    """
    Detect top N topics for a text (for multi-topic content).

    Args:
        text: Content to classify.
        max_topics: Maximum number of topics to return.

    Returns:
        List of topic strings, most relevant first.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for topic, keywords in TOPIC_SIGNALS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score

    if not scores:
        return ["general"]

    sorted_topics = sorted(scores, key=scores.get, reverse=True)
    return sorted_topics[:max_topics]
