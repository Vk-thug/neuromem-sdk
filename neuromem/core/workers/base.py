"""
Base worker class for background processing.
"""

import threading
import time
from abc import ABC, abstractmethod
from neuromem.core.task_scheduler import PriorityTaskScheduler
from neuromem.core.observability.metrics import MetricsCollector


class BaseWorker(threading.Thread, ABC):
    """Base class for background workers"""
    
    def __init__(self, name: str, scheduler: PriorityTaskScheduler, metrics: MetricsCollector):
        super().__init__(name=name, daemon=True)
        self.scheduler = scheduler
        self.metrics = metrics
        self.running = False
        self._stop_event = threading.Event()
    
    def run(self):
        """Main worker loop"""
        self.running = True
        while self.running and not self._stop_event.is_set():
            try:
                self._work_iteration()
            except Exception as e:
                self.metrics.increment('worker.error', {'worker': self.name, 'error': str(e)})
                time.sleep(1)  # Back off on error
    
    @abstractmethod
    def _work_iteration(self):
        """Single iteration of work - must be implemented by subclass"""
        pass
    
    def stop(self, timeout: float = 5.0):
        """Gracefully stop the worker"""
        self.running = False
        self._stop_event.set()
        self.join(timeout=timeout)
