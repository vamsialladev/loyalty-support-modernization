"""Milestone 13, Phase 1: where could caching help arm C? Measured from stored files only (CACHE-01).

    uv run python -m evaluations.m13_baseline

Reads the frozen dataset (v1), its labels, the stored live arm C results and the spend ledger (one row per model
call). It calls no model and changes nothing. It writes `benchmarks/reports/m13/baseline.json`, which every number in
`docs/m13-baseline.md` points to.

Three questions, per step of arm C:
1. **Repeats.** After masking names, emails, member numbers, confirmation numbers, dates and numbers, how often does
   a member's message repeat one seen earlier? And when two masked messages match, do the cases share the correct
   answer? (If they don't, reusing an answer by message text would be wrong.)
2. **Policy context.** How many distinct sets of policy versions do the cases need?
3. **Model calls.** How many calls a case makes, and how many input tokens each call re-sends from the call before.
   That re-sent prefix is what provider prompt caching could bill at the cache-read price.

Prices and cache multipliers are inputs, not facts: `--cache-read` and `--cache-write` default to the multipliers the
Claude API reference gave on 2026-11-03 (0.1x and 1.25x of the input price, 5-minute cache). Re-check them before
a live run, as `config/ai/hg-demo.yaml` says for prices.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks" / "datasets" / "v1"
LIVE = ROOT / "benchmarks" / "results" / "live"
LEDGER = LIVE / "spend-ledger.jsonl"
OUT = ROOT / "benchmarks" / "reports" / "m13" / "baseline.json"
SPLITS = ("dev", "validation", "heldout", "stress", "fairness")
# Live runs on the frozen arm C configuration. Ablations change the configuration, the lost-response pass injects a
# fault, and the variability runs repeat a subset, so they're left out of the per-case baseline.
FROZEN_RUNS = (
    "c-live-dev",
    "c-live-validation",
    "c-heldout-r1",
    "c-heldout-r2",
    "c-heldout-r3",
    "c-stress",
    "c-stress-r2",
    "c-stress-r3",
    "c-fairness",
)
HELDOUT_RUNS = ("c-heldout-r1", "c-heldout-r2", "c-heldout-r3")
MONTHLY_CASES = {"two_properties": 320, "hundred_properties": 16000}  # docs/load-profile.md; 100 = 50 x 320

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_CODE = re.compile(r"\b(?:[A-Z]{2,4}-\d{3,}|[A-Z]{2,4}\d{4,})\b")
_NUMBER = re.compile(r"\d+")
_MONTHS = re.compile(
    r"\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|aug(ust)?|sep(t|tember)?|oct(ober)?|"
    r"nov(ember)?|dec(ember)?)\b"
)
_WORD = re.compile(r"[a-z<>]+")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _pct(values: list[float], q: float) -> float:
    """Nearest-rank percentile, the same rule for every number here."""
    ordered = sorted(values)
    if not ordered:
        return math.nan
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "p50": _pct(values, 50),
        "p95": _pct(values, 95),
        "p99": _pct(values, 99),
        "max": max(values),
    }


def _wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


# ---------- 1. repeats in the member's messages ----------


def _names(cases: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> set[str]:
    """Every name the synthetic data knows, so masking doesn't depend on guessing what a name looks like."""
    found: set[str] = set()
    for case in cases:
        for request in case["requests"]:
            if request.get("form_name"):
                found |= set(request["form_name"].lower().split())
        label = labels[case["case_id"]]
        for record in label["facts"].get("records", []):
            if record.get("guest_name"):
                found |= set(record["guest_name"].lower().split())
    return {n.strip(".,") for n in found if len(n) > 1}


def mask(text: str, names: set[str]) -> str:
    out = _EMAIL.sub("<email>", text)
    out = _CODE.sub("<code>", out)
    out = _NUMBER.sub("<n>", out)
    out = out.lower()
    out = _MONTHS.sub("<month>", out)
    words = [("<name>" if w in names else w) for w in _WORD.findall(out)]
    return " ".join(words)


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def _answer(label: dict[str, Any]) -> tuple[Any, ...]:
    """What a correct reply must say: the action, the points owed and the stays."""
    return (label["next_action"], label.get("owed_total"), tuple(sorted(label["facts"].get("claimed_stay_ids", []))))


