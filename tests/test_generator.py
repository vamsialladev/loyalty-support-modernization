"""Milestone 3 done-when (Appendix C): reproducible generator, referential integrity, catalog conformance, label
independence, no split leakage, and the application can never read labels."""

import ast
import csv
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from evaluations.labeler import label_case, load_policies
from seed_data.generator.dictionary import render_dictionary
from seed_data.generator.generate import generate
from seed_data.generator.models import CaseInput, CaseLabel, DocumentTruth
from seed_data.generator.timeutil import add_months, business_date, utc_date
from tests.conftest import ROOT, read_jsonl

BENCH = "benchmarks/datasets/v1"
DEFECTS = [f"D{n:02d}" for n in range(1, 26) if n != 14]


def labels(root: Path, split: str | None = None) -> list[dict]:
    splits = [split] if split else ["dev", "validation", "heldout", "stress", "fairness"]
    return [row for s in splits for row in read_jsonl(root / BENCH / "labels" / f"{s}.jsonl")]


# ---------- reproducibility ----------


def test_committed_manifest_is_reproduced(generated: Path) -> None:
    committed = json.loads((ROOT / BENCH / "manifest.json").read_text(encoding="utf-8"))
    fresh = json.loads((generated / BENCH / "manifest.json").read_text(encoding="utf-8"))
    assert fresh["files"] == committed["files"], "regenerated files differ from the committed manifest"
    assert fresh["documents"] == committed["documents"]
    assert fresh["counts"] == committed["counts"]


def test_committed_benchmark_files_match_their_checksums() -> None:
    import hashlib

    manifest = json.loads((ROOT / BENCH / "manifest.json").read_text(encoding="utf-8"))
    for rel, digest in manifest["files"].items():
        if rel.startswith("benchmarks/"):
            assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel


def test_same_seed_same_checksums_and_different_seed_differs(tmp_path: Path) -> None:
    a = generate(7, 0.05, tmp_path / "a", documents=False)
    b = generate(7, 0.05, tmp_path / "b", documents=False)
    c = generate(8, 0.05, tmp_path / "c", documents=False)
    assert a.files == b.files
    assert a.files != c.files


# ---------- referential integrity ----------


def test_referential_integrity(generated: Path) -> None:
    op = generated / "seed_data/v1"
    members = {m["member_number"]: m for m in read_jsonl(op / "members.jsonl")}
    stays = read_jsonl(op / "stays.jsonl")
    stay_ids = {s["stay_id"] for s in stays}
    ledger = read_jsonl(op / "ledger.jsonl")
    entry_ids = {e["entry_id"] for e in ledger}
    assert len({s["record_id"] for s in stays}) == len(stays)
    assert all(s["member_number"] is None or s["member_number"] in members for s in stays)
    assert all(e["member_number"] in members for e in ledger)
    assert all(e["stay_id"] in stay_ids for e in ledger if e["stay_id"])
    assert all(e["reverses_entry_id"] in entry_ids for e in ledger if e["reverses_entry_id"])
    assert all(m["merged_into"] in members for m in members.values() if m["merged_into"])
    assert all(q["posts_entry_id"] in entry_ids for q in read_jsonl(op / "posting_queue.jsonl"))
    for case in [c for s in ("dev", "heldout", "stress") for c in read_jsonl(generated / BENCH / f"{s}.jsonl")]:
        for req in case["requests"]:
            for att in req["attachments"]:
                assert (op / att["filename"]).is_file(), att["filename"]


def test_missing_records_are_flagged_only_on_the_labels_side(generated: Path) -> None:
    stay_ids = {s["stay_id"] for s in read_jsonl(generated / "seed_data/v1/stays.jsonl")}
    missing = [lab for lab in labels(generated) if "D24" in lab["scenarios"]]
    assert missing
    for lab in missing:
        assert lab["facts"]["records"] == []
        assert lab["stays"][0]["stay_id"] not in stay_ids
        assert lab["next_action"] == "escalate"


