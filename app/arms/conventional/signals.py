"""What arm B reads from a member's message with plain rules (D05, D16, D17, D19, D20, D23).

Everything here treats the message as data: it only looks for shapes and words. Nothing a member writes can change a
rule, an amount or a permission (S01, S02).
"""

from __future__ import annotations

import re

POINTS_QUEUE = "points"
BILLING_QUEUE = "billing"

_WORD = re.compile(r"[a-zà-ÿ']+")
_MEMBER = re.compile(r"\bGR-\d{5}\b", re.IGNORECASE)
_STAY = re.compile(r"\b(?:BR|ML)-\d{4}\b", re.IGNORECASE)
_PARTNER = re.compile(r"\bTRV-\d{8}\b", re.IGNORECASE)
_POINTS_WORDS = frozenset(
    {"points", "point", "credit", "credited", "credits", "rewards", "loyalty", "stay", "stayed", "posted"}
    | {"puntos", "pontos", "punkte"}
)
_OUT_OF_SCOPE = {
    "refund": ("refund", "refunded", "chargeback", "overcharged", "reimburse", "reimbursement", "charged"),
    "complaint": ("loud", "noisy", "noise", "dirty", "rude", "complaint", "complain", "unacceptable", "broken"),
}
# Words a reader recognises at a glance as Spanish, French, Portuguese or German (the D23 languages).
_FOREIGN = {
    "es": frozenset({"hola", "gracias", "puntos", "estancia", "cuenta", "estuve", "aparecen"}),
    "fr": frozenset({"bonjour", "merci", "j'ai", "séjourné", "compte", "n'apparaissent"}),
    "pt": frozenset({"olá", "obrigado", "obrigada", "pontos", "minha", "meu", "conta", "não", "estadia", "fiquei"}),
    "de": frozenset({"hallo", "danke", "punkte", "mein", "meinem", "konto", "aufenthalt", "nicht", "gutgeschrieben"}),
}
_MORE_STAYS = re.compile(
    r"\b(?:also|as well|and my|another stay|other stays?|same for|plus my)\b.{0,60}\b(?:stay|visit|trip|lodge|resort)\b"
    r"|\b(?:stay|visit|trip)\b.{0,60}\b(?:also|too|as well)\b",
    re.IGNORECASE | re.DOTALL,
)


def _unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def detect_language(text: str) -> str | None:
    """Two unmistakable words of one language. Terse English ("Missing points. Beach Resort.") stays English."""
    words = _WORD.findall(text.lower())
    counts = {code: sum(w in vocabulary for w in words) for code, vocabulary in _FOREIGN.items()}
    best = max(counts, key=lambda code: counts[code])
    return best if counts[best] >= 2 else None


def out_of_scope_topics(text: str) -> tuple[str, ...]:
    words = set(_WORD.findall(text.lower()))
    return tuple(topic for topic, vocabulary in _OUT_OF_SCOPE.items() if words & set(vocabulary))


def route(text: str) -> str:
    """D20's process fix: a points claim stays with the points team even when the message also mentions a refund. Only a
    message that is about billing and nothing else goes to the billing queue."""
    words = set(_WORD.findall(text.lower()))
    if "refund" in out_of_scope_topics(text) and not words & _POINTS_WORDS:
        return BILLING_QUEUE
    return POINTS_QUEUE


def mentions_more_stays(text: str) -> bool:
    return bool(_MORE_STAYS.search(text))


def member_numbers_in(text: str) -> tuple[str, ...]:
    return _unique([m.upper() for m in _MEMBER.findall(text)])


def confirmations_in(text: str) -> tuple[str, ...]:
    return _unique([m.upper() for m in _STAY.findall(text)] + [m.upper() for m in _PARTNER.findall(text)])


def signoff_name(text: str) -> str | None:
    """The name on the last line ("Thanks, Clara Kowalski" -> "Clara Kowalski"), or None."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    last = lines[-1].split(", ", 1)[-1].rstrip(".")
    parts = last.split()
    return last if 2 <= len(parts) <= 4 and all(p[:1].isupper() for p in parts) else None
