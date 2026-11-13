"""Telemetry wiring (spec F.1, L2; OPS-02, LIVE-03): traces, structured logs and the GenAI attribute names.

Only the edges import this package (app factory, worker, mock API, adapters' callers). The domain layer imports
nothing from it. Everything here works with no collector: traces then exist only to stamp trace IDs on log lines.
"""
