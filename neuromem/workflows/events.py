"""
Event definitions and helpers for NeuroMem Inngest workflows.

Provides typed event names and helper functions for sending
workflow events from within the NeuroMem SDK.
"""

from typing import Any, Optional, List

try:
    import inngest

    INNGEST_AVAILABLE = True
except ImportError:
    INNGEST_AVAILABLE = False

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# Event name constants
# ──────────────────────────────────────────────


class NeuroMemEvents:
    """Event name constants for NeuroMem workflows."""

    # Memory lifecycle
    MEMORY_OBSERVED = "neuromem/memory.observed"
    MEMORY_BATCH_INGEST = "neuromem/memory.batch_ingest"
    MEMORY_UPDATED = "neuromem/memory.updated"
    MEMORY_DELETED = "neuromem/memory.deleted"

    # Consolidation
    CONSOLIDATION_REQUESTED = "neuromem/consolidation.requested"
    CONSOLIDATION_COMPLETED = "neuromem/consolidation.completed"

    # Maintenance
    MAINTENANCE_FULL_CYCLE = "neuromem/maintenance.full_cycle"
    DECAY_REQUESTED = "neuromem/decay.requested"
    OPTIMIZATION_REQUESTED = "neuromem/optimization.requested"

    # Health
    HEALTH_DEGRADED = "neuromem/health.degraded"


def send_observe_event(
    client: Any,
    user_input: str,
    assistant_output: str,
    user_id: str,
) -> Optional[List[str]]:
    """
    Send an observation event to trigger async memory processing.

    Args:
        client: Inngest client instance
        user_input: User's message
        assistant_output: Assistant's response
        user_id: User identifier

    Returns:
        List of event IDs, or None if Inngest unavailable
    """
    if not INNGEST_AVAILABLE:
        logger.warning("Inngest not available, cannot send observe event")
        return None

    try:
        return client.send_sync(
            inngest.Event(
                name=NeuroMemEvents.MEMORY_OBSERVED,
                data={
                    "user_input": user_input,
                    "assistant_output": assistant_output,
                    "user_id": user_id,
                },
            )
        )
    except Exception as e:
        logger.error(f"Failed to send observe event: {e}")
        return None


def send_consolidation_event(
    client: Any,
    user_id: str,
    trigger: str = "manual",
) -> Optional[List[str]]:
    """
    Trigger a consolidation workflow.

    Args:
        client: Inngest client instance
        user_id: User identifier
        trigger: Trigger source ("manual", "auto", "api")

    Returns:
        List of event IDs, or None if Inngest unavailable
    """
    if not INNGEST_AVAILABLE:
        return None

    try:
        return client.send_sync(
            inngest.Event(
                name=NeuroMemEvents.CONSOLIDATION_REQUESTED,
                data={"user_id": user_id, "trigger": trigger},
            )
        )
    except Exception as e:
        logger.error(f"Failed to send consolidation event: {e}")
        return None


def send_maintenance_event(client: Any) -> Optional[List[str]]:
    """
    Trigger a full maintenance cycle.

    Args:
        client: Inngest client instance

    Returns:
        List of event IDs, or None if Inngest unavailable
    """
    if not INNGEST_AVAILABLE:
        return None

    try:
        return client.send_sync(
            inngest.Event(
                name=NeuroMemEvents.MAINTENANCE_FULL_CYCLE,
                data={"trigger": "manual"},
            )
        )
    except Exception as e:
        logger.error(f"Failed to send maintenance event: {e}")
        return None


def send_batch_ingest_events(
    client: Any,
    observations: List[dict],
) -> Optional[List[str]]:
    """
    Send batch ingest events for multiple observations.

    Args:
        client: Inngest client instance
        observations: List of dicts with keys: user_input, assistant_output, user_id

    Returns:
        List of event IDs, or None if Inngest unavailable
    """
    if not INNGEST_AVAILABLE:
        return None

    try:
        events = [
            inngest.Event(
                name=NeuroMemEvents.MEMORY_BATCH_INGEST,
                data=obs,
            )
            for obs in observations
        ]
        return client.send_sync(events)
    except Exception as e:
        logger.error(f"Failed to send batch ingest events: {e}")
        return None