def message_repeats(cases: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> dict[str, Any]:
    names = _names(cases, labels)
    texts = {c["case_id"]: mask("\n".join(r["text"] for r in c["requests"]), names) for c in cases}
    ids = [c["case_id"] for c in cases]
    exact_seen: set[str] = set()
    exact_repeats = 0
    for case_id in ids:
        if texts[case_id] in exact_seen:
            exact_repeats += 1
        exact_seen.add(texts[case_id])
    bags = {i: set(texts[i].split()) for i in ids}
    near: dict[str, int] = {}
    for threshold in (0.6, 0.8, 0.9):
        count = 0
        for n, case_id in enumerate(ids):
            if any(_jaccard(bags[case_id], bags[earlier]) >= threshold for earlier in ids[:n]):
                count += 1
        near[f"jaccard_{threshold}"] = count
    # Pairs whose masked text is identical: would an answer cached for one be right for the other?
    groups: dict[str, list[str]] = defaultdict(list)
    for case_id in ids:
        groups[texts[case_id]].append(case_id)
    pairs = same_action = same_answer = 0
    for members in groups.values():
        for a_index, a in enumerate(members):
            for b in members[a_index + 1 :]:
                pairs += 1
                same_action += labels[a]["next_action"] == labels[b]["next_action"]
                same_answer += _answer(labels[a]) == _answer(labels[b])
    near_pairs = near_same = 0
    for n, a in enumerate(ids):
        for b in ids[:n]:
            if _jaccard(bags[a], bags[b]) >= 0.8:
                near_pairs += 1
                near_same += _answer(labels[a]) == _answer(labels[b])
    total = len(ids)
    # Does anyone ask a general question an FAQ-style answer cache could serve? Count sentences ending in "?".
    questions: Counter[str] = Counter()
    asking = 0
    for case in cases:
        found = [
            s.strip()
            for r in case["requests"]
            for s in re.split(r"(?<=[.?!])\s+|\n", r["text"])
            if s.strip().endswith("?")
        ]
        asking += bool(found)
        questions.update(mask(s, names) for s in found)
    return {
        "cases": total,
        "cases_with_an_explicit_question": asking,
        "explicit_questions_masked": dict(questions.most_common()),
        "distinct_masked_messages": len(groups),
        "exact_repeat_cases": exact_repeats,
        "exact_repeat_rate": round(exact_repeats / total, 4),
        "near_repeat_cases": near,
        "identical_masked_pairs": pairs,
        "identical_pairs_same_next_action": same_action,
        "identical_pairs_same_full_answer": same_answer,
        "identical_pairs_wrong_if_reused": pairs - same_answer,
        "identical_pairs_wrong_if_reused_wilson95": _wilson(pairs - same_answer, pairs),
        "near_0.8_pairs": near_pairs,
        "near_0.8_pairs_same_full_answer": near_same,
        "masking": "emails, codes like BR-1234 and GR-12345, every number, month names, and every name in the data",
        "full_answer": "next_action, owed_total and the claimed stay IDs from the labels",
    }


# ---------- 2. policy context ----------


def policy_context(run: str) -> dict[str, Any]:
    rows = _jsonl(LIVE / run / "results.jsonl")
    seen: set[tuple[str, ...]] = set()
    repeats = 0
    sets: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        versions = tuple(sorted({v for vs in (row.get("policies") or {}).values() for v in vs}))
        sets[versions] += 1
        if versions in seen:
            repeats += 1
        seen.add(versions)
    return {
        "run": run,
        "cases": len(rows),
        "distinct_policy_sets": len(sets),
        "cases_reusing_an_earlier_set": repeats,
        "sets": {" + ".join(k) or "(none)": v for k, v in sets.most_common()},
    }


def policy_versions() -> dict[str, Any]:
    out = {}
    for path in sorted((ROOT / "policies").rglob("*.md")):
        front = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
        out[path.stem] = {
            "customer": path.parent.name,
            "effective_from": str(front.get("effective_from")),
            "effective_to": str(front.get("effective_to")),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
        }
    return out


# ---------- 3. model calls, from the spend ledger ----------


def _segment(run: str, ledger: list[dict[str, Any]], live: Path = LIVE) -> list[list[dict[str, Any]]]:
    """Split a run's calls into cases, in order, by matching each case's stored token totals exactly.

    Runs were one case at a time (concurrency 1), so calls are in case order. A case is complete when its calls' input
    and output tokens add up to what its results record says. Any mismatch raises: a wrong split would make every
    number below wrong.
    """
    calls = [c for c in ledger if c["run"] == run]
    cases = _jsonl(live / run / "results.jsonl")
    # The ledger keeps every call ever paid for. Where a run name was used twice (an earlier attempt, then the stored
    # run), the stored run is the tail whose totals match its results exactly.
    need = sum(c["input_tokens"] for c in cases)
    starts = [s for s in range(len(calls)) if sum(c["input_tokens"] for c in calls[s:]) == need]
    if not starts:
        raise ValueError(f"{run}: no tail of the ledger matches the stored results")
    calls = calls[starts[0] :]
    out: list[list[dict[str, Any]]] = []
    i = 0
    for case in cases:
        group: list[dict[str, Any]] = []
        tin = tout = 0
        while (tin, tout) != (case["input_tokens"], case["output_tokens"]):
            if i >= len(calls) or tin > case["input_tokens"]:
                raise ValueError(f"{run}: the ledger doesn't add up for {case['case_id']}")
            call = calls[i]
            group.append(call)
            tin += call["input_tokens"]
            tout += call["output_tokens"]
            i += 1
        out.append(group)
    if i != len(calls):
        raise ValueError(f"{run}: {len(calls) - i} ledger calls left over")
    return out


def _cache_projection(groups: list[list[dict[str, Any]]], read: float, write: float) -> dict[str, Any]:
    """Within one case only: call k re-sends call k-1's whole input, which a cache breakpoint at the end of each
    request would make a cache read. The first call of each case pays a write for all of its input (no warm prefix
    is assumed: see the cross-case note). Output tokens are unchanged."""
    plain = cached = 0.0
    resent = total = 0
    for calls in groups:
        previous = 0
        for k, call in enumerate(calls):
            x = call["input_tokens"]
            total += x
            plain += x
            if k == 0:
                cached += x * write
            else:
                reused = min(previous, x)
                resent += reused
                cached += reused * read + (x - reused) * write
            previous = x
    return {
        "input_tokens": total,
        "resent_from_previous_call": resent,
        "resent_share": round(resent / total, 4),
        "input_cost_units_plain": plain,
        "input_cost_units_cached": round(cached, 1),
        "input_cost_change": round(cached / plain - 1, 4),
    }


def model_calls(read: float, write: float, price_in: float, price_out: float) -> dict[str, Any]:
    ledger = _jsonl(LEDGER)
    per_run: dict[str, Any] = {}
    all_groups: list[list[dict[str, Any]]] = []
    heldout_groups: list[list[dict[str, Any]]] = []
    for run in FROZEN_RUNS:
        groups = _segment(run, ledger)
        all_groups += groups
        if run in HELDOUT_RUNS:
            heldout_groups += groups
        rows = _jsonl(LIVE / run / "results.jsonl")
        per_run[run] = {
            "cases": len(rows),
            "calls": sum(len(g) for g in groups),
            "calls_per_case": _summary([len(g) for g in groups]),
            "latency_s": _summary([r["latency_s"] for r in rows]),
            "cost_usd_per_case": _summary([r["cost_usd"] for r in rows]),
            "case_success_note": "scored in benchmarks/reports/heldout/comparison.md, not re-scored here",
        }
    first = [g[0]["input_tokens"] for g in all_groups]
    per_call_in = [c["input_tokens"] for g in all_groups for c in g]
    heldout_cost = [c["cost_usd"] for r in HELDOUT_RUNS for c in _jsonl(LIVE / r / "results.jsonl")]
    projection = _cache_projection(heldout_groups, read, write)
    in_tokens = sum(c["input_tokens"] for g in heldout_groups for c in g)
    out_tokens = sum(c["output_tokens"] for g in heldout_groups for c in g)
    input_share = in_tokens * price_in / (in_tokens * price_in + out_tokens * price_out)
    case_change = input_share * projection["input_cost_change"]
    return {
        "runs": per_run,
        "cases_segmented": len(all_groups),
        "calls_per_case_all": _summary([len(g) for g in all_groups]),
        "first_call_input_tokens": _summary(first),
        "input_tokens_per_call": _summary(per_call_in),
        "heldout_cost_usd_per_case": _summary(heldout_cost),
        "heldout_input_share_of_cost": round(input_share, 4),
        "heldout_within_case_cache_projection": projection,
        "heldout_case_cost_change_projected": round(case_change, 4),
        "assumptions": {
            "cache_read_multiplier": read,
            "cache_write_multiplier": write,
            "price_in_per_mtok": price_in,
            "price_out_per_mtok": price_out,
            "ttl": "5 minutes",
        },
    }


def prefix_size() -> dict[str, Any]:
    from app.ai.config import load_prompt
    from app.ai.tools import TOOL_SPECS

    prompt = load_prompt("arm_c_v1")
    tools = json.dumps(
        [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in TOOL_SPECS]
    )
    return {"system_prompt_chars": len(prompt.text), "tool_spec_chars": len(tools), "prompt_version": prompt.version}


def cross_case_warmth(monthly: int, ttl_minutes: float = 5.0) -> float:
    """Chance the next case starts within the cache lifetime, if cases arrived evenly at random through the month
    (Poisson). Real arrivals bunch in working hours, which would raise it: an assumption, labelled as one."""
    per_minute = monthly / (30 * 24 * 60)
    return round(1 - math.exp(-per_minute * ttl_minutes), 4)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m evaluations.m13_baseline")
    parser.add_argument("--cache-read", type=float, default=0.1)
    parser.add_argument("--cache-write", type=float, default=1.25)
    parser.add_argument("--price-in", type=float, default=0.10)
    parser.add_argument("--price-out", type=float, default=0.50)
    args = parser.parse_args()
    result = build(args.cache_read, args.cache_write, args.price_in, args.price_out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


def _sha(path: Path) -> str:
    """Line endings normalised, so a Windows checkout and CI hash the same file the same way."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _ledger_sha(runs: Sequence[str] = FROZEN_RUNS) -> str:
    """Only the ledger rows of the runs this baseline reads, in file order. The ledger grows with every later live run
    (Milestone 13's Phase 3 added rows), and that mustn't change what this baseline says it was built from."""
    rows = [line for line in LEDGER.read_text(encoding="utf-8").splitlines() if json.loads(line)["run"] in runs]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def build(read: float = 0.1, write: float = 1.25, price_in: float = 0.10, price_out: float = 0.50) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    labels: dict[str, dict[str, Any]] = {}
    for split in SPLITS:
        cases += _jsonl(DATASET / f"{split}.jsonl")
        labels |= {row["case_id"]: row for row in _jsonl(DATASET / "labels" / f"{split}.jsonl")}
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    calls = model_calls(read, write, price_in, price_out)
    return {
        "label": "Measured from stored files. Real model (claude-haiku-5-5) token counts from Milestone 10's live "
        "runs; SYNTHETIC cases and messages. Cost projections are estimates.",
        "dataset_version": manifest["dataset_version"],
        "inputs_sha256": {
            "spend-ledger.jsonl, rows of the nine runs used": _ledger_sha(),
            **{p.name: _sha(p) for p in (DATASET / f"{s}.jsonl" for s in SPLITS)},
        },
        "messages": message_repeats(cases, labels),
        "messages_heldout_only": message_repeats([c for c in cases if c["split"] == "heldout"], labels),
        "policy_context": {
            "versions": policy_versions(),
            "by_run": [policy_context(r) for r in ("c-live-dev", "c-heldout-r1")],
        },
        "model_calls": calls,
        "prefix": prefix_size(),
        "cross_case_warmth_5min": {k: cross_case_warmth(v) for k, v in MONTHLY_CASES.items()},
        "monthly_cases": MONTHLY_CASES,
    }


if __name__ == "__main__":
    main()
