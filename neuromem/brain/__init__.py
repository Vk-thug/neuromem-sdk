"""
Brain-faithful memory processing system.

Implements computational models of six brain regions:
- Hippocampus: pattern separation (DG), completion (CA3), gating (CA1), replay (SWR)
- Neocortex: schema-based semantic integration (CLS theory)
- Prefrontal cortex: working memory buffer (Cowan's 4-slot limit)
- Amygdala: emotional tagging and flashbulb memory
- Basal ganglia: TD learning for retrieval reward signals
"""

from neuromem.brain.types import BrainState, SparseCode

__all__ = ["BrainState", "SparseCode"]


def get_brain_system_class():
    """Lazy import to avoid circular dependencies during Phase 1."""
    from neuromem.brain.system import BrainSystem

    return BrainSystem
