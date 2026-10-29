"""Derived random streams: each component gets its own seeded stream, so adding one never shifts another."""

import random


def rng(seed: int, *parts: object) -> random.Random:
    """A `random.Random` seeded from the master seed and a component path, e.g. rng(seed, "world", "members").

    String seeds are hashed with SHA-512 by CPython (seeding version 2), so the stream is stable across runs and
    machines and does not depend on PYTHONHASHSEED.
    """
    return random.Random(":".join([str(seed), *map(str, parts)]))