# ---------- catalog conformance and composition ----------


def test_every_catalog_item_is_seeded(generated: Path) -> None:
    seen = Counter(s for lab in labels(generated) for s in lab["scenarios"])
    for item in [*DEFECTS, *(f"K0{n}" for n in range(1, 7)), *(f"S0{n}" for n in range(1, 6))]:
        assert seen[item] > 0, f"{item} never seeded"


def test_split_sizes_and_heldout_composition(generated: Path) -> None:
    sizes = {
        s: len(read_jsonl(generated / BENCH / f"{s}.jsonl"))
        for s in ("dev", "validation", "heldout", "stress", "fairness")
    }
    assert sizes == {"dev": 100, "validation": 30, "heldout": 80, "stress": 30, "fairness": 40}
    held = Counter(s for lab in labels(generated, "heldout") for s in lab["scenarios"])
    assert sum(held[f"K0{n}"] for n in range(1, 7)) == 20
    for d in DEFECTS:
        assert held[d] >= (3 if d in ("D24", "D25") else 2), f"held-out has {held[d]} x {d}"


def test_history_frequencies_match_the_configured_mix(generated: Path) -> None:
    cfg = yaml.safe_load((ROOT / "seed_data/generator/config/scenario_mix.yaml").read_text(encoding="utf-8"))
    cases = read_jsonl(generated / "seed_data/v1/history/cases.jsonl")
    counts = Counter(c["driver"] for c in cases)
    assert 3400 <= len(cases) <= 4300, len(cases)
    for driver, freq in cfg["driver_frequency"].items():
        observed = counts[driver] / len(cases)
        assert abs(observed - freq) <= max(0.01, freq * 0.5), f"{driver}: {observed:.3f} vs {freq}"
    assert all(c["satisfaction_proxy"] is None or 1 <= c["satisfaction_proxy"] <= 5 for c in cases)


# ---------- labels ----------


def test_labels_validate_and_inputs_match(generated: Path) -> None:
    for split in ("dev", "validation", "heldout", "stress", "fairness"):
        ins = {c["case_id"]: CaseInput.model_validate(c) for c in read_jsonl(generated / BENCH / f"{split}.jsonl")}
        labs = {lab["case_id"]: CaseLabel.model_validate(lab) for lab in labels(generated, split)}
        assert set(ins) == set(labs)
    for doc in read_jsonl(generated / BENCH / "labels/documents.jsonl"):
        DocumentTruth.model_validate(doc)


def test_labeler_recomputes_every_stored_label() -> None:
    policies = load_policies(ROOT / "policies/hg-demo")
    customer = yaml.safe_load((ROOT / "config/customers/hg-demo.yaml").read_text(encoding="utf-8"))
    for lab in labels(ROOT):
        computed = label_case(lab["facts"], policies, customer["source_code_channels"])
        for key, value in computed.items():
            assert lab[key] == value, f"{lab['case_id']}.{key}"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_labeler_is_independent_of_generator_and_app() -> None:
    assert not (_imports(ROOT / "evaluations/labeler.py") & {"seed_data", "app"})
    for path in (ROOT / "seed_data/generator").rglob("*.py"):
        assert "app" not in _imports(path), f"{path.name} imports app"


def test_app_cannot_read_labels_or_generator_metadata() -> None:
    # The app and the mock API must never read ground truth or generator metadata. The mock API may read the
    # operational folder seed_data/v1 (members, stays, ledger, queue), so "seed_data" is only forbidden in the app.
    always = ("benchmarks", "evaluations", "labels/", "ground_truth", "label-review")
    rules = {
        "app": (*always, "seed_data"),
        "mock_customer_api": always,
        "worker": (*always, "seed_data"),
        "customer_shapes": (*always, "seed_data"),
    }
    for package, forbidden in rules.items():
        for path in (ROOT / package).rglob("*.py") if (ROOT / package).exists() else []:
            source = path.read_text(encoding="utf-8")
            assert not (_imports(path) & {"evaluations", "seed_data", "benchmarks"}), path
            hits = [word for word in forbidden if word in source]
            assert hits == [], f"{path} mentions {hits}"


