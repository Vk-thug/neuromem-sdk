"""
Session memory for NeuroMem.

Stores the current conversation context in RAM.
"""

from typing import List, Tuple
from collections import deque


class SessionMemory:
    """
    Session memory - current conversation context.

    This is ephemeral memory that exists only for the current session.
    It's similar to working memory in the brain.
    """

    def __init__(self, backend=None, user_id: str = None, max_turns: int = 20):
        """
        Initialize session memory.

        Args:
            backend: Storage backend (e.g., PostgresBackend)
            user_id: User ID for persistence
            max_turns: Maximum number of conversation turns to keep in RAM
        """
        self.backend = backend
        self.user_id = user_id
        self.max_turns = max_turns
        self.turns: deque = deque(maxlen=max_turns)

    def add_turn(self, user_input: str, assistant_output: str):
        """
        Add a conversation turn.

        Args:
            user_input: What the user said
            assistant_output: What the assistant responded
        """
        self.turns.append({"user": user_input, "assistant": assistant_output})

        # Persist to backend if available
        if self.backend and self.user_id and hasattr(self.backend, "add_history"):
            try:
                self.backend.add_history(self.user_id, "user", user_input)
                self.backend.add_history(self.user_id, "assistant", assistant_output)
            except Exception as e:
                print(f"⚠️ Failed to persist session history: {e}")

    def get_context(self, last_n: int = None) -> List[Tuple[str, str]]:
        """
        Get conversation context.

        Args:
            last_n: Number of recent turns to get (default: all)

        Returns:
            List of (user_input, assistant_output) tuples
        """
        turns = list(self.turns)

        if last_n:
            turns = turns[-last_n:]

        return [(turn["user"], turn["assistant"]) for turn in turns]

    def get_formatted_context(self, last_n: int = None) -> str:
        """
        Get formatted conversation context as a string.

        Args:
            last_n: Number of recent turns to get

        Returns:
            Formatted conversation history
        """
        context = self.get_context(last_n)

        formatted = []
        for user_input, assistant_output in context:
            formatted.append(f"User: {user_input}")
            formatted.append(f"Assistant: {assistant_output}")

        return "\n".join(formatted)

    def clear(self):
        """Clear session memory."""
        self.turns.clear()

    def is_empty(self) -> bool:
        """Check if session memory is empty."""
        return len(self.turns) == 0
