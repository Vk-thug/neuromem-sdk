"""
CA3 — Pattern Completion (Autoassociative Attractor Network).

CA3 contains extensive recurrent collateral connections that implement
attractor dynamics. Given a partial or noisy cue, CA3 iteratively
converges to the nearest stored memory pattern.

Algorithm (Hopfield-inspired):
1. Compute similarity between the cue and all stored patterns
2. Weight the stored patterns by their similarity to the cue
3. Normalize to produce a "completed" pattern
4. Repeat for N iterations (default 3)

The sigmoidal input-output relationship creates three regimes:
- Small differences → pattern completion (outputs converge)
- Large differences → pattern separation (outputs diverge)

Reference: Rolls (2013), "The mechanisms for pattern completion and
pattern separation in the hippocampus"
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from neuromem.constants import DEFAULT_COMPLETION_ITERATIONS


class PatternCompleter:
    """CA3 autoassociative recall from partial cues.

    Parameters
    ----------
    iterations:
        Number of attractor dynamics iterations (default 3).
    temperature:
        Softmax temperature for attention weights. Lower = sharper
        attention (stronger pattern completion). Higher = softer
        (more averaging). Default 0.1.
    """

    def __init__(
        self,
        iterations: int = DEFAULT_COMPLETION_ITERATIONS,
        temperature: float = 0.1,
    ) -> None:
        self.iterations = iterations
        self.temperature = temperature

    def complete(
        self,
        partial_embedding: List[float],
        candidate_embeddings: List[List[float]],
        candidate_ids: List[str],
    ) -> Optional[Tuple[str, float]]:
        """Recall the best matching stored pattern from a partial cue.

        Parameters
        ----------
        partial_embedding:
            The query/cue embedding (may be partial or noisy).
        candidate_embeddings:
            Stored memory embeddings to match against.
        candidate_ids:
            IDs corresponding to each candidate embedding.

        Returns
        -------
        Tuple of (best_memory_id, completion_score) or None if no candidates.
            completion_score is in [0, 1], higher = stronger attractor match.
        """
        if not candidate_embeddings:
            return None

        cue = np.array(partial_embedding, dtype=np.float64)
        patterns = np.array(candidate_embeddings, dtype=np.float64)

        # Normalize all vectors for cosine similarity
        cue_norm = np.linalg.norm(cue)
        if cue_norm < 1e-12:
            return None
        cue = cue / cue_norm

        norms = np.linalg.norm(patterns, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        patterns = patterns / norms

        # Iterative attractor dynamics
        state = cue.copy()
        for _ in range(self.iterations):
            # Compute similarities (recurrent activation)
            similarities = patterns @ state

            # Softmax attention weights (biological: firing rate competition)
            exp_sim = np.exp((similarities - similarities.max()) / self.temperature)
            weights = exp_sim / (exp_sim.sum() + 1e-12)

            # Weighted combination of stored patterns (attractor update)
            state = weights @ patterns

            # Re-normalize (maintain unit sphere)
            state_norm = np.linalg.norm(state)
            if state_norm < 1e-12:
                break
            state = state / state_norm

        # Final similarities after convergence
        final_similarities = patterns @ state
        best_idx = int(np.argmax(final_similarities))
        best_score = float(final_similarities[best_idx])

        return (candidate_ids[best_idx], best_score)
