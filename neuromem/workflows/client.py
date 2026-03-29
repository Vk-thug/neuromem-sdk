"""
Inngest client configuration for NeuroMem workflows.

Creates and configures the Inngest client that powers all
durable workflows, cron jobs, and event-driven functions.
"""

import logging
from typing import Optional, List, Any

try:
    import inngest

    INNGEST_AVAILABLE = True
except ImportError:
    INNGEST_AVAILABLE = False

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level singleton
_inngest_client: Optional[Any] = None


def get_inngest_client(
    app_id: str = "neuromem",
    is_production: bool = False,
    event_key: Optional[str] = None,
    signing_key: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> Any:
    """
    Get or create the Inngest client singleton.

    Args:
        app_id: Inngest application identifier
        is_production: Enable production mode (requires signing keys)
        event_key: API key for sending events (or INNGEST_EVENT_KEY env var)
        signing_key: Request signing key (or INNGEST_SIGNING_KEY env var)
        logger_instance: Python logger instance

    Returns:
        inngest.Inngest client instance

    Raises:
        ImportError: If inngest package is not installed
    """
    global _inngest_client

    if not INNGEST_AVAILABLE:
        raise ImportError(
            "Inngest is not installed. Install with: pip install neuromem-sdk[inngest]"
        )

    if _inngest_client is not None:
        return _inngest_client

    kwargs: dict = {
        "app_id": app_id,
        "is_production": is_production,
    }
    if event_key:
        kwargs["event_key"] = event_key
    if signing_key:
        kwargs["signing_key"] = signing_key
    if logger_instance:
        kwargs["logger"] = logger_instance

    _inngest_client = inngest.Inngest(**kwargs)

    logger.info(
        "Inngest client created",
        extra={"app_id": app_id, "is_production": is_production},
    )

    return _inngest_client


def create_neuromem_workflows(
    neuromem_instance: Any,
    app_id: str = "neuromem",
    is_production: bool = False,
) -> List[Any]:
    """
    Create all NeuroMem Inngest workflow functions bound to a NeuroMem instance.

    This is the main entry point for setting up Inngest workflows.
    It creates the client, registers all functions, and returns them
    ready to be served.

    Args:
        neuromem_instance: Initialized NeuroMem instance
        app_id: Inngest application identifier
        is_production: Enable production mode

    Returns:
        List of Inngest function objects ready for serve()

    Example:
        >>> from neuromem import NeuroMem
        >>> from neuromem.workflows import create_neuromem_workflows, create_workflow_app
        >>>
        >>> memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
        >>> functions = create_neuromem_workflows(memory)
        >>> app = create_workflow_app(functions)
        >>> # Run: INNGEST_DEV=1 uvicorn app:app --port 8000
    """
    if not INNGEST_AVAILABLE:
        raise ImportError(
            "Inngest is not installed. Install with: pip install neuromem-sdk[inngest]"
        )

    client = get_inngest_client(app_id=app_id, is_production=is_production)

    from neuromem.workflows.functions import create_all_functions

    functions = create_all_functions(client, neuromem_instance)

    logger.info(
        "NeuroMem workflows created",
        extra={"function_count": len(functions), "app_id": app_id},
    )

    return functions


def reset_client() -> None:
    """Reset the singleton client. Useful for testing."""
    global _inngest_client
    _inngest_client = None
