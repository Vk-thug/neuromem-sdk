"""
Maintenance worker for MEDIUM/LOW/BACKGROUND priority tasks.
"""

import time
from datetime import datetime, timezone
from neuromem.core.workers.base import BaseWorker
from neuromem.core.task_types import TaskType
from neuromem.core.policies.salience import SalienceCalculator
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


class MaintenanceWorker(BaseWorker):
    """Handles maintenance tasks (consolidation, optimization, decay)"""
    
    def __init__(self, scheduler, metrics, controller, config):
        super().__init__("MaintenanceWorker", scheduler, metrics)
        self.controller = controller
        self.config = config
        
        # Proactive maintenance config
        self.auto_consolidate_threshold = config.get('auto_consolidate_threshold', 10)
        self.last_consolidation = datetime.now(timezone.utc)
        self.consolidation_interval_minutes = config.get('consolidation_interval_minutes', 60)
        
        self.last_optimization = datetime.now(timezone.utc)
        self.optimization_interval_hours = config.get('optimization_interval_hours', 24)
        
        self.last_decay = datetime.now(timezone.utc)
        self.decay_interval_hours = config.get('decay_interval_hours', 168)  # Weekly
        
        self.salience_calculator = SalienceCalculator()
    
    def _work_iteration(self):
        """Process one task or run proactive maintenance"""
        # Try to get a task
        task = self.scheduler.dequeue(timeout=1.0)
        
        if task:
            # If we picked up an OBSERVE task (CRITICAL), put it back for IngestWorker
            if task.task_type == TaskType.OBSERVE:
                self.scheduler.enqueue(task)
                time.sleep(0.1)  # Yield to allow IngestWorker to pick it up
                return
                
            self._process_task(task)
        else:
            # Queue is idle - run proactive maintenance
            self._proactive_maintenance()
    
    def _process_task(self, task):
        """Process a maintenance task with comprehensive error handling"""
        start_time = time.time()
        max_retries = 2
        retry_count = 0

        while retry_count < max_retries:
            try:
                if task.task_type == TaskType.CONSOLIDATE:
                    self.controller.consolidate()
                elif task.task_type == TaskType.OPTIMIZE:
                    self._optimize_embeddings()
                elif task.task_type == TaskType.DECAY:
                    self._apply_decay()

                duration_ms = (time.time() - start_time) * 1000
                self.metrics.record('task.duration', duration_ms, {'type': task.task_type.task_name})

                logger.info(
                    f"Maintenance task completed: {task.task_type.task_name}",
                    extra={'duration_ms': duration_ms, 'retry_count': retry_count}
                )
                return  # Success

            except Exception as e:
                retry_count += 1
                self.metrics.increment('task.failed', {'type': task.task_type.task_name, 'error': type(e).__name__})

                logger.error(
                    f"Maintenance task failed (attempt {retry_count}/{max_retries}): {task.task_type.task_name}",
                    exc_info=True,
                    extra={
                        'error': str(e)[:200],
                        'error_type': type(e).__name__,
                        'retry_count': retry_count
                    }
                )

                if retry_count < max_retries:
                    wait_time = 5 * retry_count
                    logger.info(f"Retrying maintenance task after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.critical(
                        f"Maintenance task failed after {max_retries} retries: {task.task_type.task_name}",
                        extra={'error': str(e)[:200]}
                    )
    
    def _proactive_maintenance(self):
        """Run proactive maintenance when idle"""
        # Auto-consolidation
        if self._should_consolidate():
            try:
                logger.info("Running auto-consolidation")
                self.controller.consolidate()
                self.last_consolidation = datetime.now(timezone.utc)
                self.metrics.increment('maintenance.consolidation.auto')
            except Exception as e:
                self.metrics.increment('maintenance.consolidation.error')
                logger.error("Auto-consolidation failed", exc_info=True, extra={'error': str(e)[:200]})

        # Optimization
        if self._should_optimize():
            try:
                logger.info("Running auto-optimization")
                self._optimize_embeddings()
                self.last_optimization = datetime.now(timezone.utc)
                self.metrics.increment('maintenance.optimization.auto')
            except Exception as e:
                self.metrics.increment('maintenance.optimization.error')
                logger.error("Auto-optimization failed", exc_info=True, extra={'error': str(e)[:200]})

        # Decay
        if self._should_decay():
            try:
                logger.info("Running auto-decay")
                self._apply_decay()
                self.last_decay = datetime.now(timezone.utc)
                self.metrics.increment('maintenance.decay.auto')
            except Exception as e:
                self.metrics.increment('maintenance.decay.error')
                logger.error("Auto-decay failed", exc_info=True, extra={'error': str(e)[:200]})
        
        # Sleep a bit if nothing to do
        time.sleep(5)
    
    def _should_consolidate(self) -> bool:
        """Check if consolidation should run"""
        # Check memory count
        episodic_count = len(self.controller.episodic.get_all(limit=self.auto_consolidate_threshold + 1))
        if episodic_count >= self.auto_consolidate_threshold:
            return True
        
        # Check time since last consolidation
        time_since_last = (datetime.now(timezone.utc) - self.last_consolidation).total_seconds() / 60
        if time_since_last >= self.consolidation_interval_minutes:
            return episodic_count > 0  # Only if there are memories
        
        return False
    
    def _should_optimize(self) -> bool:
        """Check if optimization should run"""
        time_since_last = (datetime.now(timezone.utc) - self.last_optimization).total_seconds() / 3600
        return time_since_last >= self.optimization_interval_hours
    
    def _should_decay(self) -> bool:
        """Check if decay should run"""
        time_since_last = (datetime.now(timezone.utc) - self.last_decay).total_seconds() / 3600
        return time_since_last >= self.decay_interval_hours
    
    def _optimize_embeddings(self):
        """Optimize embeddings (placeholder for now)"""
        # This would re-embed memories based on optimization policy
        # For now, just log
        self.metrics.increment('optimization.skipped', {'reason': 'not_implemented'})
    
    def _apply_decay(self):
        """Apply decay to memories"""
        # Get all memories
        all_memories = []
        all_memories.extend(self.controller.episodic.get_all(limit=1000))
        all_memories.extend(self.controller.semantic.get_all(limit=1000))
        
        deleted_count = 0
        for memory in all_memories:
            # Update strength
            memory.strength = self.salience_calculator.calculate_strength(memory)
            
            # Check if should decay
            if self.salience_calculator.should_decay(memory):
                try:
                    if memory.memory_type.value == 'episodic':
                        self.controller.episodic.delete(memory.id)
                    elif memory.memory_type.value == 'semantic':
                        self.controller.semantic.delete(memory.id)
                    deleted_count += 1
                except Exception:
                    pass
        
        self.metrics.gauge('decay.deleted_count', deleted_count)
