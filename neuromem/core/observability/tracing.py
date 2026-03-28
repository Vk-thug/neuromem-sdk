"""
Distributed tracing for memory operations.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Span:
    """A single trace span"""
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self):
        """Mark span as complete"""
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000


class MemoryTrace:
    """Trace for a memory operation"""
    
    def __init__(self, trace_id: str = None, operation: str = "memory_operation"):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.operation = operation
        self.spans: List[Span] = []
        self.start_time = datetime.now(timezone.utc)
        self.end_time = None
        self.metadata = {}
    
    def start_span(self, name: str, metadata: Dict[str, Any] = None) -> Span:
        """Start a new span"""
        span = Span(
            name=name,
            start_time=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        self.spans.append(span)
        return span
    
    def finish(self):
        """Mark trace as complete"""
        self.end_time = datetime.now(timezone.utc)
        # Finish any open spans
        for span in self.spans:
            if span.end_time is None:
                span.finish()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dict"""
        return {
            'trace_id': self.trace_id,
            'operation': self.operation,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': (self.end_time - self.start_time).total_seconds() * 1000 if self.end_time else None,
            'metadata': self.metadata,
            'spans': [
                {
                    'name': span.name,
                    'start_time': span.start_time.isoformat(),
                    'end_time': span.end_time.isoformat() if span.end_time else None,
                    'duration_ms': span.duration_ms,
                    'metadata': span.metadata
                }
                for span in self.spans
            ]
        }
