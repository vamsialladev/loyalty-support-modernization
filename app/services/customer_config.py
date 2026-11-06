"""Load the parts of a customer's configuration the rules and the write path read (`config/customers/<id>.yaml`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.domain.eligibility import CustomerRules

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "customers"


@dataclass(frozen=True)
class CustomerConfig:
    customer_id: str
    policy_set: str
    rules: CustomerRules
    approval_ttl_hours: int
    oidc_group_roles: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, customer_id: str, config_dir: Path = CONFIG_DIR) -> CustomerConfig:
        data = yaml.safe_load((config_dir / f"{customer_id}.yaml").read_text(encoding="utf-8"))
        rules = CustomerRules(
            {name: prop["timezone"] for name, prop in data["properties"].items()},
            dict(data["source_code_channels"]),
            int(data["max_evidence_age_minutes"]),
        )
        groups = dict((data.get("oidc") or {}).get("group_roles") or {})
        return cls(data["customer_id"], data["policy_set"], rules, int(data["approval_ttl_hours"]), groups)


@lru_cache(maxsize=8)
def customer_config(customer_id: str) -> CustomerConfig:
    return CustomerConfig.load(customer_id)
