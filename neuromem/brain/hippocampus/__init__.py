"""
Hippocampal memory system.

- Dentate Gyrus (PatternSeparator): Sparse expansion coding to decorrelate similar inputs
- CA3 (PatternCompleter): Autoassociative attractor network for recall from partial cues
- CA1 (CA1Gate): Value-based output gating for memory selection
- Sharp-Wave Ripples (RippleReplayWorker): Offline consolidation replay
"""
