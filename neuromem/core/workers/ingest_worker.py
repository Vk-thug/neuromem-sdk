"""
Ingest worker for CRITICAL priority tasks (observe).
"""

import time
from datetime import datetime
from neuromem.core.workers.base import BaseWorker
from neuromem.core.task_types import TaskType, TaskPriority
from neuromem.core.types import MemoryItem, MemoryType, EmbeddingMetadata, RetrievalStats
from neuromem.utils.embeddings import get_embedding
import uuid


class IngestWorker(BaseWorker):
    """Handles high-priority memory ingestion tasks"""
    
    def __init__(self, scheduler, metrics, controller, config):
        super().__init__("IngestWorker", scheduler, metrics)
        self.controller = controller
        self.config = config
        # Get embedding model from controller (which has the correct config)
        self.embedding_model = controller.embedding_model
    
    def _work_iteration(self):
        """Process one task from the queue"""
        # Only process CRITICAL priority tasks
        task = self.scheduler.dequeue(timeout=1.0)
        
        if task is None:
            return
        
        if task.task_type != TaskType.OBSERVE:
            # Put it back for maintenance worker
            self.scheduler.enqueue(task)
            return
        
        # Process observe task
        start_time = time.time()
        try:
            self._process_observe(task)
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record('task.duration', duration_ms, {'type': 'observe'})
        except Exception as e:
            self.metrics.increment('task.failed', {'type': 'observe', 'error': str(e)})
            raise
    
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
                print(f"Error in async auto-tagging: {e}")
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
