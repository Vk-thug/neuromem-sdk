"""
Basal Ganglia — Temporal Difference Learning.

Implements TD(0) reward learning for retrieval feedback. When a retrieved
memory is marked as helpful (positive reward) or unhelpful (negative),
the value estimate for that memory's topic cluster is updated.

The Go/NoGo dual pathway is modeled as:
- Positive reward → increase value (D1 dopamine burst)
- Negative reward → decrease value (D2 dopamine dip)

Future retrievals use these learned values for CA1 gating boosts.

Reference: Schultz, Dayan & Montague (1997), "A neural substrate of
prediction and reward"
"""

from __future__ import annotations

import hashlib
from typing import Dict, List


from neuromem.constants import DEFAULT_TD_ALPHA, DEFAULT_TD_GAMMA


class TDLearner:
    """Temporal difference learning for retrieval reward signals.

    Parameters
    ----------
    alpha:
        Learning rate for TD(0) updates (default 0.1).
    gamma:
        Discount factor (default 0.9).
    n_clusters:
        Number of embedding clusters for value bucketing (default 16).
    """

    def __init__(
        self,
        alpha: float = DEFAULT_TD_ALPHA,
        gamma: float = DEFAULT_TD_GAMMA,
        n_clusters: int = 16,
    ) -> None:
        self.alpha = alpha
        self.gamma = gamma
        self.n_clusters = n_clusters

    def _get_cluster_id(self, embedding: List[float]) -> str:
        """Hash an embedding to a cluster ID for coarse value bucketing.

        This is a simple LSH: take the sign of the first n_clusters
        dimensions and hash to a string key.
        """
        if len(embedding) < self.n_clusters:
            bits = "".join("1" if x > 0 else "0" for x in embedding)
        else:
            bits = "".join("1" if embedding[i] > 0 else "0" for i in range(self.n_clusters))
        return hashlib.md5(bits.encode()).hexdigest()[:8]

    def update(
        self,
        embedding: List[float],
        task_type: str,
        reward: float,
        td_values: Dict[str, Dict[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        """Apply TD(0) update to the value estimate for this cluster.

        Parameters
        ----------
        embedding:
            The memory's embedding vector (used to compute cluster ID).
        task_type:
            The task type context (e.g., "chat", "code", "planning").
        reward:
            Reward signal (+1.0 = helpful, -1.0 = unhelpful, 0 = neutral).
        td_values:
            Current task_type → cluster → value mapping (mutated in place).

        Returns
        -------
        Updated td_values dict.
        """
        cluster_id = self._get_cluster_id(embedding)

        if task_type not in td_values:
            td_values[task_type] = {}

        current_value = td_values[task_type].get(cluster_id, 0.0)

        # TD(0) update: V(s) ← V(s) + α * (reward - V(s))
        td_error = reward - current_value
        new_value = current_value + self.alpha * td_error

        # Clamp to [-1, 1]
        td_values[task_type][cluster_id] = max(-1.0, min(1.0, new_value))

        return td_values

    def get_value(
        self,
        embedding: List[float],
        task_type: str,
        td_values: Dict[str, Dict[str, float]],
    ) -> float:
        """Look up the learned value for this embedding's cluster.

        Returns 0.0 if no value has been learned yet.
        """
        cluster_id = self._get_cluster_id(embedding)
        return td_values.get(task_type, {}).get(cluster_id, 0.0)

    def get_cluster_id(self, embedding: List[float]) -> str:
        """Public access to cluster ID for metadata tagging."""
        return self._get_cluster_id(embedding)
