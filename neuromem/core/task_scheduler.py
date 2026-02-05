"""
Priority-based task scheduler with salience-aware backpressure.
"""

import queue
from typing import Dict, Optional
from collections import defaultdict
from neuromem.core.task_types import Task, TaskPriority


class PriorityTaskScheduler:
    """Multi-queue scheduler with priority-based task routing"""
    
    def __init__(self, config: Dict = None):
        config = config or {}
        
        # Separate queue for each priority level
        self.queues: Dict[TaskPriority, queue.Queue] = {
            TaskPriority.CRITICAL: queue.Queue(maxsize=config.get('critical_queue_size', 1000)),
            TaskPriority.HIGH: queue.Queue(maxsize=config.get('high_queue_size', 500)),
            TaskPriority.MEDIUM: queue.Queue(maxsize=config.get('medium_queue_size', 100)),
            TaskPriority.LOW: queue.Queue(maxsize=config.get('low_queue_size', 50)),
            TaskPriority.BACKGROUND: queue.Queue(maxsize=config.get('background_queue_size', 10)),
        }
        
        # Metrics
        self.metrics = defaultdict(int)
        self.salience_threshold = config.get('salience_threshold', 0.7)
    
    def enqueue(self, task: Task) -> bool:
        """
        Enqueue task with salience-aware backpressure.
        
        Returns:
            True if task was enqueued, False if dropped
        """
        priority = task.priority
        q = self.queues[priority]
        
        if q.full():
            if priority == TaskPriority.CRITICAL:
                # NEVER drop critical high-salience tasks
                if task.salience >= self.salience_threshold:
                    # Evict oldest low-salience task
                    self._evict_low_salience(priority)
                    q.put(task)
                    self.metrics['task.evicted'] += 1
                    return True
                else:
                    # Drop low-salience critical task
                    self.metrics['task.dropped'] += 1
                    self.metrics[f'task.dropped.{priority.name}'] += 1
                    return False
            else:
                # Non-critical: drop oldest
                try:
                    q.get_nowait()
                    self.metrics['task.evicted'] += 1
                except queue.Empty:
                    pass
                q.put(task)
                return True
        else:
            q.put_nowait(task)
            self.metrics['task.enqueued'] += 1
            self.metrics[f'task.enqueued.{priority.name}'] += 1
            return True
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Task]:
        """
        Dequeue highest-priority available task.
        
        Args:
            timeout: Max time to wait for a task
            
        Returns:
            Task or None if no tasks available
        """
        # Check queues in priority order
        for priority in sorted(TaskPriority):
            q = self.queues[priority]
            try:
                # Use shorter timeout for lower-priority queues
                queue_timeout = timeout if priority == TaskPriority.CRITICAL else 0.1
                task = q.get(timeout=queue_timeout)
                self.metrics['task.dequeued'] += 1
                self.metrics[f'task.dequeued.{priority.name}'] += 1
                return task
            except queue.Empty:
                continue
        
        return None
    
    def _evict_low_salience(self, priority: TaskPriority):
        """Evict oldest low-salience task from queue"""
        q = self.queues[priority]
        temp_tasks = []
        evicted = False
        
        # Scan queue for low-salience task
        while not q.empty():
            try:
                task = q.get_nowait()
                if not evicted and task.salience < self.salience_threshold:
                    # Drop this one
                    evicted = True
                    continue
                temp_tasks.append(task)
            except queue.Empty:
                break
        
        # Put tasks back
        for task in temp_tasks:
            try:
                q.put_nowait(task)
            except queue.Full:
                break
    
    def get_queue_depth(self, priority: TaskPriority) -> int:
        """Get current depth of a priority queue"""
        return self.queues[priority].qsize()
    
    def get_metrics(self) -> Dict[str, int]:
        """Get scheduler metrics"""
        metrics = dict(self.metrics)
        # Add queue depths
        for priority in TaskPriority:
            metrics[f'queue.depth.{priority.name}'] = self.get_queue_depth(priority)
        return metrics
    
    def is_idle(self) -> bool:
        """Check if all queues are empty"""
        return all(q.empty() for q in self.queues.values())
