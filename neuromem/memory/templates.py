"""
Memory templates for NeuroMem.

Structured observation templates for different interaction types,
like Obsidian's Templates but for AI agent observations.
"""

from typing import Dict, Any, List

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "decision": {
        "content_format": "Decision: {user_input}\nReason: {assistant_output}",
        "default_salience": 0.8,
        "default_tags": ["intent:decision"],
        "default_metadata": {"intent": "decision", "fact_type": "knowledge"},
    },
    "preference": {
        "content_format": "Preference: {user_input}\nAcknowledged: {assistant_output}",
        "default_salience": 0.9,
        "default_tags": ["intent:preference"],
        "default_metadata": {"intent": "preference", "fact_type": "preference"},
    },
    "fact": {
        "content_format": "Fact: {user_input}\nContext: {assistant_output}",
        "default_salience": 0.7,
        "default_tags": ["intent:statement"],
        "default_metadata": {"intent": "statement", "fact_type": "knowledge"},
    },
    "goal": {
        "content_format": "Goal: {user_input}\nPlan: {assistant_output}",
        "default_salience": 0.85,
        "default_tags": ["intent:goal"],
        "default_metadata": {"intent": "goal", "fact_type": "goal"},
    },
    "feedback": {
        "content_format": "Feedback: {user_input}\nResponse: {assistant_output}",
        "default_salience": 0.75,
        "default_tags": ["intent:feedback"],
        "default_metadata": {"intent": "feedback"},
    },
}

# Keywords for auto-detecting template type
_DETECTION_KEYWORDS: Dict[str, List[str]] = {
    "decision": ["decided", "chose", "picked", "going with", "settled on", "i'll go with"],
    "preference": ["prefer", "like", "want", "love", "hate", "favorite", "rather"],
    "goal": ["want to", "planning to", "goal is", "aiming to", "trying to", "need to"],
    "feedback": ["feedback", "suggestion", "improve", "better if", "would be nice", "complaint"],
    "fact": ["my name is", "i am", "i work", "i live", "i have", "i use"],
}

TEMPLATE_NAMES = list(TEMPLATES.keys())


def apply_template(
    template_name: str,
    user_input: str,
    assistant_output: str,
) -> Dict[str, Any]:
    """
    Apply a template to an observation.

    Args:
        template_name: Template name (decision, preference, fact, goal, feedback)
        user_input: User's message
        assistant_output: Assistant's response

    Returns:
        Dict with content, salience, tags, metadata shaped by the template
    """
    template = TEMPLATES.get(template_name)
    if not template:
        # Fallback to generic format
        return {
            "content": f"User: {user_input}\nAssistant: {assistant_output}",
            "salience_boost": 0.0,
            "tags": [],
            "metadata": {},
        }

    return {
        "content": template["content_format"].format(
            user_input=user_input, assistant_output=assistant_output
        ),
        "salience_boost": template["default_salience"] - 0.5,  # Boost above base
        "tags": list(template["default_tags"]),
        "metadata": dict(template["default_metadata"]),
    }


def detect_template(user_input: str) -> str:
    """
    Auto-detect which template fits the user input.

    Args:
        user_input: User's message

    Returns:
        Template name or 'general' if no match
    """
    input_lower = user_input.lower()

    best_match = "general"
    best_score = 0

    for template_name, keywords in _DETECTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in input_lower)
        if score > best_score:
            best_score = score
            best_match = template_name

    return best_match
