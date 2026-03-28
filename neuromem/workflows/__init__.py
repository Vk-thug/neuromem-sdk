"""
NeuroMem Workflows — Inngest-powered durable workflows for memory operations.

Provides cron-scheduled and event-driven workflows for:
- Memory consolidation (episodic → semantic)
- Memory decay and cleanup
- Embedding optimization
- Event-driven observe and retrieval

Requires: pip install neuromem-sdk[inngest]
"""

from neuromem.workflows.client import get_inngest_client, create_neuromem_workflows
from neuromem.workflows.functions import (
    NEUROMEM_FUNCTIONS,
)
from neuromem.workflows.server import create_workflow_app

__all__ = [
    "get_inngest_client",
    "create_neuromem_workflows",
    "create_workflow_app",
    "NEUROMEM_FUNCTIONS",
]
