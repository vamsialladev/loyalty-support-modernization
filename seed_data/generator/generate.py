"""Build the whole dataset: world, benchmark cases with labels, fairness set, documents, history, manifest.

Operational data goes to `seed_data/v1/` (git-ignored, regenerated). Benchmark inputs, labels and the manifest go to
`benchmarks/datasets/v1/` (committed, ADR-0030). The label-review sheet goes to `evaluations/label-review/`.
"""

import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from evaluations.labeler import label_case, load_policies
from seed_data.generator import DATASET_VERSION, GENERATOR_VERSION
from seed_data.generator.documents import render
from seed_data.generator.fairness import build_pairs
from seed_data.generator.history import build_history
from seed_data.generator.models import AttachmentRef, CaseInput, CaseLabel, DocumentTruth
from seed_data.generator.rng import rng
from seed_data.generator.scenarios import SCENARIOS, Ctx, Draft, render_requests
from seed_data.generator.timeutil import business_date
from seed_data.generator.world import World, build_background, checkout_dt

SRC_ROOT = Path(__file__).resolve().parents[2]

# Catalog §10 composition (pre-registered). Keys are SCENARIOS entries; D04b/D19b/D22n are variants of D04/D19/D22.
QUOTAS: dict[str, dict[str, int]] = {
    "dev": {
        "K01": 14,
        "K02": 8,
        "K03": 6,
        "K04": 6,
        "K05": 3,
        "K06": 3,
        "D01": 2,
        "D02": 2,
        "D03": 2,
        "D04": 1,
        "D04b": 1,
        "D05": 2,
        "D06": 3,
        "D07": 2,
        "D08": 2,
        "D09": 2,
        "D10": 2,
        "D11": 2,
        "D12": 3,
        "D13": 2,
        "D15": 2,
        "D16": 3,
        "D17": 2,
        "D18": 3,
        "D19": 2,
        "D19b": 1,
        "D20": 3,
        "D21": 2,
        "D22": 2,
        "D22n": 1,
        "D23": 3,
        "D24": 2,
        "D25": 2,
        "B01": 2,
        "B02": 2,
    },
    "validation": {
        "K01": 4,
        "K02": 2,
        "K03": 1,
        "K04": 1,
        "K05": 1,
        "K06": 1,
        "D01": 1,
        "D03": 1,
        "D04": 1,
        "D05": 1,
        "D06": 1,
        "D08": 1,
        "D09": 1,
        "D10": 1,
        "D12": 1,
        "D13": 1,
        "D15": 1,
        "D16": 1,
        "D17": 1,
        "D18": 1,
        "D19": 1,
        "D20": 1,
        "D22n": 1,
        "D23": 1,
        "D24": 1,
        "D25": 1,
    },
    "heldout": {
        "K01": 6,
        "K02": 4,
        "K03": 3,
        "K04": 3,
        "K05": 2,
        "K06": 2,
        "D01": 2,
        "D02": 2,
        "D03": 3,
        "D04": 2,
        "D05": 2,
        "D06": 3,
        "D07": 2,
        "D08": 2,
        "D09": 2,
        "D10": 2,
        "D11": 2,
        "D12": 3,
        "D13": 3,
        "D15": 2,
        "D16": 3,
        "D17": 3,
        "D18": 2,
        "D19": 2,
        "D19b": 1,
        "D20": 3,
        "D21": 2,
        "D22": 1,
        "D22n": 2,
        "D23": 3,
        "D24": 3,
        "D25": 3,
    },
    "stress": {
        "S01": 4,
        "S02": 4,
        "S03": 4,
        "S04": 4,
        "S05": 4,
        "C1": 2,
        "C2": 2,
        "C3": 2,
        "C4": 2,
        "B01": 1,
        "B02": 1,
    },
}
PREFIX = {"dev": "DV", "validation": "VA", "heldout": "HO", "stress": "ST", "fairness": "FA"}
SPLITS = ["dev", "validation", "heldout", "stress", "fairness"]


@dataclass
class Output:
    files: dict[str, str] = field(default_factory=dict)
    documents: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)


