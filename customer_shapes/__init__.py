"""Map records between the canonical model and a customer's upstream shape (`config/customers/<id>.yaml`, ADR-0033).

Used in both directions: the mock customer API renders canonical rows in the customer's shape; the app's adapter maps
the customer's responses back to canonical records. Pure functions, no I/O beyond loading the config file.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "customers"


class ShapeError(ValueError):
    """An upstream record could not be mapped: a missing field, an unknown code or a bad value."""

    def __init__(self, entity: str, problems: list[str]) -> None:
        super().__init__(f"{entity}: " + "; ".join(problems))
        self.entity = entity
        self.problems = problems


@dataclass(frozen=True)
class CustomerShape:
    customer_id: str
    fields: dict[str, dict[str, str]]  # entity -> canonical -> upstream
    value_maps: dict[str, dict[str, str]]  # upstream field -> upstream code -> canonical value
    conversions: dict[str, str]  # upstream field -> conversion name

    @classmethod
    def load(cls, customer_id: str, config_dir: Path = CONFIG_DIR) -> CustomerShape:
        data = yaml.safe_load((config_dir / f"{customer_id}.yaml").read_text(encoding="utf-8"))
        return cls(data["customer_id"], data["field_mapping"], data.get("value_maps", {}), data.get("conversions", {}))

    def upstream_names(self, entity: str) -> dict[str, str]:
        return dict(self.fields[entity])

    def to_upstream(self, entity: str, record: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for canonical, upstream in self.fields[entity].items():
            if canonical not in record:
                continue
            value = record[canonical]
            if value is not None and upstream in self.value_maps:
                reverse = {v: k for k, v in self.value_maps[upstream].items()}
                value = reverse.get(value, value)
            if value is not None and self.conversions.get(upstream) == "usd_to_cents":
                value = f"{Decimal(int(value)) / 100:.2f}"
            out[upstream] = value
        return out

    def to_canonical(self, entity: str, record: dict[str, Any], required: tuple[str, ...]) -> dict[str, Any]:
        """Canonical dict from an upstream record. Unknown upstream fields are ignored; missing required fields,
        unknown enum codes and bad money values raise ShapeError."""
        problems: list[str] = []
        out: dict[str, Any] = {}
        for canonical, upstream in self.fields[entity].items():
            if upstream not in record:
                if canonical in required:
                    problems.append(f"missing field {upstream!r}")
                continue
            value = record[upstream]
            if value is not None and upstream in self.value_maps:
                if value not in self.value_maps[upstream]:
                    problems.append(f"unknown {upstream} code {value!r}")
                    continue
                value = self.value_maps[upstream][value]
            if value is not None and self.conversions.get(upstream) == "usd_to_cents":
                try:
                    value = int((Decimal(str(value)) * 100).to_integral_value(ROUND_HALF_UP))
                except InvalidOperation:
                    problems.append(f"{upstream} is not a dollar amount")
                    continue
            out[canonical] = value
        if problems:
            raise ShapeError(entity, problems)
        return out
