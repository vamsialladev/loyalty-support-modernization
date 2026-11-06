"""Who is asking: normalized, fuzzy member lookup with a candidate list (D01, D02, D13, D18).

A candidate counts as the member only with **two matching identifiers** (catalog, D01 and D18). A name alone, or a
number alone, is never enough, so a mistyped number that happens to be someone else's account finds nobody to act on.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.arms.conventional.config import ConventionalConfig
from app.domain.customer_records import Member
from app.ports.customer_systems import CustomerSystems, RecordNotFound

MAX_MERGE_HOPS = 3
MAX_NEAR_DISTANCE = 2
MAX_CANDIDATES_SHOWN = 5
EXACT_NUMBER, NEAR_NUMBER, EMAIL, NAME = "member_number", "member_number_near", "email", "name"
_WEIGHT = {EXACT_NUMBER: 4, EMAIL: 3, NAME: 2, NEAR_NUMBER: 1}


class IdentityStatus(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_SECOND_IDENTIFIER = "needs_second_identifier"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class IdentityClaim:
    member_numbers: tuple[str, ...] = ()
    email: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class Candidate:
    member: Member
    matched: tuple[str, ...]
    via_retired_number: str | None = None

    @property
    def weight(self) -> int:
        return sum(_WEIGHT[m] for m in self.matched)


@dataclass(frozen=True)
class IdentityResult:
    status: IdentityStatus
    member: Member | None
    candidates: tuple[Candidate, ...]


def fold(text: str) -> str:
    """Case and accents don't count."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def normalize_email(email: str) -> str:
    """Case, dots in the local part and `+tags` don't identify a person differently (D13)."""
    local, _, domain = email.strip().lower().partition("@")
    return f"{local.split('+', 1)[0].replace('.', '')}@{domain}"


def edit_distance(a: str, b: str) -> int:
    """Levenshtein with adjacent transpositions counted as one edit: how people mistype numbers."""
    rows = [list(range(len(b) + 1))]
    for i, ca in enumerate(a, 1):
        row = [i]
        for j, cb in enumerate(b, 1):
            cost = min(rows[-1][j] + 1, row[j - 1] + 1, rows[-1][j - 1] + (ca != cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cost = min(cost, rows[-2][j - 2] + 1)
            row.append(cost)
        rows.append(row)
    return rows[-1][-1]


def digits_of(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def is_near_number(given: str, actual: str) -> bool:
    a, b = digits_of(given), digits_of(actual)
    return bool(a) and len(a) == len(b) and 0 < edit_distance(a, b) <= MAX_NEAR_DISTANCE


def first_names_match(given: str, actual: str, config: ConventionalConfig) -> bool:
    a, b = fold(given), fold(actual)
    return a == b or a in config.nicknames.get(b, frozenset())


def names_match(name: str, member: Member, config: ConventionalConfig) -> bool:
    parts = name.split()
    if len(parts) < 2:
        return False
    return fold(" ".join(parts[1:])) == fold(member.last_name) and first_names_match(
        parts[0], member.first_name, config
    )


def score(claim: IdentityClaim, member: Member, config: ConventionalConfig, via: str | None = None) -> tuple[str, ...]:
    matched = []
    numbers = {member.member_number, *([via] if via else [])}
    if any(n in numbers for n in claim.member_numbers):
        matched.append(EXACT_NUMBER)
    elif any(is_near_number(n, member.member_number) for n in claim.member_numbers):
        matched.append(NEAR_NUMBER)
    if claim.email and normalize_email(claim.email) == normalize_email(member.email):
        matched.append(EMAIL)
    if claim.name and names_match(claim.name, member, config):
        matched.append(NAME)
    return tuple(matched)


def current_profile(systems: CustomerSystems, member: Member) -> tuple[Member, str | None]:
    """Follow `merged_into` to the active profile (D02). Returns the profile and the retired number it came from."""
    retired = None
    for _ in range(MAX_MERGE_HOPS):
        if not member.merged_into:
            return member, retired
        retired = retired or member.member_number
        try:
            member = systems.get_member(member.merged_into)
        except RecordNotFound:
            return member, retired
    return member, retired


def find_candidates(systems: CustomerSystems, claim: IdentityClaim, config: ConventionalConfig) -> list[Candidate]:
    found: list[Member] = []
    for number in claim.member_numbers:
        try:
            found.append(systems.get_member(number))
        except RecordNotFound:
            continue
    if claim.email:
        found += systems.find_members(email=claim.email)
        if claim.email.strip().lower() != claim.email:
            found += systems.find_members(email=claim.email.strip().lower())
    if claim.name and len(claim.name.split()) >= 2:
        found += systems.find_members(family_name=" ".join(claim.name.split()[1:]))
    candidates: dict[str, Candidate] = {}
    for member in found:
        profile, via = current_profile(systems, member)
        matched = score(claim, profile, config, via)
        known = candidates.get(profile.member_number)
        if matched and (known is None or len(matched) > len(known.matched)):
            candidates[profile.member_number] = Candidate(profile, matched, via)
    return sorted(candidates.values(), key=lambda c: (-c.weight, c.member.member_number))


def same_person(a: Member, b: Member) -> bool:
    """Duplicate profiles (D01): same phone and date of birth, and the same name."""
    return (
        a.phone == b.phone
        and a.date_of_birth is not None
        and a.date_of_birth == b.date_of_birth
        and fold(a.last_name) == fold(b.last_name)
        and fold(a.first_name) == fold(b.first_name)
    )


def choose(candidates: list[Candidate]) -> IdentityResult:
    shown = tuple(candidates[:MAX_CANDIDATES_SHOWN])
    if not candidates:
        return IdentityResult(IdentityStatus.NOT_FOUND, None, ())
    confirmed = [c for c in candidates if len(c.matched) >= 2]
    if not confirmed:
        return IdentityResult(IdentityStatus.NEEDS_SECOND_IDENTIFIER, None, shown)
    best = confirmed[0]
    rivals = [c for c in confirmed[1:] if c.weight == best.weight and not same_person(c.member, best.member)]
    if rivals:
        return IdentityResult(IdentityStatus.AMBIGUOUS, None, shown)
    return IdentityResult(IdentityStatus.CONFIRMED, best.member, shown)


def linked_profiles(systems: CustomerSystems, member: Member) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(duplicate profiles, numbers merged into this one). Reads the phone and name searches; both are data checks."""
    others = {m.member_number: m for m in systems.find_members(phone=member.phone)} if member.phone else {}
    others |= {m.member_number: m for m in systems.find_members(family_name=member.last_name)}
    others.pop(member.member_number, None)
    duplicates = sorted(n for n, m in others.items() if not m.merged_into and same_person(m, member))
    merged = sorted(n for n, m in others.items() if m.merged_into == member.member_number)
    return tuple(duplicates), tuple(merged)