def write_jsonl(path: Path, rows: Sequence[BaseModel] | Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            data = row.model_dump(mode="json") if isinstance(row, BaseModel) else row
            fh.write(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(src: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    customer = yaml.safe_load((src / "config/customers/hg-demo.yaml").read_text(encoding="utf-8"))
    mix = yaml.safe_load((src / "seed_data/generator/config/scenario_mix.yaml").read_text(encoding="utf-8"))
    return customer, mix


def build_cases(world: World, seed: int) -> list[Draft]:
    drafts: list[Draft] = []
    for split, quota in QUOTAS.items():
        keys = [k for k, n in quota.items() for _ in range(n)]
        rng(seed, "order", split).shuffle(keys)  # case IDs must not reveal the scenario
        seen: Counter[str] = Counter()
        for i, key in enumerate(keys, start=1):
            seen[key] += 1
            ctx = Ctx(world, seed, split, f"{PREFIX[split]}-{i:03d}")
            if key == "D03":  # first D03 in each split: channel underivable (member must be asked); others derivable
                ctx.variant = 1 if seen[key] == 1 else 2
            drafts.append(SCENARIOS[key](ctx))
    drafts.extend(build_pairs(world, seed))
    return drafts


def facts_for(world: World, d: Draft, index: dict[str, Any]) -> dict[str, Any]:
    ids = d.claimed_stay_ids + d.unclaimed_stay_ids
    records = [s for sid in ids for s in index["stays"].get(sid, [])]
    linked = [index["members"][m] for m in d.linked_profiles]
    checkout_days: dict[str, str] = {}
    for rec in records:
        checkout_days.setdefault(rec.stay_id, business_date(checkout_dt(rec)).isoformat())
    extra = []
    if d.attachments:
        extra.append("attachment")
    if any((r.form_confirmation or "").startswith("TRV-") for r in d.requests):
        extra.append("partner_confirmation")
    if d.second_request:
        extra.append("other_open_case_for_same_stay")
    return {
        "received_at_utc": d.requests[0].received_at_utc,
        "claimant": d.claimant.member_number if d.claimant else None,
        "linked_profiles": d.linked_profiles,
        "duplicate_profiles": [m.member_number for m in linked if m.status == "active"],
        "merged_profiles": [m.member_number for m in linked if m.status == "merged"],
        "claimed_stay_ids": d.claimed_stay_ids,
        "unclaimed_stay_ids": d.unclaimed_stay_ids,
        "candidate_stays": d.candidate_stays,
        "records": [rec.model_dump(mode="json") for rec in records],
        "ledger": [e.model_dump(mode="json") for sid in ids for e in index["ledger"].get(sid, [])],
        "queue": [q.model_dump(mode="json") for sid in ids for q in index["queue"].get(sid, [])],
        "reply_channel": d.reply_channel,
        "harness_late_postings": [e.entry_id for e in d.later_postings],
        "checkout_days": checkout_days,
        "extra_evidence": extra,
        "other_member_referenced": d.other_member,
    }


def make_label(d: Draft, facts: dict[str, Any], policies: Any, sources: dict[str, str | None]) -> CaseLabel:
    computed = label_case(facts, policies, sources)
    got = (computed["next_action"], computed["expected_outcome"], computed["owed_total"])
    want = (d.intent.next_action, d.intent.outcome, d.intent.owed)
    if got != want:
        raise ValueError(f"{d.case_id} {d.scenarios}: labeler {got} != builder intent {want}")
    claimant = d.claimant
    stay = d.stays[0]
    slices = {
        "tier": claimant.tier if claimant else "none",
        "region": claimant.home_region if claimant else "unknown",
        "channel": stay.channel or "unknown",
        "language": d.language,
        "style": d.style,
    }
    if d.pair_id:
        slices["pair"] = d.pair_id
    if d.family:
        slices["paraphrase_family"] = str(d.family)
    parts = [
        f"{s['stay_id']}: {s['stay_action']}"
        + (f" ({s['policy_id']} v{s['policy_version']})" if s["policy_id"] else "")
        + f", owed {s['owed_by_adjustment']}"
        for s in computed["stays"]
    ]
    rationale = f"{' + '.join(d.scenarios)} -> {computed['next_action']}"
    if computed["next_action_detail"]:
        rationale += f" [{computed['next_action_detail']}]"
    rationale += f"; final outcome {computed['expected_outcome']}. " + "; ".join(parts) + "."
    return CaseLabel(
        case_id=d.case_id,
        split=d.split,
        scenarios=d.scenarios,
        claimant_member_number=claimant.member_number if claimant else None,
        out_of_scope_items=d.out_of_scope,
        member_reply=d.reply,
        harness_events=d.harness_events,
        slices=slices,
        group_id=d.pair_id or d.case_id,
        rationale=rationale,
        facts=facts,
        **computed,
    )


def generate(seed: int, scale: float, out_root: Path, src_root: Path = SRC_ROOT, documents: bool = True) -> Output:
    customer, mix = load_config(src_root)
    policies = load_policies(src_root / customer["policy_set"])
    sources = customer["source_code_channels"]
    world = World(seed, stay_digits=4 if scale <= 1.5 else 5)
    build_background(world, scale)
    drafts = build_cases(world, seed)
    for d in drafts:
        ctx = Ctx(world, seed, d.split, d.case_id)
        if d.pair_id:
            ctx.rng_override = rng(seed, "fairness-render", d.pair_id)
        d.requests = render_requests(ctx, d)

    index: dict[str, dict[str, list[Any]] | dict[str, Any]] = {"stays": {}, "ledger": {}, "queue": {}, "members": {}}
    for s in world.stays:
        index["stays"].setdefault(s.stay_id, []).append(s)
    for e in world.ledger:
        if e.stay_id:
            index["ledger"].setdefault(e.stay_id, []).append(e)
    for q in world.queue:
        index["queue"].setdefault(q.stay_id, []).append(q)
    index["members"] = {m.member_number: m for m in world.members}

    labels = [make_label(d, facts_for(world, d, index), policies, sources) for d in drafts]
    inputs = [
        CaseInput(case_id=d.case_id, split=d.split, customer_id="hg-demo", requests=d.requests)  # type: ignore[arg-type]
        for d in drafts
    ]

    op = out_root / "seed_data" / DATASET_VERSION
    bench = out_root / "benchmarks" / "datasets" / DATASET_VERSION
    for directory in (op, bench):
        if directory.exists():
            shutil.rmtree(directory)
    out = Output()

    truths = _documents(world, drafts, seed, op, documents)
    write_jsonl(op / "members.jsonl", world.members)
    write_jsonl(op / "stays.jsonl", world.stays)
    write_jsonl(op / "ledger.jsonl", world.ledger)
    write_jsonl(op / "posting_queue.jsonl", world.queue)
    cases, events, adjustments = build_history(seed, mix, scale)
    write_jsonl(op / "history" / "cases.jsonl", cases)
    write_jsonl(op / "history" / "events.jsonl", events)
    write_jsonl(op / "history" / "adjustments.jsonl", adjustments)

    for split in SPLITS:
        write_jsonl(bench / f"{split}.jsonl", [c for c in inputs if c.split == split])
        write_jsonl(bench / "labels" / f"{split}.jsonl", [lab for lab in labels if lab.split == split])
    write_jsonl(bench / "labels" / "documents.jsonl", truths)
    write_jsonl(
        bench / "document_set.jsonl",
        [
            AttachmentRef(
                attachment_id=t.attachment_id,
                kind=t.kind,  # type: ignore[arg-type]
                filename=f"attachments/{t.attachment_id}.{_ext(t.kind)}",
            )
            for t in truths
            if t.case_id is None
        ],
    )
    (bench / "composition.md").write_text(composition_report(labels, cases), encoding="utf-8", newline="\n")

    for path in sorted([*op.rglob("*.jsonl"), *bench.rglob("*.jsonl"), bench / "composition.md"]):
        out.files[path.relative_to(out_root).as_posix()] = sha256(path)
    out.documents = {t.attachment_id: t.content_digest for t in truths}
    out.counts = {
        "members": len(world.members),
        "stay_records": len(world.stays),
        "ledger_entries": len(world.ledger),
        "posting_queue_items": len(world.queue),
        "history_cases": len(cases),
        "history_events": len(events),
        "history_adjustments": len(adjustments),
        "documents": len(truths),
        **{f"cases_{s}": sum(1 for c in inputs if c.split == s) for s in SPLITS},
    }
    manifest = {
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "scale": scale,
        "synthetic": True,
        "policies": sorted(f"{p.policy_id}@v{p.version}" for p in policies),
        "counts": out.counts,
        "files": out.files,
        "documents": out.documents if documents else {},
    }
    (bench / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return out


def _ext(kind: str) -> str:
    return {"folio_pdf": "pdf", "receipt_image": "png", "ota_email": "eml"}[kind]


def _documents(world: World, drafts: list[Draft], seed: int, op: Path, enabled: bool) -> list[DocumentTruth]:
    attach_dir = op / "attachments"
    attach_dir.mkdir(parents=True, exist_ok=True)
    truths: list[DocumentTruth] = []
    for d in drafts:
        for n, spec in enumerate(d.attachments, start=1):
            att_id = f"ATT-{d.case_id}-{n}"
            truths.append(_one(att_id, d.case_id, spec, attach_dir, seed, enabled))
    # Extraction-only set from background stays (Appendix H3): 20 folios, 20 noisy receipts, 20 OTA emails.
    r = rng(seed, "document-set")
    pool = [s for s in world.stays if s.status == "checked_out" and s.member_number]
    ota_pool = [s for s in pool if s.partner_confirmation]
    for i in range(60):
        kind = ["folio_pdf", "receipt_image", "ota_email"][i // 20]
        stay = r.choice(ota_pool if kind == "ota_email" else pool)
        noise = (
            sorted(r.sample(["blur", "rotation", "crop", "low_contrast", "speckle"], k=r.randrange(1, 4)))
            if kind == "receipt_image"
            else []
        )
        spec = {
            "kind": kind,
            "layout": r.choice("ABC")
            if kind == "folio_pdf"
            else ("receipt" if kind == "receipt_image" else "standard"),
            "noise": noise,
            "stay": stay,
            "disagree": ["departure"] if r.random() < 0.15 else [],
            "injection": r.random() < 0.1,
        }
        truths.append(_one(f"DOC-{i + 1:03d}", None, spec, attach_dir, seed, enabled))
    return truths


def _one(
    att_id: str, case_id: str | None, spec: dict[str, Any], attach_dir: Path, seed: int, enabled: bool
) -> DocumentTruth:
    kind = str(spec["kind"])
    path = attach_dir / f"{att_id}.{_ext(kind)}"
    if enabled:
        fields, content = render(
            path,
            kind,
            spec["stay"],
            str(spec["layout"]),
            list(spec["noise"]),
            list(spec["disagree"]),
            bool(spec["injection"]),
            rng(seed, "doc", att_id),
        )
    else:
        from seed_data.generator.documents import document_fields

        fields, content = document_fields(spec["stay"], list(spec["disagree"])), "not-rendered"
    return DocumentTruth(
        attachment_id=att_id,
        kind=kind,
        layout=str(spec["layout"]),
        noise=list(spec["noise"]),
        case_id=case_id,
        fields=fields,
        disagrees_with_record=list(spec["disagree"]),
        contains_injection=bool(spec["injection"]),
        content_digest=content,
    )


def composition_report(labels: list[CaseLabel], history: list[Any]) -> str:
    """Per-split counts per scenario, and how held-out over-represents defects versus the history."""
    lines = [
        "# Benchmark composition (dataset v1)",
        "",
        "> Generated by `python -m seed_data.generator generate`. SYNTHETIC. Pre-registered composition:",
        "> `docs/legacy-defect-catalog.md` §10. The fairness set is separate (ADR-0031).",
        "",
        "## Cases per split and scenario",
        "",
        "| Scenario | " + " | ".join(SPLITS) + " |",
        "|---|" + "---|" * len(SPLITS),
    ]
    keys = sorted({s for lab in labels for s in lab.scenarios})
    for key in keys:
        row = [str(sum(1 for lab in labels if lab.split == sp and key in lab.scenarios)) for sp in SPLITS]
        lines.append(f"| {key} | " + " | ".join(row) + " |")
    totals = [str(sum(1 for lab in labels if lab.split == sp)) for sp in SPLITS]
    lines += ["| **cases** | " + " | ".join(totals) + " |", ""]
    held = [lab for lab in labels if lab.split == "heldout"]
    hist_total = len(history)
    hist_counts = Counter(c.driver for c in history)
    lines += [
        "## Held-out vs synthetic history, and re-weighting factors for Milestone 10",
        "",
        "A case's weight = its driver's share of the history / its share of held-out. Controls are pooled.",
        "",
        "| Driver | History share | Held-out cases | Held-out share | Weight |",
        "|---|---|---|---|---|",
    ]
    held_drivers = Counter("K" if lab.scenarios[0].startswith("K") else lab.scenarios[0] for lab in held)
    for driver in sorted(set(hist_counts) | set(held_drivers)):
        h_share = hist_counts.get(driver, 0) / hist_total if hist_total else 0.0
        n = held_drivers.get(driver, 0)
        o_share = n / len(held) if held else 0.0
        weight = f"{h_share / o_share:.3f}" if o_share else "n/a"
        lines.append(f"| {driver} | {h_share:.3f} | {n} | {o_share:.3f} | {weight} |")
    defect_share = sum(1 for lab in held if not lab.scenarios[0].startswith("K")) / len(held)
    hist_defect = sum(v for k, v in hist_counts.items() if k != "K") / hist_total if hist_total else 0.0
    lines += [
        "",
        f"Defect cases are {defect_share:.0%} of held-out but {hist_defect:.0%} of the history, so raw "
        "held-out results exaggerate differences between arms. Milestone 10 reports both raw and re-weighted "
        "results.",
        "",
    ]
    return "\n".join(lines)
