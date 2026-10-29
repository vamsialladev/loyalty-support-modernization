"""Reference labeler: computes ground truth from planted facts and the written policy (spec E.1, ADR-0029).

Independence rules:
- Reads only plain facts (dicts) and the policy files' front matter. Imports nothing from `seed_data.generator`
  and nothing from `app`, so the generator's intent and the app's future rules engine are both checked against
  separate code.
- Never calls a model.

Vocabulary of actions: adjust, no_adjustment_credited, no_adjustment_pending, wait_until, not_checked_out, deny,
request_info, escalate, plus `not_claimed` for stays a request did not claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

Facts = dict[str, Any]


@dataclass(frozen=True)
class Policy:
    policy_id: str
    version: int
    effective_from: date
    effective_to: date | None
    status: str
    rules: dict[str, Any]


def load_policies(directory: Path) -> list[Policy]:
    policies = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---", 2)[1])
        end = front.get("effective_to")
        policies.append(
            Policy(
                front["policy_id"],
                int(front["version"]),
                _as_date(front["effective_from"]),
                _as_date(end) if end else None,
                front["status"],
                front.get("rules", {}),
            )
        )
    return policies


def _as_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def policy_in_force(policies: list[Policy], policy_id: str, day: date) -> Policy:
    matches = [
        p
        for p in policies
        if p.policy_id == policy_id
        and p.effective_from <= day
        and (p.effective_to is None or day <= p.effective_to)
        and p.status != "draft"
    ]
    if len(matches) != 1:
        raise ValueError(f"{len(matches)} versions of {policy_id} in force on {day}")
    return matches[0]


def _ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _local(ts: datetime, tz: str) -> date:
    return ts.astimezone(ZoneInfo(tz)).date()


def _add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    for d in (day.day, 30, 29, 28):
        try:
            return date(year, month, min(day.day, d))
        except ValueError:
            continue
    raise ValueError(day)


@dataclass
class StayResult:
    stay_id: str
    policy_id: str | None
    policy_version: int | None
    eligibility: str
    action: str
    detail: str | None
    existing_credit: str
    earned: int
    owed: int
    final: int
    evidence: list[str]
    needs_info: str | None = None


def _conflicting(records: list[dict[str, Any]]) -> bool:
    keys = ("checkout_at_utc", "room_revenue_cents", "arrival_date", "member_number", "channel")
    return len({tuple(r[k] for k in keys) for r in records}) > 1


def evaluate_stay(
    stay_id: str, facts: Facts, policies: list[Policy], source_channels: dict[str, str | None]
) -> StayResult:
    received = _ts(facts["received_at_utc"])
    records = [rec for rec in facts["records"] if rec["stay_id"] == stay_id]
    profiles = {p for p in [facts.get("claimant"), *facts.get("linked_profiles", [])] if p}
    entries = [e for e in facts["ledger"] if e["stay_id"] == stay_id]
    queue = [q for q in facts["queue"] if q["stay_id"] == stay_id]
    final_entries = sum(e["points"] for e in entries)

    if not records:
        return StayResult(
            stay_id,
            None,
            None,
            "needs_escalation",
            "escalate",
            "missing_stay_record",
            "unknown",
            0,
            0,
            final_entries,
            ["member_record", "stay_record"],
        )
    if _conflicting(records):
        return StayResult(
            stay_id,
            None,
            None,
            "needs_escalation",
            "escalate",
            "conflicting_records",
            "unknown",
            0,
            0,
            final_entries,
            ["member_record", "all_stay_records"],
        )

    rec = records[0]
    tz = "America/New_York"
    checkout_day = _local(_ts(rec["checkout_at_utc"]), tz)
    mpr = policy_in_force(policies, "missing-points-requests", checkout_day)
    earn = policy_in_force(policies, "guest-rewards-earning", checkout_day)
    tz = mpr.rules.get("business_date_timezone", tz)
    claim_day = _local(received, tz)
    earned = rec["room_revenue_cents"] * int(earn.rules["points_per_usd_room_revenue"]) // 100
    evidence = ["member_record", "stay_record", "ledger", f"policy:{mpr.policy_id}@v{mpr.version}"]
    ref = (mpr.policy_id, mpr.version)

    def result(
        eligibility: str,
        action: str,
        detail: str | None,
        credit: str,
        owed: int,
        final: int,
        extra: list[str] | None = None,
        needs_info: str | None = None,
    ) -> StayResult:
        return StayResult(
            stay_id,
            ref[0],
            ref[1],
            eligibility,
            action,
            detail,
            credit,
            earned if eligibility != "ineligible" else 0,
            owed,
            final,
            evidence + (extra or []),
            needs_info,
        )

    if rec["status"] != "checked_out":
        return result("ineligible", "not_checked_out", None, "none", 0, final_entries)
    if rec["member_number"] is None and not facts.get("claimant"):
        return result("ineligible", "deny", "not_a_member", "none", 0, final_entries)
    if claim_day > _add_months(checkout_day, int(mpr.rules["claim_window_months"])):
        return result("ineligible", "deny", "claim_window", "none", 0, final_entries)

    needs_info = None
    channel = rec["channel"] or source_channels.get(rec["source_code"])
    if channel is None:
        needs_info = "booking_channel"
        channel = facts.get("reply_channel")
        if channel is None:
            raise ValueError(f"{stay_id}: channel underivable and no member reply planted")
    eligible_channel = (
        channel in mpr.rules["eligible_channels"]
        or (channel == "ota" and mpr.rules["ota_eligible_with_member_on_booking"] and rec["member_on_booking"])
        or (
            channel == "travel_agent"
            and mpr.rules["corporate_rate_prefix"]
            and str(rec["rate_code"]).startswith(mpr.rules["corporate_rate_prefix"])
        )
    )
    if not eligible_channel:
        return result("ineligible", "deny", "channel_ineligible", "none", 0, final_entries, needs_info=needs_info)

    other_profiles = set(facts.get("duplicate_profiles", []))
    on_other = sum(
        e["points"] for e in entries if e["member_number"] in other_profiles and _ts(e["posted_at_utc"]) <= received
    )
    if other_profiles and on_other >= earned:
        return result(
            "eligible",
            "no_adjustment_credited",
            "credited_other_profile",
            "credited_other_profile",
            0,
            final_entries,
            ["linked_profile"],
            needs_info,
        )
    posted = sum(e["points"] for e in entries if e["member_number"] in profiles and _ts(e["posted_at_utc"]) <= received)
    if posted >= earned:
        return result("eligible", "no_adjustment_credited", None, "credited", 0, final_entries, None, needs_info)

    wait = int(mpr.rules["waiting_period_days"])
    if claim_day < checkout_day + timedelta(days=wait):
        owed = max(0, earned - final_entries)
        return result(
            "ineligible",
            "wait_until",
            (checkout_day + timedelta(days=wait)).isoformat(),
            "none",
            owed,
            final_entries + owed,
            None,
            needs_info,
        )

    pending = [q for q in queue if _ts(q["queued_at_utc"]) <= received < _ts(q["expected_post_at_utc"])]
    if pending:
        if not mpr.rules["pending_posting_blocks_adjustment"]:
            raise ValueError(f"{stay_id}: pending posting under a policy without a pending rule (not in the catalog)")
        expected = _local(_ts(pending[0]["expected_post_at_utc"]), tz).isoformat()
        return result(
            "eligible",
            "no_adjustment_pending",
            expected,
            "pending_posting",
            0,
            final_entries,
            ["posting_queue"],
            needs_info,
        )

    late = [e for e in entries if _ts(e["posted_at_utc"]) > received]
    harness = set(facts.get("harness_late_postings", []))
    if late and all(e["entry_id"] in harness for e in late):
        # Investigation says adjust; the posting lands after approval; the re-check before execution must stop it.
        return result("eligible", "adjust", None, "none", 0, final_entries, None, needs_info)
    if late:
        raise ValueError(f"{stay_id}: a later posting with no queue item and no harness event (generator bug)")
    owed = earned - posted
    extra = ["merge_map"] if facts.get("merged_profiles") else []
    return result("eligible", "adjust", None, "none", owed, final_entries + owed, extra, needs_info)


PRIORITY = [
    "escalate",
    "request_info",
    "deny",
    "adjust",
    "wait_until",
    "no_adjustment_pending",
    "no_adjustment_credited",
    "not_checked_out",
]


def label_case(facts: Facts, policies: list[Policy], source_channels: dict[str, str | None]) -> dict[str, Any]:
    """Case-level label. Returns the fields of CaseLabel that depend on facts and policy."""
    claimed = [evaluate_stay(s, facts, policies, source_channels) for s in facts["claimed_stay_ids"]]
    unclaimed = []
    for stay_id in facts.get("unclaimed_stay_ids", []):
        total = sum(e["points"] for e in facts["ledger"] if e["stay_id"] == stay_id)
        unclaimed.append(StayResult(stay_id, None, None, "eligible", "not_claimed", None, "none", 0, 0, total, []))

    actions = {r.action for r in claimed}
    detail: str | None
    if "escalate" in actions:
        first = next(r for r in claimed if r.action == "escalate")
        action, detail = "escalate", first.detail
    elif len(facts.get("candidate_stays", [])) > 1:
        action, detail = "request_info", "which_stay"
    elif any(r.needs_info for r in claimed):
        action, detail = "request_info", next(r.needs_info for r in claimed if r.needs_info)
    else:
        top = min(claimed, key=lambda r: PRIORITY.index(r.action))
        action, detail = top.action, top.detail
    owed_total = sum(r.owed for r in claimed)

    limit = None
    for r in claimed:
        if r.policy_id:
            checkout = facts["checkout_days"][r.stay_id]
            limit = policy_in_force(policies, "missing-points-requests", date.fromisoformat(checkout)).rules.get(
                "supervisor_limit_points"
            )
    if limit is not None and owed_total > int(limit) and action == "adjust":
        action, detail = "escalate", "over_supervisor_limit"

    if action == "escalate":
        outcome = "escalated"
    elif owed_total > 0:
        outcome = "adjusted"
    elif any(r.action == "deny" for r in claimed):
        outcome = "denied"
    else:
        outcome = "no_adjustment"

    eligibility = {"escalate": "needs_escalation", "request_info": "insufficient_evidence"}.get(action)
    if eligibility is None:
        eligibility = "ineligible" if action in ("deny", "wait_until", "not_checked_out") else "eligible"

    evidence = sorted({e for r in claimed for e in r.evidence} | set(facts.get("extra_evidence", [])))
    stays = [
        {
            "stay_id": r.stay_id,
            "policy_id": r.policy_id,
            "policy_version": r.policy_version,
            "eligibility": r.eligibility,
            "stay_action": r.action,
            "existing_credit": r.existing_credit,
            "earned_points": r.earned,
            "owed_by_adjustment": r.owed,
            "expected_final_points": r.final,
        }
        for r in claimed + unclaimed
    ]
    return {
        "eligibility": eligibility,
        "next_action": action,
        "next_action_detail": detail,
        "expected_outcome": outcome,
        "clarification_needed": action == "request_info",
        "escalation_needed": action == "escalate",
        "owed_total": owed_total,
        "stays": stays,
        "required_evidence": evidence,
    }
