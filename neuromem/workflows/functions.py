"""
Inngest function definitions for NeuroMem workflows.

Defines all durable workflows, cron jobs, and event-driven functions:

Cron Jobs:
  - scheduled_consolidation: Periodic episodic → semantic consolidation
  - scheduled_decay: Periodic memory decay and cleanup
  - scheduled_optimization: Periodic embedding optimization
  - scheduled_health_check: Periodic health monitoring

Event-Driven:
  - on_memory_observed: Process new observations with enrichment
  - on_consolidation_requested: Manual consolidation trigger
  - on_memory_batch_ingest: Batch ingest multiple memories

Workflows:
  - full_maintenance_cycle: Complete maintenance pipeline
"""

import datetime
import functools
from typing import Any, List, Optional

try:
    import inngest

    INNGEST_AVAILABLE = True
except ImportError:
    INNGEST_AVAILABLE = False

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Placeholder for the function list — populated by create_all_functions()
NEUROMEM_FUNCTIONS: List[Any] = []


def create_all_functions(client: Any, neuromem: Any) -> List[Any]:
    """
    Create all Inngest functions bound to a NeuroMem instance.

    Args:
        client: inngest.Inngest client
        neuromem: NeuroMem instance

    Returns:
        List of Inngest function objects
    """
    if not INNGEST_AVAILABLE:
        raise ImportError("inngest package required")

    functions = []

    # ──────────────────────────────────────────────
    # CRON JOBS
    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-scheduled-consolidation",
        trigger=inngest.TriggerCron(cron="0 */2 * * *"),  # Every 2 hours
        retries=2,
    )
    def scheduled_consolidation(ctx: inngest.ContextSync) -> dict:
        """
        Periodic consolidation: episodic → semantic memory promotion.

        Runs every 2 hours. Identifies episodic memories ready for
        consolidation and promotes them to semantic/procedural memories.
        """
        ctx.logger.info("Starting scheduled consolidation")

        # Step 1: Get consolidation candidates
        candidates = ctx.step.run(
            "get-candidates",
            functools.partial(_get_consolidation_candidates, neuromem),
        )

        if not candidates or candidates.get("count", 0) == 0:
            ctx.logger.info("No candidates for consolidation")
            return {"status": "skipped", "reason": "no_candidates"}

        # Step 2: Run consolidation
        result = ctx.step.run(
            "consolidate",
            functools.partial(_run_consolidation, neuromem),
        )

        ctx.logger.info(
            "Consolidation complete",
            extra=result,
        )

        return result

    functions.append(scheduled_consolidation)

    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-scheduled-decay",
        trigger=inngest.TriggerCron(cron="0 3 * * *"),  # Daily at 3 AM
        retries=2,
    )
    def scheduled_decay(ctx: inngest.ContextSync) -> dict:
        """
        Periodic decay: apply Ebbinghaus forgetting curves.

        Runs daily. Calculates memory strength and removes
        memories that have decayed below threshold.
        """
        ctx.logger.info("Starting scheduled decay")

        result = ctx.step.run(
            "apply-decay",
            functools.partial(_apply_decay, neuromem),
        )

        ctx.logger.info("Decay complete", extra=result)
        return result

    functions.append(scheduled_decay)

    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-scheduled-optimization",
        trigger=inngest.TriggerCron(cron="0 4 * * 0"),  # Weekly on Sunday at 4 AM
        retries=1,
    )
    def scheduled_optimization(ctx: inngest.ContextSync) -> dict:
        """
        Periodic optimization: re-embed stale or underperforming memories.

        Runs weekly. Checks embedding age and retrieval performance,
        re-embeds memories that would benefit from fresh embeddings.
        """
        ctx.logger.info("Starting scheduled optimization")

        # Step 1: Find memories needing re-embedding
        candidates = ctx.step.run(
            "find-stale-embeddings",
            functools.partial(_find_stale_embeddings, neuromem),
        )

        if not candidates or candidates.get("count", 0) == 0:
            return {"status": "skipped", "reason": "no_stale_embeddings"}

        # Step 2: Re-embed them
        result = ctx.step.run(
            "reembed-memories",
            functools.partial(_reembed_memories, neuromem, candidates.get("ids", [])),
        )

        return result

    functions.append(scheduled_optimization)

    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-scheduled-health-check",
        trigger=inngest.TriggerCron(cron="*/15 * * * *"),  # Every 15 minutes
        retries=0,
    )
    def scheduled_health_check(ctx: inngest.ContextSync) -> dict:
        """
        Periodic health check: monitor system components.

        Runs every 15 minutes. Checks database, workers, queues,
        and external APIs. Logs warnings for degraded components.
        """
        from neuromem.health import get_health_status

        health = get_health_status(neuromem)
        status = health.get("status", "unknown")

        if status != "healthy":
            ctx.logger.warning(
                "NeuroMem health degraded",
                extra={
                    "status": status,
                    "checks": {k: v.get("status") for k, v in health.get("checks", {}).items()},
                },
            )

        return {"status": status, "timestamp": health.get("timestamp")}

    functions.append(scheduled_health_check)

    # ──────────────────────────────────────────────
    # EVENT-DRIVEN FUNCTIONS
    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-on-memory-observed",
        trigger=inngest.TriggerEvent(event="neuromem/memory.observed"),
        retries=3,
        concurrency=[inngest.Concurrency(limit=20)],
    )
    def on_memory_observed(ctx: inngest.ContextSync) -> dict:
        """
        Process a new observation event.

        Triggered when memory.observe() is called with Inngest mode enabled.
        Handles embedding generation, auto-tagging, and storage as
        durable steps with automatic retries.
        """
        data = ctx.event.data
        user_input = data["user_input"]
        assistant_output = data["assistant_output"]
        user_id = data["user_id"]

        ctx.logger.info(
            "Processing observation",
            extra={"user_id": user_id},
        )

        # Step 1: Generate embedding (retriable)
        embedding = ctx.step.run(
            "generate-embedding",
            functools.partial(_generate_embedding, neuromem, user_input, assistant_output),
        )

        # Step 2: Auto-tag (retriable, non-critical)
        enrichment = ctx.step.run(
            "auto-tag",
            functools.partial(_auto_tag, neuromem, user_input, assistant_output),
        )

        # Step 3: Store memory (retriable)
        memory_id = ctx.step.run(
            "store-memory",
            functools.partial(
                _store_observation,
                neuromem,
                user_input,
                assistant_output,
                user_id,
                embedding,
                enrichment,
            ),
        )

        # Step 4: Check if consolidation is needed
        should_consolidate = ctx.step.run(
            "check-consolidation",
            functools.partial(_should_trigger_consolidation, neuromem),
        )

        if should_consolidate:
            # Trigger consolidation as a separate event
            ctx.step.send_event(
                "trigger-consolidation",
                inngest.Event(
                    name="neuromem/consolidation.requested",
                    data={"user_id": user_id, "trigger": "auto"},
                ),
            )

        return {"memory_id": memory_id, "user_id": user_id}

    functions.append(on_memory_observed)

    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-on-consolidation-requested",
        trigger=inngest.TriggerEvent(event="neuromem/consolidation.requested"),
        retries=2,
        debounce=inngest.Debounce(
            period=datetime.timedelta(minutes=5),
            key="event.data.user_id",
        ),
    )
    def on_consolidation_requested(ctx: inngest.ContextSync) -> dict:
        """
        Manual/event-triggered consolidation.

        Debounced per user (5 minutes) to prevent excessive consolidation.
        Can be triggered manually or by on_memory_observed when threshold is met.
        """
        user_id = ctx.event.data.get("user_id", "unknown")
        trigger = ctx.event.data.get("trigger", "manual")

        ctx.logger.info(
            "Consolidation requested",
            extra={"user_id": user_id, "trigger": trigger},
        )

        result = ctx.step.run(
            "consolidate",
            functools.partial(_run_consolidation, neuromem),
        )

        return {**result, "user_id": user_id, "trigger": trigger}

    functions.append(on_consolidation_requested)

    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-on-batch-ingest",
        trigger=inngest.TriggerEvent(event="neuromem/memory.batch_ingest"),
        retries=3,
        batch_events=inngest.Batch(
            max_size=50,
            timeout=datetime.timedelta(seconds=10),
        ),
    )
    def on_batch_ingest(ctx: inngest.ContextSync) -> dict:
        """
        Batch ingest multiple memories at once.

        Automatically batches events (up to 50) within a 10-second window
        and processes them together for efficiency.
        """
        events = ctx.events
        ctx.logger.info(f"Batch ingesting {len(events)} memories")

        processed = 0
        errors = 0

        for i, event in enumerate(events):
            try:
                ctx.step.run(
                    f"ingest-{i}",
                    functools.partial(
                        _store_observation,
                        neuromem,
                        event.data["user_input"],
                        event.data["assistant_output"],
                        event.data["user_id"],
                        None,  # embedding generated inside
                        None,  # enrichment generated inside
                    ),
                )
                processed += 1
            except Exception as e:
                errors += 1
                ctx.logger.error(f"Batch ingest item {i} failed: {e}")

        return {"processed": processed, "errors": errors, "total": len(events)}

    functions.append(on_batch_ingest)

    # ──────────────────────────────────────────────
    # DURABLE WORKFLOWS
    # ──────────────────────────────────────────────

    @client.create_function(
        fn_id="neuromem-full-maintenance-cycle",
        trigger=inngest.TriggerEvent(event="neuromem/maintenance.full_cycle"),
        retries=1,
    )
    def full_maintenance_cycle(ctx: inngest.ContextSync) -> dict:
        """
        Full maintenance pipeline: consolidation → decay → optimization.

        Runs all maintenance tasks in sequence as durable steps.
        Each step is independently retriable.
        """
        ctx.logger.info("Starting full maintenance cycle")

        # Step 1: Consolidation
        consolidation_result = ctx.step.run(
            "consolidation",
            functools.partial(_run_consolidation, neuromem),
        )

        # Step 2: Decay
        decay_result = ctx.step.run(
            "decay",
            functools.partial(_apply_decay, neuromem),
        )

        # Step 3: Find stale embeddings
        stale = ctx.step.run(
            "find-stale",
            functools.partial(_find_stale_embeddings, neuromem),
        )

        # Step 4: Re-embed if needed
        optimization_result = {"status": "skipped"}
        if stale and stale.get("count", 0) > 0:
            optimization_result = ctx.step.run(
                "reembed",
                functools.partial(_reembed_memories, neuromem, stale.get("ids", [])),
            )

        # Step 5: Health check
        health_result = ctx.step.run(
            "health-check",
            functools.partial(_run_health_check, neuromem),
        )

        return {
            "consolidation": consolidation_result,
            "decay": decay_result,
            "optimization": optimization_result,
            "health": health_result,
        }

    functions.append(full_maintenance_cycle)

    # Update module-level reference
    global NEUROMEM_FUNCTIONS
    NEUROMEM_FUNCTIONS = functions

    return functions


