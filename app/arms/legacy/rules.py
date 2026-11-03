"""Arm A's legacy rules configuration (`config/legacy/<customer>-legacy-rules.yaml`), loaded into typed values.

The file is the legacy system's own configuration, deliberately out of date in the pre-registered ways (ADR-0043).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "legacy"


@dataclass(frozen=True)
class RulesRevision:
    effective_from: date
    waiting_period_days: dict[str, int]
    eligible_channels: tuple[str, ...]


@dataclass(frozen=True)
class LegacyRules:
    customer_id: str
    points_per_usd_room_revenue: int
    claim_window_months: int
    supervisor_limit_points: int
    date_basis: str
    revisions: tuple[RulesRevision, ...]

    @classmethod
    def load(cls, customer_id: str, config_dir: Path = CONFIG_DIR) -> LegacyRules:
        data = yaml.safe_load((config_dir / f"{customer_id}-legacy-rules.yaml").read_text(encoding="utf-8"))
        revisions = tuple(
            sorted(
                (
                    RulesRevision(
                        date.fromisoformat(str(r["effective_from"])),
                        {str(k): int(v) for k, v in r["waiting_period_days"].items()},
                        tuple(str(c) for c in r["eligible_channels"]),
                    )
                    for r in data["revisions"]
                ),
                key=lambda r: r.effective_from,
            )
        )
        if data["date_basis"] != "utc":
            raise ValueError("the legacy engine only knows UTC dates (defect D04)")
        return cls(
            data["customer_id"],
            int(data["points_per_usd_room_revenue"]),
            int(data["claim_window_months"]),
            int(data["supervisor_limit_points"]),
            data["date_basis"],
            revisions,
        )

    def revision_on(self, day: date) -> RulesRevision:
        """The revision in force on the day the case is worked: 'current rules', whatever the stay's date (D15)."""
        current = [r for r in self.revisions if r.effective_from <= day]
        if not current:
            raise ValueError(f"no legacy rules revision in force on {day}")
        return current[-1]
