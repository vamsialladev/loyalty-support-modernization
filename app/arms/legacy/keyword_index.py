"""Arm A's policy keyword search over a frozen index (spec B.8; defects D09, D12, D15; ADR-0047).

The index is a committed file built by `scripts/build_legacy_index.py` from the policies in force on its build date.
Search is exact-term: every query word must appear in a section, with no stemming and no synonyms (D12). The index
was never rebuilt after 2026-03-15, so it holds only the versions in force then (D09), and hits do not say which
policy version applies to a given stay (D15).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

INDEX_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_INDEX = INDEX_DIR / "keyword-index-hg-demo-2026-03-15.json"

STOPWORDS = frozenset({"a", "an", "and", "the", "of", "to", "for", "in", "on", "or", "is", "my", "i"})
_WORD = re.compile(r"[a-z0-9]+")


def terms(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


@dataclass(frozen=True)
class Section:
    ref: str  # "<policy_id>#<section_id>", what a case stores as policy evidence
    policy_id: str
    title: str
    section_id: str
    heading: str
    text: str


@dataclass(frozen=True)
class KeywordIndex:
    built_as_of: str
    sections: tuple[Section, ...]

    @classmethod
    def load(cls, path: Path = DEFAULT_INDEX) -> KeywordIndex:
        data = json.loads(path.read_text(encoding="utf-8"))
        sections = tuple(
            Section(
                ref=f"{s['policy_id']}#{s['section_id']}",
                policy_id=s["policy_id"],
                title=s["title"],
                section_id=s["section_id"],
                heading=s["heading"],
                text=s["text"],
            )
            for s in data["sections"]
        )
        return cls(data["built_as_of"], sections)

    def get(self, ref: str) -> Section | None:
        return next((s for s in self.sections if s.ref == ref), None)

    def search(self, query: str, limit: int = 10) -> list[Section]:
        wanted = terms(query)
        if not wanted:
            return []
        hits: list[tuple[int, Section]] = []
        for section in self.sections:
            words = terms(f"{section.heading} {section.text}")
            if all(w in words for w in wanted):
                hits.append((sum(words.count(w) for w in wanted), section))
        hits.sort(key=lambda h: (-h[0], h[1].ref))
        return [s for _, s in hits[:limit]]
