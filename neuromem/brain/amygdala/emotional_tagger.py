"""
Amygdala — Emotional Tagging and Flashbulb Memory.

The amygdala modulates hippocampal encoding strength via norepinephrine
and beta-adrenergic receptor activation. High-arousal events receive
stronger initial encoding, priority in replay consolidation, and
resistance to decay (flashbulb memories).

Algorithm:
1. Compute arousal score from content (lexicon-based, fast)
2. Compute valence score (positive/negative polarity)
3. Calculate emotional_weight = arousal * (0.5 + 0.5 * |valence|)
4. If arousal > flashbulb_threshold → pin salience to 1.0, set decay_rate ≈ 0

Reference: McGaugh (2004), "The amygdala modulates the consolidation
of memories of emotionally arousing experiences"
"""

from __future__ import annotations

from typing import Dict

from neuromem.constants import (
    DEFAULT_FLASHBULB_AROUSAL_THRESHOLD,
    HIGH_AROUSAL_WORDS,
    LOW_AROUSAL_WORDS,
    PREFERENCE_KEYWORDS,
)

# Valence lexicons (lightweight, no external deps)
_POSITIVE_WORDS = frozenset(
    {
        "love",
        "great",
        "amazing",
        "wonderful",
        "excellent",
        "happy",
        "joy",
        "fantastic",
        "brilliant",
        "beautiful",
        "perfect",
        "best",
        "awesome",
        "incredible",
        "won",
        "success",
        "promoted",
        "breakthrough",
        "celebrate",
        "grateful",
        "proud",
        "excited",
        "thrilled",
        "delighted",
    }
)

_NEGATIVE_WORDS = frozenset(
    {
        "hate",
        "terrible",
        "awful",
        "horrible",
        "worst",
        "angry",
        "sad",
        "disgusting",
        "failed",
        "disaster",
        "lost",
        "fired",
        "dead",
        "death",
        "killed",
        "accident",
        "crash",
        "broken",
        "pain",
        "suffering",
        "fear",
        "terrified",
        "depressed",
        "anxious",
        "devastated",
    }
)


class EmotionalTagger:
    """Amygdala-inspired emotional modulation of memory encoding.

    Parameters
    ----------
    flashbulb_threshold:
        Arousal score above which a memory becomes a "flashbulb" — pinned
        salience, near-zero decay. Default 0.8.
    """

    def __init__(
        self,
        flashbulb_threshold: float = DEFAULT_FLASHBULB_AROUSAL_THRESHOLD,
    ) -> None:
        self.flashbulb_threshold = flashbulb_threshold

    def tag(self, content: str, base_salience: float = 0.5) -> Dict[str, float | bool]:
        """Compute emotional metadata for a memory.

        Parameters
        ----------
        content:
            The memory text content to analyze.
        base_salience:
            The salience score computed by the existing SalienceCalculator.

        Returns
        -------
        Dict with keys: arousal, valence, emotional_weight, flashbulb,
        adjusted_salience, adjusted_decay_rate.
        """
        words = set(content.lower().split())

        # Arousal: proportion of high-arousal words (capped at 1.0)
        high_count = len(words & HIGH_AROUSAL_WORDS)
        low_count = len(words & LOW_AROUSAL_WORDS)
        word_count = max(len(words), 1)
        arousal = min(1.0, (high_count * 3 - low_count) / max(word_count, 5))
        arousal = max(0.0, arousal)

        # Boost arousal for exclamation marks and ALL CAPS words
        exclamation_count = content.count("!")
        caps_words = sum(1 for w in content.split() if w.isupper() and len(w) > 1)
        arousal = min(1.0, arousal + exclamation_count * 0.1 + caps_words * 0.05)

        # Valence: positive vs negative polarity [-1, +1]
        pos_count = len(words & _POSITIVE_WORDS) + len(words & set(PREFERENCE_KEYWORDS))
        neg_count = len(words & _NEGATIVE_WORDS)
        if pos_count + neg_count > 0:
            valence = (pos_count - neg_count) / (pos_count + neg_count)
        else:
            valence = 0.0

        # Emotional weight: arousal modulated by valence intensity
        emotional_weight = arousal * (0.5 + 0.5 * abs(valence))

        # Flashbulb detection
        flashbulb = arousal >= self.flashbulb_threshold

        # Adjust salience and decay based on emotional tagging
        if flashbulb:
            adjusted_salience = 1.0
            adjusted_decay_rate = 0.001  # Near-zero: flashbulb memories persist
        else:
            # Emotional memories get salience boost proportional to arousal
            salience_boost = emotional_weight * 0.3
            adjusted_salience = min(1.0, base_salience + salience_boost)
            adjusted_decay_rate = None  # Use default decay rate

        return {
            "arousal": round(arousal, 4),
            "valence": round(valence, 4),
            "emotional_weight": round(emotional_weight, 4),
            "flashbulb": flashbulb,
            "adjusted_salience": round(adjusted_salience, 4),
            "adjusted_decay_rate": adjusted_decay_rate,
        }
