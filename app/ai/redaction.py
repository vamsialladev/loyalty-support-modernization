"""Remove what the model doesn't need from free text, before any call (SEC-05, ENT-12).

Pattern matching, so it has limits: a phone number written in words, or an address, passes through. Names stay, because
telling a nickname from a different person needs them. Member and confirmation numbers stay: they select records. The
limits are in `docs/known-limitations.md`.
"""

from __future__ import annotations

import re

_PATTERNS = (
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{6,}"), "[secret]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE), "[secret]"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), "[card]"),
    (re.compile(r"(?<![\w-])(?!\d{4}-\d{2}-\d{2}\b)\+?\d[\d ()\-.]{8,}\d\b"), "[phone]"),  # a date isn't a phone number
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