# ──────────────────────────────────────────────────────────
# Step handler functions (pure functions called by Inngest steps)
# ──────────────────────────────────────────────────────────


def _get_consolidation_candidates(neuromem: Any) -> dict:
    """Get episodic memories eligible for consolidation."""
    controller = neuromem.controller
    episodic_items = controller.episodic.get_all()
    candidates = controller.decay_engine.schedule_consolidation(episodic_items)
    return {
        "count": len(candidates),
        "ids": [c.id for c in candidates],
    }


def _run_consolidation(neuromem: Any) -> dict:
    """Execute memory consolidation."""
    try:
        neuromem.consolidate()
        return {
            "status": "completed",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Consolidation failed", exc_info=True, extra={"error": str(e)[:200]})
        return {"status": "failed", "error": str(e)[:200]}


def _apply_decay(neuromem: Any) -> dict:
    """Apply decay to all memories."""
    controller = neuromem.controller
    all_memories = []
    all_memories.extend(controller.episodic.get_all(limit=1000))
    all_memories.extend(controller.semantic.get_all(limit=1000))

    active, forgotten = controller.decay_engine.apply_decay(all_memories)

    deleted_count = 0
    for item in forgotten:
        try:
            if item.memory_type.value == "episodic":
                controller.episodic.delete(item.id)
            elif item.memory_type.value == "semantic":
                controller.semantic.delete(item.id)
            deleted_count += 1
        except Exception:
            pass

    return {
        "status": "completed",
        "total_checked": len(all_memories),
        "active": len(active),
        "deleted": deleted_count,
    }


def _find_stale_embeddings(neuromem: Any) -> dict:
    """Find memories with stale or underperforming embeddings."""
    from neuromem.core.policies.optimization import EmbeddingOptimizationPolicy

    controller = neuromem.controller
    config = {}
    if hasattr(controller, "config") and controller.config:
        config = controller.config.embeddings() if hasattr(controller.config, "embeddings") else {}

    policy = EmbeddingOptimizationPolicy(config)
    all_memories = controller.episodic.get_all(limit=500)
    all_memories.extend(controller.semantic.get_all(limit=500))

    stale_ids = [m.id for m in all_memories if policy.should_reembed(m)]

    return {"count": len(stale_ids), "ids": stale_ids[:100]}  # Cap at 100


def _reembed_memories(neuromem: Any, memory_ids: List[str]) -> dict:
    """Re-embed a list of memories with fresh embeddings."""
    from neuromem.utils.embeddings import get_embedding

    controller = neuromem.controller
    model = controller.embedding_model
    reembedded = 0

    for memory_id in memory_ids:
        memory = None
        for mem_layer in [controller.episodic, controller.semantic, controller.procedural]:
            memory = mem_layer.get_by_id(memory_id)
            if memory:
                break

        if memory:
            try:
                memory.embedding = get_embedding(memory.content, model)
                if memory.embedding_metadata:
                    memory.embedding_metadata.model_name = model
                    memory.embedding_metadata.last_updated = datetime.datetime.now(
                        datetime.timezone.utc
                    )
                for mem_layer in [controller.episodic, controller.semantic, controller.procedural]:
                    if mem_layer.get_by_id(memory_id):
                        mem_layer.update(memory)
                        break
                reembedded += 1
            except Exception as e:
                logger.warning(f"Re-embed failed for {memory_id}: {e}")

    return {"status": "completed", "reembedded": reembedded, "total": len(memory_ids)}


def _generate_embedding(neuromem: Any, user_input: str, assistant_output: str) -> list:
    """Generate embedding for an observation."""
    from neuromem.utils.embeddings import get_embedding

    content = f"User: {user_input}\nAssistant: {assistant_output}"
    model = neuromem.controller.embedding_model
    return get_embedding(content, model)


def _auto_tag(neuromem: Any, user_input: str, assistant_output: str) -> dict:
    """Auto-tag an observation. Returns empty dict on failure."""
    controller = neuromem.controller
    content = f"User: {user_input}\nAssistant: {assistant_output}"

    if hasattr(controller, "auto_tagger") and controller.auto_tagger:
        try:
            return controller.auto_tagger.enrich_memory(content)
        except Exception as e:
            logger.warning(f"Auto-tagging failed: {e}")

    return {"tags": [], "intent": None, "sentiment": None, "entities": []}


def _store_observation(
    neuromem: Any,
    user_input: str,
    assistant_output: str,
    user_id: str,
    embedding: Optional[list],
    enrichment: Optional[dict],
) -> str:
    """Store an observation as an episodic memory. Returns memory ID."""
    import uuid
    from neuromem.core.types import MemoryItem, MemoryType
    from neuromem.utils.embeddings import get_embedding
    from neuromem import constants

    controller = neuromem.controller
    content = f"User: {user_input}\nAssistant: {assistant_output}"

    # Generate embedding if not provided
    if embedding is None:
        embedding = get_embedding(content, controller.embedding_model)

    # Parse enrichment
    tags = []
    metadata = {}
    if enrichment:
        tags = enrichment.get("tags", [])
        metadata = {
            "intent": enrichment.get("intent"),
            "sentiment": (
                enrichment.get("sentiment", {}).get("sentiment")
                if isinstance(enrichment.get("sentiment"), dict)
                else enrichment.get("sentiment")
            ),
            "entities": enrichment.get("entities", []),
        }

    memory_id = str(uuid.uuid4())
    memory_item = MemoryItem(
        id=memory_id,
        user_id=user_id,
        content=content,
        embedding=embedding,
        memory_type=MemoryType.EPISODIC,
        salience=controller._calculate_salience(user_input, assistant_output),
        confidence=constants.DEFAULT_EPISODIC_CONFIDENCE,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        last_accessed=datetime.datetime.now(datetime.timezone.utc),
        decay_rate=constants.DEFAULT_EPISODIC_DECAY_RATE,
        reinforcement=1,
        inferred=False,
        editable=True,
        tags=tags,
        metadata=metadata,
    )

    controller.episodic.store(memory_item)
    controller.session.add_turn(user_input, assistant_output)

    return memory_id


def _should_trigger_consolidation(neuromem: Any) -> bool:
    """Check if consolidation should be triggered based on memory count."""
    controller = neuromem.controller
    consolidation_interval = 10
    if hasattr(controller, "config") and controller.config:
        consolidation_interval = controller.config.memory().get("consolidation_interval", 10)

    episodic_count = len(controller.episodic.get_all(limit=consolidation_interval + 1))
    return episodic_count >= consolidation_interval


def _run_health_check(neuromem: Any) -> dict:
    """Run a health check and return status."""
    from neuromem.health import get_health_status

    health = get_health_status(neuromem)
    return {
        "status": health.get("status", "unknown"),
        "timestamp": health.get("timestamp"),
    }
