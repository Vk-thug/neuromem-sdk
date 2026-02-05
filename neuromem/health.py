"""
Health check system for NeuroMem SDK.

Provides comprehensive health monitoring for all components
including database, workers, queues, and external APIs.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus:
    """Health status constants"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


def get_health_status(neuromem_instance) -> Dict[str, Any]:
    """
    Get comprehensive health status of NeuroMem system.

    Args:
        neuromem_instance: NeuroMem SDK instance

    Returns:
        Dictionary with health status of all components

    Example:
        >>> from neuromem import NeuroMem
        >>> from neuromem.health import get_health_status
        >>> memory = NeuroMem.for_langchain("user_123")
        >>> health = get_health_status(memory)
        >>> print(health['status'])
        'healthy'
    """
    health = {
        'status': HealthStatus.HEALTHY,
        'timestamp': datetime.utcnow().isoformat(),
        'version': '0.1.0',
        'checks': {}
    }

    controller = neuromem_instance.controller

    # 1. Database connectivity check
    health['checks']['database'] = _check_database(controller)

    # 2. Worker health check
    health['checks']['workers'] = _check_workers(controller)

    # 3. Queue depth check
    health['checks']['queues'] = _check_queues(controller)

    # 4. Memory usage check
    health['checks']['memory'] = _check_memory_usage(controller)

    # 5. External API check (OpenAI)
    health['checks']['external_apis'] = _check_external_apis()

    # 6. Dead letter queue check
    health['checks']['dead_letter_queue'] = _check_dead_letter_queue(controller)

    # Determine overall status
    health['status'] = _determine_overall_status(health['checks'])

    logger.info(
        "Health check completed",
        extra={
            'status': health['status'],
            'unhealthy_checks': [k for k, v in health['checks'].items() if v['status'] != HealthStatus.HEALTHY]
        }
    )

    return health


def _check_database(controller) -> Dict[str, Any]:
    """Check database connectivity"""
    try:
        # Try a simple operation
        backend = controller.episodic.backend

        if hasattr(backend, '_get_conn'):
            # PostgreSQL backend
            conn = backend._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                backend._put_conn(conn)
                return {
                    'status': HealthStatus.HEALTHY,
                    'type': 'postgres',
                    'message': 'Database connection successful'
                }
            except Exception as e:
                backend._put_conn(conn)
                return {
                    'status': HealthStatus.UNHEALTHY,
                    'type': 'postgres',
                    'error': str(e)[:200]
                }
        else:
            # In-memory or other backend
            return {
                'status': HealthStatus.HEALTHY,
                'type': 'in-memory',
                'message': 'Backend operational'
            }

    except Exception as e:
        logger.error("Database health check failed", exc_info=True)
        return {
            'status': HealthStatus.UNHEALTHY,
            'error': str(e)[:200]
        }


def _check_workers(controller) -> Dict[str, Any]:
    """Check worker thread health"""
    try:
        if not controller.async_enabled:
            return {
                'status': HealthStatus.HEALTHY,
                'message': 'Async mode disabled'
            }

        workers = {}

        # Check ingest worker
        if controller.ingest_worker:
            workers['ingest'] = {
                'running': controller.ingest_worker._running,
                'thread_alive': controller.ingest_worker._thread.is_alive() if controller.ingest_worker._thread else False
            }

        # Check maintenance worker
        if controller.maintenance_worker:
            workers['maintenance'] = {
                'running': controller.maintenance_worker._running,
                'thread_alive': controller.maintenance_worker._thread.is_alive() if controller.maintenance_worker._thread else False
            }

        # Determine status
        all_healthy = all(
            w['running'] and w['thread_alive']
            for w in workers.values()
        )

        return {
            'status': HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY,
            'workers': workers
        }

    except Exception as e:
        logger.error("Worker health check failed", exc_info=True)
        return {
            'status': HealthStatus.UNHEALTHY,
            'error': str(e)[:200]
        }


def _check_queues(controller) -> Dict[str, Any]:
    """Check queue depths and capacity"""
    try:
        if not controller.async_enabled or not controller.scheduler:
            return {
                'status': HealthStatus.HEALTHY,
                'message': 'Async mode disabled'
            }

        metrics = controller.scheduler.get_metrics()

        queue_depths = {}
        for priority in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'BACKGROUND']:
            depth_key = f'queue.depth.{priority}'
            if depth_key in metrics:
                queue_depths[priority.lower()] = metrics[depth_key]

        # Check for concerning queue depths
        critical_depth = queue_depths.get('critical', 0)
        high_depth = queue_depths.get('high', 0)

        if critical_depth > 500 or high_depth > 250:
            status = HealthStatus.DEGRADED
            message = f"High queue depth: critical={critical_depth}, high={high_depth}"
        else:
            status = HealthStatus.HEALTHY
            message = "Queue depths normal"

        return {
            'status': status,
            'depths': queue_depths,
            'message': message
        }

    except Exception as e:
        logger.error("Queue health check failed", exc_info=True)
        return {
            'status': HealthStatus.UNHEALTHY,
            'error': str(e)[:200]
        }


