"""Versioned policy documents: parsing, sections and which version is in force on a day (spec B.6, Appendix B). Pure."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

MISSING_POINTS = "missing-points-requests"
EARNING = "guest-rewards-earning"
DRAFT, PUBLISHED, SUPERSEDED = "draft", "published", "superseded"

_HEADING = re.compile(r"^##\s+(\d+(?:\.\d+)?)\.?\s+(.+?)\s*$", re.MULTILINE)
_REQUIRED = ("policy_id", "title", "customer", "version", "effective_from", "status", "sections")


class PolicyFormatError(ValueError):
    """A policy document can't be read as a versioned policy (the message says what is wrong)."""


@dataclass(frozen=True)
class PolicyRef:
    """What a citation points to. `section` is None when the version has no section for the rule."""

    policy_id: str
    version: int
    section: str | None = None

    def __str__(self) -> str:
        cited = f"{self.policy_id}@v{self.version}"
        return f"{cited}#{self.section}" if self.section else cited


@dataclass(frozen=True)
class PolicyVersion:
    policy_id: str
    version: int
    title: str
    customer: str
    effective_from: date
    effective_to: date | None
    status: str
    sections: tuple[str, ...]
    rules: dict[str, Any]

    def ref(self, *sections: str) -> PolicyRef:
        """A citation of the first of `sections` this version has."""
        found = next((section for section in sections if section in self.sections), None)
        return PolicyRef(self.policy_id, self.version, found)

    def in_force_on(self, day: date) -> bool:
        return (
            self.status != DRAFT
            and self.effective_from <= day
            and (self.effective_to is None or day <= self.effective_to)
        )


@dataclass(frozen=True)
class PolicySection:
    section_id: str
    heading: str
    text: str


@dataclass(frozen=True)
class PolicyDocument:
    version: PolicyVersion
    sections: tuple[PolicySection, ...]
    checksum: str


def _as_date(value: object, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise PolicyFormatError(f"{field} is not a date: {value!r}") from exc


def parse_document(text: str) -> PolicyDocument:
    """Read one Markdown policy file: YAML front matter, then `## <section id> <heading>` sections."""
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise PolicyFormatError("the document has no front matter")
    front = yaml.safe_load(parts[1])
    if not isinstance(front, dict):
        raise PolicyFormatError("the front matter is not a mapping")
    missing = [name for name in _REQUIRED if name not in front]
    if missing:
        raise PolicyFormatError("the front matter is missing: " + ", ".join(missing))
    body = parts[2]
    headings = list(_HEADING.finditer(body))
    sections = tuple(
        PolicySection(
            match.group(1),
            match.group(2),
            body[match.end() : headings[i + 1].start() if i + 1 < len(headings) else len(body)].strip(),
        )
        for i, match in enumerate(headings)
    )
    listed = tuple(str(s) for s in front["sections"])
    found = tuple(section.section_id for section in sections)
    if listed != found:
        raise PolicyFormatError(f"the front matter lists sections {listed}, but the document has {found}")
    end = front.get("effective_to")
    version = PolicyVersion(
        str(front["policy_id"]),
        int(front["version"]),
        str(front["title"]),
        str(front["customer"]),
        _as_date(front["effective_from"], "effective_from"),
        _as_date(end, "effective_to") if end else None,
        str(front["status"]),
        listed,
        dict(front.get("rules") or {}),
    )
    return PolicyDocument(version, sections, hashlib.sha256(text.encode("utf-8")).hexdigest())


def versions_in_force(versions: Iterable[PolicyVersion], policy_id: str, day: date) -> list[PolicyVersion]:
    """Every non-draft version of `policy_id` in force on `day`. More than one, or none, is the caller's to handle:
    a recommendation can't rest on either (spec B.6: never invent policy)."""
    return sorted((v for v in versions if v.policy_id == policy_id and v.in_force_on(day)), key=lambda v: v.version)
