"""Stored policy versions: loading, which version applies on a date, search, exact excerpts (spec B.6, POL-02 to 04).

Search is Postgres full-text (`websearch_to_tsquery`, so user text can't break the query). Offline tests run on SQLite,
which has no full-text search, so a small word match stands in; `tests/test_policy_postgres.py` tests the real one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.policy import DRAFT, MISSING_POINTS, PolicyDocument, PolicyRef, PolicyVersion, parse_document
from app.persistence.models import PolicyChunk, PolicyVersionRow

# Uses the same expression as the GIN index in migration 0003. The query text is always a bound parameter.
_POSTGRES_SEARCH = text(
    "SELECT id FROM policy_chunks "
    "WHERE policy_version_id = ANY(:versions) "
    "AND to_tsvector('english', heading || ' ' || text) @@ websearch_to_tsquery('english', :q) "
    "ORDER BY ts_rank(to_tsvector('english', heading || ' ' || text), websearch_to_tsquery('english', :q)) DESC, id "
    "LIMIT :limit"
)
_STOPWORDS = frozenset({"a", "an", "and", "are", "for", "in", "is", "it", "my", "of", "on", "or", "the", "to", "was"})
_WORD = re.compile(r"[a-z0-9]+")


class PolicyChanged(Exception):
    """A stored version's source differs from what is being loaded. A version never changes: publish a new one."""


@dataclass(frozen=True)
class Citation:
    """What a citation opens: the exact stored excerpt and version, with where and when it was read (spec B.6)."""

    ref: PolicyRef
    title: str
    heading: str
    text: str
    effective_from: str
    effective_to: str | None
    status: str
    source_checksum: str
    retrieved_at_utc: str


def to_domain(row: PolicyVersionRow) -> PolicyVersion:
    return PolicyVersion(
        row.policy_id,
        row.version,
        row.title,
        row.customer_id,
        date.fromisoformat(row.effective_from),
        date.fromisoformat(row.effective_to) if row.effective_to else None,
        row.status,
        tuple(row.sections),
        dict(row.rules),
    )


def version_rows(s: Session, customer_id: str) -> list[PolicyVersionRow]:
    query = select(PolicyVersionRow).where(PolicyVersionRow.customer_id == customer_id)
    return list(s.scalars(query.order_by(PolicyVersionRow.policy_id, PolicyVersionRow.version)))


def published_versions(s: Session, customer_id: str) -> tuple[PolicyVersion, ...]:
    """Every version that can apply to some stay: published or superseded, never a draft."""
    return tuple(to_domain(row) for row in version_rows(s, customer_id) if row.status != DRAFT)


def in_force_rows(s: Session, customer_id: str, day: date) -> list[PolicyVersionRow]:
    return [row for row in version_rows(s, customer_id) if row.status != DRAFT and to_domain(row).in_force_on(day)]


def claim_policy_refs(s: Session, customer_id: str, checkout_day: date) -> list[str]:
    """The versions in force for a checkout date, as `policy@vN` strings, sorted. What an approval binds to. Only
    complete when exactly one claim policy is in force; the caller treats anything else as "no policy to act on"."""
    return sorted(str(to_domain(row).ref()) for row in in_force_rows(s, customer_id, checkout_day))


def has_single_claim_policy(s: Session, customer_id: str, checkout_day: date) -> bool:
    rows = in_force_rows(s, customer_id, checkout_day)
    return sum(1 for row in rows if row.policy_id == MISSING_POINTS) == 1