def _check_memory_usage(controller) -> Dict[str, Any]:
    """Check memory item counts"""
    try:
        episodic_count = len(controller.episodic.get_all())
        semantic_count = len(controller.semantic.get_all())
        procedural_count = len(controller.procedural.get_all())

        total_count = episodic_count + semantic_count + procedural_count

        # Check for excessive memory growth
        if total_count > 100000:
            status = HealthStatus.DEGRADED
            message = f"High memory count: {total_count}"
        elif total_count > 500000:
            status = HealthStatus.UNHEALTHY
            message = f"Critical memory count: {total_count}"
        else:
            status = HealthStatus.HEALTHY
            message = "Memory usage normal"

        return {
            'status': status,
            'counts': {
                'episodic': episodic_count,
                'semantic': semantic_count,
                'procedural': procedural_count,
                'total': total_count
            },
            'message': message
        }

    except Exception as e:
        logger.error("Memory usage health check failed", exc_info=True)
        return {
            'status': HealthStatus.UNHEALTHY,
            'error': str(e)[:200]
        }


def _check_external_apis() -> Dict[str, Any]:
    """Check external API status (OpenAI)"""
    try:
        from neuromem.utils.embeddings import _openai_circuit_breaker

        circuit_state = _openai_circuit_breaker.state

        if circuit_state == "CLOSED":
            status = HealthStatus.HEALTHY
            message = "OpenAI API operational"
        elif circuit_state == "HALF_OPEN":
            status = HealthStatus.DEGRADED
            message = "OpenAI API recovering"
        else:  # OPEN
            status = HealthStatus.UNHEALTHY
            message = "OpenAI API circuit breaker open"

        return {
            'status': status,
            'openai': {
                'circuit_breaker': circuit_state,
                'failure_count': _openai_circuit_breaker.failure_count
            },
            'message': message
        }

    except Exception as e:
        logger.error("External API health check failed", exc_info=True)
        return {
            'status': HealthStatus.DEGRADED,
            'error': str(e)[:200]
        }


def _check_dead_letter_queue(controller) -> Dict[str, Any]:
    """Check dead letter queue for failed tasks"""
    try:
        if not controller.async_enabled or not controller.ingest_worker:
            return {
                'status': HealthStatus.HEALTHY,
                'message': 'Async mode disabled'
            }

        dlq = controller.ingest_worker.get_dead_letter_queue()
        dlq_size = len(dlq)

        if dlq_size == 0:
            status = HealthStatus.HEALTHY
            message = "No failed tasks"
        elif dlq_size < 10:
            status = HealthStatus.DEGRADED
            message = f"{dlq_size} failed tasks in queue"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"{dlq_size} failed tasks - attention required"

        return {
            'status': status,
            'size': dlq_size,
            'message': message
        }

    except Exception as e:
        logger.error("Dead letter queue health check failed", exc_info=True)
        return {
            'status': HealthStatus.DEGRADED,
            'error': str(e)[:200]
        }


def _determine_overall_status(checks: Dict[str, Dict[str, Any]]) -> str:
    """Determine overall status from individual checks"""
    statuses = [check['status'] for check in checks.values()]

    if HealthStatus.UNHEALTHY in statuses:
        return HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.HEALTHY


def get_readiness_status(neuromem_instance) -> Dict[str, Any]:
    """
    Get readiness status (can the system accept new requests?).

    Args:
        neuromem_instance: NeuroMem SDK instance

    Returns:
        Dictionary with readiness status
    """
    controller = neuromem_instance.controller

    ready = True
    reasons = []

    # Check if workers are running
    if controller.async_enabled:
        if not controller.ingest_worker or not controller.ingest_worker._running:
            ready = False
            reasons.append("Ingest worker not running")

        if not controller.maintenance_worker or not controller.maintenance_worker._running:
            ready = False
            reasons.append("Maintenance worker not running")

    # Check database
    try:
        backend = controller.episodic.backend
        if hasattr(backend, '_get_conn'):
            conn = backend._get_conn()
            backend._put_conn(conn)
    except Exception as e:
        ready = False
        reasons.append(f"Database not accessible: {str(e)[:100]}")

    return {
        'ready': ready,
        'timestamp': datetime.utcnow().isoformat(),
        'reasons': reasons if not ready else ["System ready"]
    }


def get_liveness_status(neuromem_instance) -> Dict[str, Any]:
    """
    Get liveness status (is the system alive?).

    Args:
        neuromem_instance: NeuroMem SDK instance

    Returns:
        Dictionary with liveness status
    """
    # Simple check - if we can execute this, we're alive
    return {
        'alive': True,
        'timestamp': datetime.utcnow().isoformat()
    }