def test_fairness_pairs_get_the_same_outcome(generated: Path) -> None:
    pairs: dict[str, list[dict]] = {}
    for lab in labels(generated, "fairness"):
        pairs.setdefault(lab["slices"]["pair"], []).append(lab)
    assert len(pairs) == 20
    for pair_id, (a, b) in pairs.items():
        assert (a["next_action"], a["expected_outcome"], a["owed_total"]) == (
            b["next_action"],
            b["expected_outcome"],
            b["owed_total"],
        ), pair_id


# ---------- leakage ----------


def test_no_member_stay_or_text_crosses_splits(generated: Path) -> None:
    by_split: dict[str, dict[str, set[str]]] = {}
    for split in ("dev", "validation", "heldout", "stress", "fairness"):
        labs = labels(generated, split)
        ins = read_jsonl(generated / BENCH / f"{split}.jsonl")
        by_split[split] = {
            "members": {m for lab in labs for m in [lab["facts"]["claimant"], *lab["facts"]["linked_profiles"]] if m},
            "stays": {s["stay_id"] for lab in labs for s in lab["stays"]},
            "texts": {r["text"] for c in ins for r in c["requests"]},
            "groups": {lab["group_id"] for lab in labs},
        }
    names = list(by_split)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            for key in ("members", "stays", "texts", "groups"):
                assert not (by_split[a][key] & by_split[b][key]), f"{key} shared by {a} and {b}"


def test_paraphrase_families_and_temporal_split(generated: Path) -> None:
    for lab in labels(generated):
        family = lab["slices"].get("paraphrase_family")
        if family and lab["split"] in ("dev", "validation"):
            assert int(family) <= 8
        if family and lab["split"] == "heldout":
            assert int(family) >= 9
    for lab in labels(generated, "heldout"):
        received = date.fromisoformat(lab["facts"]["received_at_utc"][:10])
        if "D15" not in lab["scenarios"]:  # policy-boundary cases are anchored to July 2026 (documented exception)
            assert received >= date(2026, 9, 1), lab["case_id"]


# ---------- documents, dictionary, review sheet ----------


