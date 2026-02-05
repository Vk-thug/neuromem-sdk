"""Brain-faithful cognitive policies"""

from neuromem.core.policies.salience import SalienceCalculator
from neuromem.core.policies.reconsolidation import ReconsolidationPolicy
from neuromem.core.policies.conflict_resolution import ConflictResolver
from neuromem.core.policies.optimization import EmbeddingOptimizationPolicy

__all__ = [
    'SalienceCalculator',
    'ReconsolidationPolicy',
    'ConflictResolver',
    'EmbeddingOptimizationPolicy'
]
