"""Deterministic failure injection (ADR-0038). Enabled only when MOCK_API_FAULTS=true; never in a hosted demo.

A fault comes from the `X-Mock-Fault` header, or from a seeded rule file (`MOCK_API_FAULT_RULES_FILE`) that matches a
member number or confirmation number by suffix. Rules with `times` fire that many times per process (an in-memory
counter, documented: the mock is not durable about faults, only about data).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FAULTS = {
    "auth_failure": "401 problem response",
    "rate_limited": "429 with Retry-After",
    "timeout": "delay longer than the client timeout, then a normal response",
    "unavailable": "503 with Retry-After",
    "malformed": "200 with a body that is not valid JSON",
    "schema_v1_1": "200 with a renamed field and an extra field (a future contract version)",
    "duplicate": "the same request processed twice (as a network-level retry would)",
    "partial": "first page of a paginated read succeeds, later pages return 503",
    "commit_then_lost": "the adjustment commits, then the gateway times out (504): only a status lookup tells",
    "crash_before_commit": "test only: fail after writing the ledger entry and before commit (proves atomicity)",
}


@dataclass
class Rule:
    fault: str
    member_suffix: str | None = None
    stay_suffix: str | None = None
    times: int | None = None
    fired: int = 0


@dataclass
class FaultBook:
    enabled: bool
    rules: list[Rule] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def load(cls, enabled: bool, path: Path | None) -> FaultBook:
        rules: list[Rule] = []
        if enabled and path is not None:
            for item in yaml.safe_load(path.read_text(encoding="utf-8")).get("rules", []):
                if item["fault"] not in FAULTS:
                    raise ValueError(f"unknown fault {item['fault']!r} in {path}")
                rules.append(Rule(item["fault"], item.get("member_suffix"), item.get("stay_suffix"), item.get("times")))
        return cls(enabled, rules)

    def pick(self, header: str | None, member: str | None = None, stay: str | None = None) -> str | None:
        """The fault to apply to this request, or None. Header faults win over rules."""
        if not self.enabled:
            return None
        if header:
            if header not in FAULTS:
                raise ValueError(header)
            return header
        with self._lock:
            for rule in self.rules:
                if rule.times is not None and rule.fired >= rule.times:
                    continue
                if (rule.member_suffix and member and member.endswith(rule.member_suffix)) or (
                    rule.stay_suffix and stay and stay.endswith(rule.stay_suffix)
                ):
                    rule.fired += 1
                    return rule.fault
        return None
