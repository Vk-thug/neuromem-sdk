"""
Ingest worker for CRITICAL priority tasks (observe).
"""

import time
from datetime import datetime
from neuromem.core.workers.base import BaseWorker
from neuromem.core.task_types import TaskType, TaskPriority
from neuromem.core.types import MemoryItem, MemoryType, EmbeddingMetadata, RetrievalStats
from neuromem.utils.embeddings import get_embedding
from neuromem.utils.logging import get_logger
import uuid

logger = get_logger(__name__)


class IngestWorker(BaseWorker):
    """Handles high-priority memory ingestion tasks with comprehensive error handling"""

    def __init__(self, scheduler, metrics, controller, config):
        super().__init__("IngestWorker", scheduler, metrics)
        self.controller = controller
        self.config = config
        # Get embedding model from controller (which has the correct config)
        self.embedding_model = controller.embedding_model
        # Dead letter queue for failed tasks
        self.dead_letter_queue = []
        self.max_dead_letter_size = 1000
    
    def _work_iteration(self):
        """Process one task from the queue with comprehensive error handling"""
        # Only process CRITICAL priority tasks
        task = self.scheduler.dequeue(timeout=1.0)

        if task is None:
            return

        if task.task_type != TaskType.OBSERVE:
            # Put it back for maintenance worker
            self.scheduler.enqueue(task)
            return

        # Process observe task with retry logic
        start_time = time.time()
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                self._process_observe(task)
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.record('task.duration', duration_ms, {'type': 'observe'})

                # Log success with context
                # logger.info(
                #     "Observe task processed successfully",
                #     extra={
                #         'task_id': task.data.get('task_id'),
                #         'user_id': task.data.get('user_id'),
                #         'duration_ms': duration_ms,
                #         'retry_count': retry_count
                #     }
                # )
                return  # Success

            except Exception as e:
                retry_count += 1
                self.metrics.increment('task.failed', {'type': 'observe', 'error': type(e).__name__})

                logger.error(
                    f"Observe task failed (attempt {retry_count}/{max_retries})",
                    exc_info=True,
                    extra={
                        'task_id': task.data.get('task_id'),
                        'user_id': task.data.get('user_id'),
                        'error': str(e)[:200],
                        'error_type': type(e).__name__,
                        'retry_count': retry_count,
                        'salience': task.salience
                    }
                )

                if retry_count < max_retries:
                    # Exponential backoff
                    wait_time = 2 ** retry_count
                    logger.info(f"Retrying after {wait_time}s", extra={'retry_count': retry_count})
                    time.sleep(wait_time)
                else:
                    # Max retries exceeded - send to dead letter queue
                    logger.critical(
                        "Task failed after max retries, moving to dead letter queue",
                        extra={
                            'task_id': task.data.get('task_id'),
                            'user_id': task.data.get('user_id'),
                            'error': str(e)[:200],
                            'max_retries': max_retries
                        }
                    )
                    self._send_to_dead_letter_queue(task, e)
                    return
    
    def _process_observe(self, task):
        """Process an observe task"""
        data = task.data
        user_input = data['user_input']
        assistant_output = data['assistant_output']
        user_id = data.get('user_id', 'default')
        
        # 1. Prepare content
        content = f"User: {user_input}\nAssistant: {assistant_output}"
        
        # 2. Tag and Enrich (if auto-tagger available)
        tags = []
        metadata = {}
        
        if hasattr(self.controller, 'auto_tagger') and self.controller.auto_tagger:
            try:
                enrichment = self.controller.auto_tagger.enrich_memory(content)
                tags = enrichment.get('tags', [])
                metadata = {
                    'intent': enrichment.get('intent'),
                    'sentiment': enrichment.get('sentiment', {}).get('sentiment'),
                    'entities': enrichment.get('entities', [])
                }
            except Exception as e:
                self.metrics.increment('auto_tagger.error')
                logger.warning(
                    "Auto-tagging failed in ingest worker",
                    exc_info=True,
                    extra={'error': str(e)[:200], 'user_id': user_id}
                )
                tags = []
        
        # 3. Generate embedding
        try:
            embedding = get_embedding(content, self.embedding_model)
        except Exception as e:
            self.metrics.increment('embedding.error')
            raise
        
        # 3. Create memory item
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            embedding=embedding,
            memory_type=MemoryType.EPISODIC,
            salience=task.salience,
            confidence=0.9,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            decay_rate=0.1,
            reinforcement=0,
            inferred=False,
            editable=True,
            tags=tags,
            metadata=metadata,
            embedding_metadata=EmbeddingMetadata(
                model_name=self.embedding_model,
                created_at=datetime.now(),
                last_updated=datetime.now()
            ),
            retrieval_stats=RetrievalStats()
        )
        
        # 4. Store
        self.controller.episodic.store(memory)
        self.metrics.increment('memory.created', {'type': 'episodic'})

    def _send_to_dead_letter_queue(self, task, error: Exception):
        """
        Send failed task to dead letter queue for later analysis.

        Args:
            task: Failed task
            error: Exception that caused failure
        """
        if len(self.dead_letter_queue) >= self.max_dead_letter_size:
            # Remove oldest item
            removed = self.dead_letter_queue.pop(0)
            logger.warning(
                "Dead letter queue full, removing oldest item",
                extra={'removed_task_id': removed.get('task_id')}
            )

        dead_letter_item = {
            'task_id': task.data.get('task_id'),
            'task_type': task.task_type,
            'user_id': task.data.get('user_id'),
            'data': task.data,
            'error': str(error),
            'error_type': type(error).__name__,
            'failed_at': datetime.now(),
            'salience': task.salience
        }

        self.dead_letter_queue.append(dead_letter_item)
        self.metrics.increment('dead_letter.added', {'type': task.task_type})

        logger.info(
            "Task added to dead letter queue",
            extra={
                'task_id': task.data.get('task_id'),
                'dlq_size': len(self.dead_letter_queue)
            }
        )

    def get_dead_letter_queue(self):
        """Get all failed tasks in dead letter queue"""
        return list(self.dead_letter_queue)

    def clear_dead_letter_queue(self):
        """Clear dead letter queue"""
        count = len(self.dead_letter_queue)
        self.dead_letter_queue = []
        logger.info(f"Dead letter queue cleared ({count} items)")
        return count
