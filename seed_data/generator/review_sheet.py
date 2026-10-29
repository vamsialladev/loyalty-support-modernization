"""Fill `evaluations/label-review/review-sheet.csv` with the 30-case stratified sample (README sampling plan)."""

import csv
import json
from pathlib import Path
from typing import Any

from seed_data.generator.rng import rng

SAMPLE_SEED_PART = "label-review"
COLUMNS = [
    "case_id",
    "split",
    "stratum",
    "property",
    "request_text",
    "attachment_summary",
    "member_facts",
    "stay_facts",
    "ledger_facts",
    "policy_version_applied",
    "label_eligibility",
    "label_expected_points",
    "label_existing_credit",
    "label_required_evidence",
    "label_next_action",
    "label_clarification_needed",
    "label_escalation_needed",
    "label_rationale",
    "reviewer_verdict",
    "reviewer_corrected_fields",
    "reviewer_note",
]
STRATA: list[tuple[str, list[str], int | None]] = [
    ("control", ["K01", "K02", "K03", "K04", "K05", "K06"], None),
    ("ai_may_help", ["D16", "D18", "D19", "D20", "D22", "D23"], None),
    ("not_fixable", ["D24", "D25"], None),
    ("policy_date_boundary", ["D04", "D06", "D08", "D09", "D15"], None),
    ("other_defect", ["D01", "D02", "D03", "D05", "D07", "D10", "D12", "D13", "D17", "D21"], 6),
    ("safety", ["S01", "S02", "S03", "S04", "S05"], None),
]
SPLIT_PREFERENCE = ["heldout", "dev", "stress", "validation"]


def _load(bench: Path, kind: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for split in SPLIT_PREFERENCE:
        path = bench / (f"labels/{split}.jsonl" if kind == "labels" else f"{split}.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows[row["case_id"]] = row
    return rows


def choose(labels: dict[str, dict[str, Any]], seed: int) -> list[tuple[str, str]]:
    """(stratum, case_id) pairs: one case per scenario, alternating held-out and dev to get about 15 held-out."""
    r = rng(seed, SAMPLE_SEED_PART)
    picks: list[tuple[str, str]] = []
    turn = 0
    for stratum, scenarios, take in STRATA:
        chosen = sorted(scenarios)
        if take is not None:
            chosen = sorted(r.sample(chosen, take))
        for scenario in chosen:
            preferred = ["heldout", "dev"] if turn % 2 == 0 else ["dev", "heldout"]
            order = preferred + [s for s in SPLIT_PREFERENCE if s not in preferred]
            for split in order:
                matches = sorted(
                    cid for cid, lab in labels.items() if lab["split"] == split and lab["scenarios"] == [scenario]
                )
                if matches:
                    picks.append((stratum, r.choice(matches)))
                    turn += 1
                    break
            else:
                raise ValueError(f"no single-scenario case for {scenario}")
    return picks


def summarise(lab: dict[str, Any], case: dict[str, Any]) -> dict[str, str]:
    facts = lab["facts"]
    req = case["requests"][0]
    text = "\n---\n".join(r["text"] for r in case["requests"])
    stays = (
        "; ".join(
            f"{s['stay_id']} {s['property']} arr {s['arrival_date']} out {s['checkout_at_utc']} {s['status']} "
            f"ch={s['channel']} src={s['source_code']} rate={s['rate_code']} member={s['member_number']} "
            f"on_booking={s['member_on_booking']} revenue=${s['room_revenue_cents'] / 100:.2f}"
            for s in facts["records"]
        )
        or "NO STAY RECORD IN ANY SYSTEM"
    )
    ledger = (
        "; ".join(
            f"{e['kind']} {e['points']} pts to {e['member_number']} at {e['posted_at_utc']}" for e in facts["ledger"]
        )
        or "no ledger entries"
    )
    queue = "; ".join(f"queued {q['points']} pts, expected {q['expected_post_at_utc']}" for q in facts["queue"])
    members = (
        f"claimant {facts['claimant']}; linked {facts['linked_profiles'] or 'none'}; "
        f"form member {req['form_member_number']}; form conf {req['form_confirmation']}; "
        f"sender {req['sender_email']}"
    )
    policies = (
        "; ".join(f"{s['stay_id']}: {s['policy_id']} v{s['policy_version']}" for s in lab["stays"] if s["policy_id"])
        or "none (escalation before policy)"
    )
    return {
        "property": req["form_property"] or (facts["records"][0]["property"] if facts["records"] else ""),
        "request_text": text,
        "attachment_summary": ", ".join(a["kind"] for a in req["attachments"]) or "none",
        "member_facts": members,
        "stay_facts": stays,
        "ledger_facts": ledger + (f" | queue: {queue}" if queue else ""),
        "policy_version_applied": policies,
        "label_eligibility": lab["eligibility"],
        "label_expected_points": "; ".join(f"{s['stay_id']}={s['expected_final_points']}" for s in lab["stays"]),
        "label_existing_credit": "; ".join(f"{s['stay_id']}={s['existing_credit']}" for s in lab["stays"]),
        "label_required_evidence": ", ".join(lab["required_evidence"]),
        "label_next_action": lab["next_action"]
        + (f":{lab['next_action_detail']}" if lab["next_action_detail"] else ""),
        "label_clarification_needed": "yes" if lab["clarification_needed"] else "no",
        "label_escalation_needed": "yes" if lab["escalation_needed"] else "no",
        "label_rationale": lab["rationale"],
    }


def write_sheet(bench: Path, out_csv: Path, seed: int) -> list[tuple[str, str]]:
    labels, cases = _load(bench, "labels"), _load(bench, "cases")
    picks = choose(labels, seed)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\r\n")
        writer.writeheader()
        for stratum, case_id in picks:
            row = {
                "case_id": case_id,
                "split": labels[case_id]["split"],
                "stratum": stratum,
                **summarise(labels[case_id], cases[case_id]),
                "reviewer_verdict": "",
                "reviewer_corrected_fields": "",
                "reviewer_note": "",
            }
            writer.writerow(row)
    return picks
