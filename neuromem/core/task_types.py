"""
Task type definitions for priority-based scheduling.
"""

from enum import IntEnum, Enum
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


class TaskPriority(IntEnum):
    """Priority levels for task scheduling (lower = higher priority)"""

    CRITICAL = 1  # observe (user-facing latency)
    HIGH = 2  # retrieval optimization
    MEDIUM = 3  # consolidation
    LOW = 4  # re-embedding
    BACKGROUND = 5  # decay, cleanup


class TaskType(Enum):
    """Task types with their default priorities"""

    OBSERVE = ("observe", TaskPriority.CRITICAL)
    CONSOLIDATE = ("consolidate", TaskPriority.MEDIUM)
    OPTIMIZE = ("optimize", TaskPriority.LOW)
    DECAY = ("decay", TaskPriority.BACKGROUND)
    RECONSOLIDATE = ("reconsolidate", TaskPriority.HIGH)
    # Brain system tasks (v0.3.0)
    RIPPLE_REPLAY = ("ripple_replay", TaskPriority.BACKGROUND)
    TD_UPDATE = ("td_update", TaskPriority.LOW)
    MULTIMODAL_ENCODE = ("multimodal_encode", TaskPriority.HIGH)

    def __init__(self, task_name: str, priority: TaskPriority):
        self.task_name = task_name
        self.priority = priority


@dataclass
class Task:
    """A memory processing task"""

    task_type: TaskType
    priority: TaskPriority
    data: Dict[str, Any]
    created_at: datetime
    salience: float = 0.5
    trace_id: Optional[str] = None

    def __lt__(self, other):
        """For priority queue comparison"""
        if self.priority != other.priority:
            return self.priority < other.priority
        # Same priority: higher salience first
        return self.salience > other.salience
