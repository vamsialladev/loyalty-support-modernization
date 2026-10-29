"""Deterministic synthetic data generator (spec B.5, E.1, F2, Appendix H1; ADR-0028).

Same seed and scale -> byte-identical JSONL and the same manifest checksums. The generator never imports `app`.
"""

GENERATOR_VERSION = "1.0.0"
DATASET_VERSION = "v1"
DEFAULT_SEED = 20261102
