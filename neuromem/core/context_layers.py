"""
Layered context loading system for efficient memory retrieval.

Inspired by MemPalace's L0-L3 system, provides four tiers of context
with increasing detail and cost:

  L0 (Identity)  — User-defined identity text (~100 tokens, always loaded)
  L1 (Essential)  — Top-15 highest-salience memories (~500-800 tokens)
  L2 (On-demand)  — Topic-filtered retrieval (~200-500 tokens)
  L3 (Deep search) — Full semantic search (unlimited, explicit trigger)

Target: Wake-up cost <200 tokens (L0 + L1 summary).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ContextLayer:
    """A single layer of context."""

    level: int  # 0-3
    name: str
    content: str
    token_estimate: int
    source_ids: tuple[str, ...] = ()


@dataclass
class LayeredContext:
    """Complete context across all loaded layers."""

    layers: List[ContextLayer] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(layer.token_estimate for layer in self.layers)

    @property
    def full_text(self) -> str:
        return "\n\n".join(layer.content for layer in self.layers if layer.content)

    def up_to_level(self, max_level: int) -> str:
        """Get concatenated context up to a given level."""
        parts = [
            layer.content for layer in self.layers if layer.level <= max_level and layer.content
        ]
        return "\n\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


class ContextManager:
    """
    Manages layered context loading for a user.

    Usage:
        ctx_mgr = ContextManager(controller, user_id)
        ctx_mgr.set_identity("Senior Python developer at Acme Corp")
        context = ctx_mgr.load(max_level=1)  # L0 + L1
        context = ctx_mgr.load(max_level=2, topic="career")  # + L2
        context = ctx_mgr.load(max_level=3, query="project timeline")  # + L3
    """

    def __init__(
        self,
        controller: Any,  # MemoryController
        user_id: str,
        identity_text: str = "",
        essential_limit: int = 15,
    ):
        self.controller = controller
        self.user_id = user_id
        self.identity_text = identity_text
        self.essential_limit = essential_limit
        self._essential_cache: Optional[ContextLayer] = None

    def set_identity(self, text: str) -> None:
        """Set L0 identity text."""
        self.identity_text = text

    def _build_l0(self) -> ContextLayer:
        """L0: Identity layer (~100 tokens)."""
        return ContextLayer(
            level=0,
            name="Identity",
            content=self.identity_text,
            token_estimate=_estimate_tokens(self.identity_text),
        )

    def _build_l1(self) -> ContextLayer:
        """L1: Essential facts — top-N highest-salience memories."""
        if self._essential_cache is not None:
            return self._essential_cache

        memories = self.controller.list_memories(limit=self.essential_limit * 3)

        # Sort by salience descending, take top N
        memories.sort(key=lambda m: m.salience, reverse=True)
        top = memories[: self.essential_limit]

        if not top:
            layer = ContextLayer(level=1, name="Essential", content="", token_estimate=0)
            self._essential_cache = layer
            return layer

        parts = [m.content for m in top]
        content = "\n".join(parts)
        ids = tuple(m.id for m in top)

        layer = ContextLayer(
            level=1,
            name="Essential",
            content=content,
            token_estimate=_estimate_tokens(content),
            source_ids=ids,
        )
        self._essential_cache = layer
        return layer

    def _build_l2(self, topic: str = "") -> ContextLayer:
        """L2: On-demand topic-filtered retrieval."""
        memories = self.controller.list_memories(limit=200)

        if topic:
            filtered = [m for m in memories if m.metadata.get("topic", "") == topic]
        else:
            filtered = memories[:50]

        if not filtered:
            return ContextLayer(level=2, name="On-demand", content="", token_estimate=0)

        # Take top 10 by salience
        filtered.sort(key=lambda m: m.salience, reverse=True)
        top = filtered[:10]
        content = "\n".join(m.content for m in top)
        ids = tuple(m.id for m in top)

        return ContextLayer(
            level=2,
            name="On-demand",
            content=content,
            token_estimate=_estimate_tokens(content),
            source_ids=ids,
        )

    def _build_l3(
        self, query: str, embedding: Optional[List[float]] = None, k: int = 10
    ) -> ContextLayer:
        """L3: Deep semantic search — full retrieval pipeline."""
        if not query:
            return ContextLayer(level=3, name="Deep search", content="", token_estimate=0)

        try:
            from neuromem.utils.embeddings import get_embedding

            if embedding is None:
                model = "text-embedding-3-large"
                if hasattr(self.controller, "embedding_model"):
                    model = self.controller.embedding_model
                embedding = get_embedding(query, model)

            items = self.controller.retrieve(
                embedding=embedding,
                task_type="chat",
                k=k,
                query_text=query,
            )

            content = "\n".join(item.content for item in items)
            ids = tuple(item.id for item in items)

            return ContextLayer(
                level=3,
                name="Deep search",
                content=content,
                token_estimate=_estimate_tokens(content),
                source_ids=ids,
            )
        except Exception as e:
            logger.warning("L3 deep search failed", extra={"error": str(e)})
            return ContextLayer(level=3, name="Deep search", content="", token_estimate=0)

    def load(
        self,
        max_level: int = 1,
        topic: str = "",
        query: str = "",
        embedding: Optional[List[float]] = None,
    ) -> LayeredContext:
        """
        Load context up to the specified level.

        Args:
            max_level: Maximum context level (0=identity, 1=essential, 2=on-demand, 3=deep)
            topic: Topic filter for L2 (optional)
            query: Query for L3 deep search (optional)
            embedding: Pre-computed query embedding for L3 (optional)

        Returns:
            LayeredContext with all loaded layers.
        """
        layers: List[ContextLayer] = []

        layers.append(self._build_l0())

        if max_level >= 1:
            layers.append(self._build_l1())

        if max_level >= 2:
            layers.append(self._build_l2(topic))

        if max_level >= 3:
            layers.append(self._build_l3(query, embedding))

        return LayeredContext(layers=layers)

    def invalidate_cache(self) -> None:
        """Clear the L1 essential cache (call after new memories are stored)."""
        self._essential_cache = None
