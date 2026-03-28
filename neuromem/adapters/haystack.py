"""
Haystack adapter for NeuroMem.

Provides @component-decorated classes for retrieval, writing, and
graph-expanded context retrieval within Haystack pipelines.

Usage:
    from neuromem import NeuroMem
    from neuromem.adapters.haystack import NeuroMemRetriever, NeuroMemWriter
    from haystack import Pipeline

    memory = NeuroMem.for_haystack(user_id="user_123")

    pipeline = Pipeline()
    pipeline.add_component("retriever", NeuroMemRetriever(memory, top_k=5))
    pipeline.add_component("writer", NeuroMemWriter(memory))

    result = pipeline.run({"retriever": {"query": "database decisions"}})
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from haystack import Document, component

    HAYSTACK_AVAILABLE = True
except ImportError:
    HAYSTACK_AVAILABLE = False
    Document = None  # type: ignore
    component = None  # type: ignore

logger = logging.getLogger(__name__)


if HAYSTACK_AVAILABLE:

    @component
    class NeuroMemRetriever:
        """Haystack component that retrieves documents from NeuroMem.

        Args:
            neuromem: NeuroMem instance
            top_k: Default number of documents to retrieve

        Usage in a pipeline:
            pipeline.add_component("retriever", NeuroMemRetriever(memory, top_k=5))
        """

        def __init__(self, neuromem: Any, top_k: int = 5):
            self.neuromem = neuromem
            self.top_k = top_k

        @component.output_types(documents=List[Document])
        def run(self, query: str, top_k: Optional[int] = None) -> Dict[str, List[Document]]:
            """Retrieve documents from NeuroMem.

            Args:
                query: The search query
                top_k: Number of documents (overrides default)

            Returns:
                Dict with 'documents' key containing list of Haystack Documents
            """
            k = top_k or self.top_k
            try:
                results = self.neuromem.retrieve(query=query, task_type="chat", k=k)
                documents = [
                    Document(
                        content=r.content,
                        meta={
                            "memory_id": r.id,
                            "memory_type": r.memory_type.value,
                            "salience": r.salience,
                            "confidence": r.confidence,
                            "tags": r.tags,
                            "created_at": r.created_at.isoformat(),
                            "strength": r.strength,
                        },
                    )
                    for r in results
                ]
            except Exception as e:
                logger.warning("NeuroMem retrieval failed", extra={"error": str(e)[:200]})
                documents = []
            return {"documents": documents}

    @component
    class NeuroMemWriter:
        """Haystack component that stores documents as NeuroMem memories.

        Args:
            neuromem: NeuroMem instance
            template: Optional memory template (preference, decision, fact, goal)

        Usage in a pipeline:
            pipeline.add_component("writer", NeuroMemWriter(memory))
        """

        def __init__(self, neuromem: Any, template: Optional[str] = None):
            self.neuromem = neuromem
            self.template = template

        @component.output_types(memories_written=int)
        def run(self, documents: List[Document]) -> Dict[str, int]:
            """Write documents to NeuroMem as memories.

            Args:
                documents: List of Haystack Documents to store

            Returns:
                Dict with 'memories_written' count
            """
            count = 0
            for doc in documents:
                try:
                    user_input = doc.content
                    response = doc.meta.get("response", "Stored from Haystack pipeline")
                    self.neuromem.observe(user_input, response, template=self.template)
                    count += 1
                except Exception:
                    pass
            return {"memories_written": count}

    @component
    class NeuroMemContextRetriever:
        """Haystack component that retrieves graph-expanded context from NeuroMem.

        Returns documents with expanded_context in metadata.

        Args:
            neuromem: NeuroMem instance
            top_k: Default number of documents to retrieve

        Usage in a pipeline:
            pipeline.add_component("retriever", NeuroMemContextRetriever(memory, top_k=5))
        """

        def __init__(self, neuromem: Any, top_k: int = 5):
            self.neuromem = neuromem
            self.top_k = top_k

        @component.output_types(documents=List[Document])
        def run(self, query: str, top_k: Optional[int] = None) -> Dict[str, List[Document]]:
            """Retrieve graph-expanded context from NeuroMem.

            Args:
                query: The search query
                top_k: Number of documents (overrides default)

            Returns:
                Dict with 'documents' key containing list of Haystack Documents
            """
            k = top_k or self.top_k
            try:
                results = self.neuromem.retrieve_with_context(query=query, task_type="chat", k=k)
                documents = [
                    Document(
                        content=r.content,
                        meta={
                            "memory_id": r.id,
                            "memory_type": r.memory_type.value,
                            "confidence": r.confidence,
                            "expanded_context": r.metadata.get("expanded_context", ""),
                        },
                    )
                    for r in results
                ]
            except Exception as e:
                logger.warning(
                    "NeuroMem context retrieval failed",
                    extra={"error": str(e)[:200]},
                )
                documents = []
            return {"documents": documents}

else:
    # Stubs when haystack is not installed
    class NeuroMemRetriever:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any):
            raise ImportError(
                "haystack-ai is not installed. Install it with: pip install haystack-ai"
            )

    class NeuroMemWriter:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any):
            raise ImportError(
                "haystack-ai is not installed. Install it with: pip install haystack-ai"
            )

    class NeuroMemContextRetriever:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any):
            raise ImportError(
                "haystack-ai is not installed. Install it with: pip install haystack-ai"
            )


__all__ = [
    "NeuroMemRetriever",
    "NeuroMemWriter",
    "NeuroMemContextRetriever",
]
