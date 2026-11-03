"""Arm A's intake routing rule (defect D20): a message that mentions a refund goes to the billing queue.

The rule is the legacy system's real behaviour: a keyword match on the whole message, so a points claim that also
asks for a refund waits in billing and never reaches the points queue.
"""

from __future__ import annotations

POINTS_QUEUE = "points"
BILLING_QUEUE = "billing"


def route(text: str) -> str:
    return BILLING_QUEUE if "refund" in text.lower() else POINTS_QUEUE
