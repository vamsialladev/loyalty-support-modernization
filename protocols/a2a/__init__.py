"""A2A: a loyalty investigation coordinator asks a reservation evidence specialist for stay evidence (spec G.4).

Two separately running services, on the official `a2a-sdk` (spec 1.0, JSON-RPC binding):

    FEATURE_A2A=true uv run python -m protocols.a2a.specialist        # the reservations team's agent
    FEATURE_A2A=true uv run python -m protocols.a2a.coordinator --case 12

A lab, not the core (ADR-0025): the artifact is evidence for a person to review, and nothing a remote agent returns
can approve, credit or change a case. When a plain REST call is enough: `docs/a2a-vs-rest.md`.
"""