def test_document_ground_truth_matches_records(generated: Path) -> None:
    stays = {}
    for s in read_jsonl(generated / "seed_data/v1/stays.jsonl"):
        stays.setdefault(s["stay_id"], s)
    truths = read_jsonl(generated / BENCH / "labels/documents.jsonl")
    assert len(truths) >= 80
    for t in truths:
        record = stays.get(t["fields"]["confirmation"])
        if record is None:
            continue  # D24 folio for a stay missing from every system
        assert t["fields"]["arrival"] == record["arrival_date"]
        if "departure" not in t["disagrees_with_record"]:
            checkout = datetime.strptime(record["checkout_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            assert t["fields"]["departure"] == business_date(checkout).isoformat()
    assert Counter(t["kind"] for t in truths if t["case_id"] is None) == {
        "folio_pdf": 20,
        "receipt_image": 20,
        "ota_email": 20,
    }


def test_documents_are_deterministic(tmp_path: Path) -> None:
    import random

    from seed_data.generator.documents import write_folio_pdf, write_receipt_png
    from seed_data.generator.models import StayRecord

    stay = StayRecord.model_validate(
        read_jsonl(ROOT / BENCH / "labels/heldout.jsonl")[0]["facts"]["records"][0]
        if read_jsonl(ROOT / BENCH / "labels/heldout.jsonl")[0]["facts"]["records"]
        else read_jsonl(ROOT / BENCH / "labels/dev.jsonl")[0]["facts"]["records"][0]
    )
    fields = {
        "confirmation": stay.stay_id,
        "property": "Beach Resort",
        "arrival": stay.arrival_date,
        "departure": "2026-01-01",
        "rate": "100.00",
        "total": "112.00",
        "name": stay.guest_name,
        "member": "",
    }
    d1 = write_receipt_png(tmp_path / "a.png", stay, fields, ["blur", "speckle"], random.Random(1))
    d2 = write_receipt_png(tmp_path / "b.png", stay, fields, ["blur", "speckle"], random.Random(1))
    assert d1 == d2
    write_folio_pdf(tmp_path / "a.pdf", stay, fields, "A", None)
    write_folio_pdf(tmp_path / "b.pdf", stay, fields, "A", None)
    assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()


def test_data_dictionary_is_up_to_date() -> None:
    assert (ROOT / "docs/data-dictionary.md").read_text(encoding="utf-8") == render_dictionary()


def test_review_sheet_has_the_stratified_sample() -> None:
    with (ROOT / "evaluations/label-review/review-sheet.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 30
    template = (ROOT / "evaluations/label-review/review-sheet.template.csv").read_text(encoding="utf-8").strip()
    assert list(rows[0]) == template.split(",")
    strata = Counter(r["stratum"] for r in rows)
    assert strata == {
        "control": 6,
        "ai_may_help": 6,
        "not_fixable": 2,
        "policy_date_boundary": 5,
        "other_defect": 6,
        "safety": 5,
    }
    assert 10 <= sum(r["split"] == "heldout" for r in rows) <= 20
    assert all(r["reviewer_verdict"] == "" or r["reviewer_verdict"] in ("agree", "disagree", "unsure") for r in rows)


# ---------- unit tests ----------


def test_points_use_integer_cents() -> None:
    from seed_data.generator.world import earned_points

    record = read_jsonl(ROOT / BENCH / "labels/dev.jsonl")[0]["facts"]["records"]
    from seed_data.generator.models import StayRecord

    if record:
        stay = StayRecord.model_validate(record[0])
        assert earned_points(stay) == stay.room_revenue_cents // 10
    stay2 = StayRecord.model_validate(
        {
            **read_jsonl(ROOT / "benchmarks/datasets/v1/labels/dev.jsonl")[1]["facts"]["records"][0],
            "room_revenue_cents": 12010,
        }
    )
    assert earned_points(stay2) == 1201  # 120.10 USD: float math would give 1200


def test_business_date_and_dst() -> None:
    late = datetime(2026, 8, 11, 0, 30, tzinfo=UTC)  # 20:30 Eastern on 10 Aug
    assert business_date(late) == date(2026, 8, 10)
    assert utc_date(late) == date(2026, 8, 11)
    winter = datetime(2026, 1, 15, 2, 0, tzinfo=UTC)  # 21:00 Eastern standard time on 14 Jan
    assert business_date(winter) == date(2026, 1, 14)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def _facts(checkout_utc: str, received_utc: str, **record: object) -> dict:
    base = {
        "record_id": "R1",
        "stay_id": "BR-1000",
        "customer_id": "hg-demo",
        "property": "beach-resort",
        "member_number": "GR-10000",
        "member_on_booking": True,
        "arrival_date": "2026-08-08",
        "nights": 2,
        "checkout_at_utc": checkout_utc,
        "status": "checked_out",
        "channel": "direct",
        "source_code": "WEB",
        "rate_code": "BAR",
        "partner_confirmation": None,
        "room_revenue_cents": 40000,
        "taxes_cents": 0,
        "fees_cents": 0,
        "guest_name": "A B",
    }
    base.update(record)
    return {
        "received_at_utc": received_utc,
        "claimant": "GR-10000",
        "linked_profiles": [],
        "records": [base],
        "ledger": [],
        "queue": [],
        "claimed_stay_ids": ["BR-1000"],
        "checkout_days": {"BR-1000": "2026-08-10"},
    }


@pytest.mark.parametrize(
    ("received", "action"),
    [
        ("2026-08-24T14:00:00Z", "adjust"),  # day 14 in Eastern time: first eligible day
        ("2026-08-23T14:00:00Z", "wait_until"),  # day 13: too early
    ],
)
def test_waiting_period_boundary_in_eastern_time(received: str, action: str) -> None:
    policies = load_policies(ROOT / "policies/hg-demo")
    facts = _facts("2026-08-11T00:30:00Z", received)  # checkout 20:30 Eastern on 10 Aug (UTC date 11 Aug)
    assert label_case(facts, policies, {"WEB": "direct"})["next_action"] == action


def test_supervisor_limit_escalates() -> None:
    policies = load_policies(ROOT / "policies/hg-demo")
    facts = _facts("2026-08-11T00:30:00Z", "2026-09-30T14:00:00Z", room_revenue_cents=250_000)
    result = label_case(facts, policies, {"WEB": "direct"})
    assert (result["next_action"], result["next_action_detail"]) == ("escalate", "over_supervisor_limit")


# ---------- analysis, financial model, command line ----------


def test_committed_day_one_reports_trace_to_the_data(generated: Path, tmp_path: Path) -> None:
    from evaluations.discovery_analysis import write_all

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "executive-brief.md").write_text(
        (ROOT / "docs/executive-brief.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = write_all(root=generated, docs=docs)
    for name in ("day-one-discovery.md", "problem-statement.md", "executive-brief.md"):
        assert (docs / name).read_text(encoding="utf-8") == (ROOT / "docs" / name).read_text(encoding="utf-8"), name
    assert {p.name for p in (docs / "images/day-one").iterdir()} == {
        "pareto.png",
        "weekly-volume-sla.png",
        "backlog.png",
        "handling-time.png",
    }
    assert 0 < result["failures"] < result["n"]
    assert "SYNTHETIC" in (docs / "day-one-discovery.md").read_text(encoding="utf-8")


def test_financial_model_labels_everything_as_an_estimate() -> None:
    from evaluations.financial_model import Assumptions, break_even_volume, history_estimate, sensitivity

    cases = [
        {
            "outcome": "correct",
            "points_due": 1000,
            "points_credited": 1000,
            "handling_minutes": 12.0,
            "contacts": 1,
            "reopened": False,
        },
        {
            "outcome": "false_approval",
            "points_due": 0,
            "points_credited": 2000,
            "handling_minutes": 18.0,
            "contacts": 2,
            "reopened": False,
        },
        {
            "outcome": "false_denial",
            "points_due": 3000,
            "points_credited": 0,
            "handling_minutes": 30.0,
            "contacts": 3,
            "reopened": True,
        },
    ]
    est = history_estimate(cases, Assumptions())
    assert est["label"] == "estimate under stated assumptions"
    assert est["over_credit_points"] == 2000 and est["over_credit_leakage_usd"] == 16.0
    assert est["under_credit_points_member_harm_proxy"] == 3000
    assert est["handling_cost_usd"] == 32.0  # 60 minutes at $32/hour
    assert est["incremental_ai_cost"] == "not measured yet"
    assert len(sensitivity(cases, Assumptions())) == 6
    assert break_even_volume(100.0, 2.0) == 50.0
    assert break_even_volume(100.0, 0.0) is None


def test_cli_verify_and_clean(tmp_path: Path) -> None:
    from seed_data.generator import DEFAULT_SEED
    from seed_data.generator.cli import cmd_verify, main

    assert cmd_verify(DEFAULT_SEED, 1.0) == 0  # regenerates in a temp folder and matches the committed manifest
    target = tmp_path / "seed_data/v1"
    target.mkdir(parents=True)
    (target / "x.jsonl").write_text("{}\n", encoding="utf-8")
    keep = tmp_path / "benchmarks/datasets/v1/manifest.json"
    keep.parent.mkdir(parents=True)
    keep.write_text("{}", encoding="utf-8")
    assert main(["clean", "--root", str(tmp_path)]) == 0
    assert not target.exists() and keep.exists()  # clean removes regenerated data only
