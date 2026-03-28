"""
NeuroMem + Inngest Workflow Example

Demonstrates how to run NeuroMem's brain-inspired memory operations
as durable, scheduled workflows using Inngest.

Setup:
    1. pip install neuromem-sdk[inngest]
    2. Start Inngest Dev Server:
       npx inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
    3. Run this script:
       INNGEST_DEV=1 python examples/inngest_workflows.py

What this sets up:
    - Cron: Memory consolidation every 2 hours
    - Cron: Memory decay daily at 3 AM
    - Cron: Embedding optimization weekly on Sundays
    - Cron: Health checks every 15 minutes
    - Event: Async memory observation with auto-retry
    - Event: Batch memory ingestion
    - Workflow: Full maintenance cycle (consolidation → decay → optimization)

Open http://localhost:8288 to see the Inngest Dev Server dashboard.
"""

import os
import sys

# Add parent directory to path for local development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from neuromem import NeuroMem
    from neuromem.workflows import create_neuromem_workflows, create_workflow_app

    # 1. Initialize NeuroMem with in-memory backend (for demo)
    config_path = os.path.join(os.path.dirname(__file__), "neuromem.yaml")
    if not os.path.exists(config_path):
        config_path = "neuromem.yaml"

    memory = NeuroMem.from_config(config_path, user_id="demo-user-001")
    print("NeuroMem initialized")

    # 2. Create Inngest workflow functions
    functions = create_neuromem_workflows(memory, app_id="neuromem-demo")
    print(f"Created {len(functions)} Inngest functions:")
    for fn in functions:
        fn_id = getattr(fn, "id", str(fn))
        print(f"  - {fn_id}")

    # 3. Create FastAPI app with Inngest endpoint
    app = create_workflow_app(
        neuromem_instance=memory,
        functions=functions,
        app_id="neuromem-demo",
    )
    print("\nFastAPI app created with endpoints:")
    print("  GET  /health     - Server health")
    print("  GET  /workflows  - List registered functions")
    print("  POST /trigger/{event_name} - Manual event trigger")
    print("  POST /api/inngest - Inngest webhook endpoint")

    # 4. Run the server
    print("\n" + "=" * 60)
    print("Starting NeuroMem Workflow Server on http://localhost:8000")
    print("Inngest Dev Dashboard: http://localhost:8288")
    print("=" * 60 + "\n")

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def demo_send_events():
    """
    Example: Send events programmatically to trigger workflows.

    Run this after the server is running:
        python -c "from examples.inngest_workflows import demo_send_events; demo_send_events()"
    """
    from neuromem.workflows.client import get_inngest_client
    from neuromem.workflows.events import (
        send_observe_event,
        send_consolidation_event,
        send_maintenance_event,
        send_batch_ingest_events,
    )

    client = get_inngest_client(app_id="neuromem-demo")

    # Send a single observation
    print("Sending observation event...")
    result = send_observe_event(
        client,
        user_input="I prefer using PostgreSQL for production databases",
        assistant_output="Great choice! PostgreSQL is robust and scalable.",
        user_id="demo-user-001",
    )
    print(f"  Event IDs: {result}")

    # Send batch observations
    print("Sending batch ingest events...")
    result = send_batch_ingest_events(
        client,
        observations=[
            {
                "user_input": "I like Python for ML work",
                "assistant_output": "Python has excellent ML libraries!",
                "user_id": "demo-user-001",
            },
            {
                "user_input": "I use Docker for deployments",
                "assistant_output": "Docker makes deployments consistent.",
                "user_id": "demo-user-001",
            },
        ],
    )
    print(f"  Event IDs: {result}")

    # Trigger consolidation
    print("Triggering consolidation...")
    result = send_consolidation_event(client, user_id="demo-user-001", trigger="manual")
    print(f"  Event IDs: {result}")

    # Trigger full maintenance
    print("Triggering full maintenance cycle...")
    result = send_maintenance_event(client)
    print(f"  Event IDs: {result}")

    print("\nDone! Check the Inngest Dev Dashboard at http://localhost:8288")


if __name__ == "__main__":
    main()