def store_document(
    s: Session, customer_id: str, doc: PolicyDocument, source_text: str, *, status: str, created_by: str
) -> PolicyVersionRow:
    version = doc.version
    row = PolicyVersionRow(
        customer_id=customer_id,
        policy_id=version.policy_id,
        version=version.version,
        title=version.title,
        effective_from=version.effective_from.isoformat(),
        effective_to=version.effective_to.isoformat() if version.effective_to else None,
        status=status,
        sections=list(version.sections),
        rules=version.rules,
        checksum=doc.checksum,
        source_text=source_text,
        created_by=created_by,
        created_at_utc=utc_now(),
    )
    s.add(row)
    s.flush()
    for section in doc.sections:
        s.add(
            PolicyChunk(
                policy_version_id=row.id, section_id=section.section_id, heading=section.heading, text=section.text
            )
        )
    s.flush()
    return row


def load_policy_set(s: Session, customer_id: str, directory: Path) -> list[str]:
    """Load the customer's committed policy files, at the status each file states (the initial set, ADR-0057). Safe to
    run again. A file that no longer matches its stored version is refused. Returns the versions it added."""
    existing = {(r.policy_id, r.version): r for r in version_rows(s, customer_id)}
    added = []
    for path in sorted(directory.glob("*.md")):
        source = path.read_text(encoding="utf-8")
        doc = parse_document(source)
        found = existing.get((doc.version.policy_id, doc.version.version))
        if found is not None:
            if found.checksum != doc.checksum:
                raise PolicyChanged(
                    f"{path.name} differs from stored {found.policy_id} v{found.version}: publish a new version"
                )
            continue
        store_document(s, customer_id, doc, source, status=doc.version.status, created_by="seed")
        added.append(str(doc.version.ref()))
    s.commit()
    return added


def _citation(row: PolicyVersionRow, chunk: PolicyChunk) -> Citation:
    return Citation(
        PolicyRef(row.policy_id, row.version, chunk.section_id),
        row.title,
        chunk.heading,
        chunk.text,
        row.effective_from,
        row.effective_to,
        row.status,
        row.checksum,
        utc_now(),
    )


def excerpt(s: Session, customer_id: str, policy_id: str, version: int, section_id: str) -> Citation | None:
    """The exact stored excerpt of one version. Drafts are never cited."""
    query = (
        select(PolicyVersionRow, PolicyChunk)
        .join(PolicyChunk, PolicyChunk.policy_version_id == PolicyVersionRow.id)
        .where(
            PolicyVersionRow.customer_id == customer_id,
            PolicyVersionRow.policy_id == policy_id,
            PolicyVersionRow.version == version,
            PolicyVersionRow.status != DRAFT,
            PolicyChunk.section_id == section_id,
        )
    )
    found = s.execute(query).first()
    return _citation(found[0], found[1]) if found else None


def _words(content: str) -> set[str]:
    return {w for w in _WORD.findall(content.lower()) if w not in _STOPWORDS}


def search(s: Session, customer_id: str, query: str, checkout_day: date, limit: int = 5) -> list[Citation]:
    """Sections of the versions in force on `checkout_day` that match `query`, best first. No version in force finds
    nothing: never another version's text (spec B.6)."""
    rows = {row.id: row for row in in_force_rows(s, customer_id, checkout_day)}
    if not rows or not query.strip():
        return []
    if s.get_bind().dialect.name == "postgresql":
        ids = s.scalars(_POSTGRES_SEARCH, {"versions": list(rows), "q": query, "limit": limit}).all()
        by_id = {c.id: c for c in s.scalars(select(PolicyChunk).where(PolicyChunk.id.in_(ids)))}
        found = [by_id[i] for i in ids]
    else:
        wanted = _words(query)
        chunks = s.scalars(select(PolicyChunk).where(PolicyChunk.policy_version_id.in_(rows))).all()
        found = sorted(
            (c for c in chunks if wanted and all(_prefix_match(w, _words(c.heading + " " + c.text)) for w in wanted)),
            key=lambda c: c.id,
        )[:limit]
    return [_citation(rows[chunk.policy_version_id], chunk) for chunk in found]


def _prefix_match(word: str, words: set[str]) -> bool:
    stem = word[:-1] if word.endswith("s") else word
    return any(w.startswith(stem) for w in words)
