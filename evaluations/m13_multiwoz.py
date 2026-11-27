"""Milestone 13: how often do real hotel messages ask a general question? MultiWOZ 2.2, test split (CACHE-01).

    uv run python -I evaluations/m13_multiwoz.py --data <folder with dialogues_001.json and dialogues_002.json>

The data isn't committed: `docs/datasets.md` says where it comes from (a pinned commit), its licence and checksums,
and how to download it. Only counts and slot names are written to `benchmarks/reports/m13/multiwoz-questions.json`,
never an utterance. Standard library only, so it runs with `python -I` over downloaded files.

A user turn is "about the hotel" when its hotel frame has an active intent. It "asks a question" when that frame
lists requested slots (in MultiWOZ 2.2's schema-guided format they are the slots the user asks for in that turn,
such as `hotel-parking` or `hotel-phone`). Those are facts about a named, public property: what an answer cache in a
knowledge assistant could serve, keyed by property. The analysis also counts what a key without the property would
get wrong.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "reports" / "m13" / "multiwoz-questions.json"
FILES = {
    "dialogues_001.json": "d6f43876cf130fdb2dfa8f96bc056b0995354137f02122e004925d01264ed386",
    "dialogues_002.json": "89af95d8f596a448e733d59b31be78f1dd1632eddd99d5cb298a3fcb1ac9d185",
}
SOURCE = "github.com/budzianowski/multiwoz @ fe0c8e65cfcd8462bd33c86e35f21addc84ca82b, data/MultiWOZ_2.2/test"
BOOKING_INTENTS = {"book_hotel"}
PRIVATE_SLOTS = {"hotel-ref"}  # the guest's own booking reference: never a cacheable answer


def load(folder: Path) -> list[dict[str, Any]]:
    dialogues: list[dict[str, Any]] = []
    for name, expected in FILES.items():
        raw = (folder / name).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f"{name}: checksum {actual} isn't the pinned {expected}")
        dialogues += json.loads(raw)
    return dialogues


def _hotel_frame(turn: dict[str, Any]) -> dict[str, Any] | None:
    return next((f for f in turn.get("frames", []) if f.get("service") == "hotel"), None)


def analyse(dialogues: list[dict[str, Any]]) -> dict[str, Any]:
    hotel_dialogues = [d for d in dialogues if "hotel" in d["services"]]
    about = asking = booking = 0
    slots: Counter[str] = Counter()
    keyed_seen: set[tuple[str, tuple[str, ...]]] = set()
    slot_seen: dict[tuple[str, ...], set[str]] = {}
    keyed_repeats = slot_repeats = slot_repeats_other_hotel = unnamed = private = public_named = 0
    dialogues_asking = 0
    for dialogue in hotel_dialogues:
        asked_here = False
        for turn in dialogue["turns"]:
            if turn["speaker"] != "USER":
                continue
            frame = _hotel_frame(turn)
            if frame is None or frame["state"]["active_intent"] == "NONE":
                continue
            about += 1
            booking += frame["state"]["active_intent"] in BOOKING_INTENTS
            requested = tuple(sorted(frame["state"]["requested_slots"]))
            if not requested:
                continue
            asking += 1
            asked_here = True
            slots.update(requested)
            if PRIVATE_SLOTS & set(requested):
                private += 1
                continue
            names = frame["state"]["slot_values"].get("hotel-name") or []
            hotel = names[0] if names else ""
            if not hotel:
                unnamed += 1  # no property to key on: an answer cache couldn't serve it safely
                continue
            public_named += 1
            key = (hotel, requested)
            keyed_repeats += key in keyed_seen
            keyed_seen.add(key)
            earlier = slot_seen.setdefault(requested, set())
            if earlier:
                slot_repeats += 1
                slot_repeats_other_hotel += bool(earlier - {hotel})
            earlier.add(hotel)
        dialogues_asking += asked_here
    return {
        "label": "Real public conversation data: MultiWOZ 2.2 test split, written by crowd workers in a role-play "
        "(licence: MIT per the repository, Apache-2.0 per the Hugging Face card; docs/datasets.md). No model used.",
        "source": SOURCE,
        "files_sha256": FILES,
        "dialogues": len(dialogues),
        "hotel_dialogues": len(hotel_dialogues),
        "hotel_dialogues_with_a_question": dialogues_asking,
        "user_turns_about_the_hotel": about,
        "user_turns_booking": booking,
        "user_turns_asking_a_question": asking,
        "question_share_of_hotel_turns": round(asking / about, 4) if about else None,
        "requested_slots": dict(slots.most_common()),
        "question_turns_about_own_booking": private,
        "question_turns_public_without_a_hotel_name": unnamed,
        "question_turns_public_about_a_named_hotel": public_named,
        "named_public_repeats_keyed_by_hotel_and_slots": keyed_repeats,
        "named_public_repeats_keyed_by_slots_only": slot_repeats,
        "slot_only_repeats_where_an_earlier_one_was_another_hotel": slot_repeats_other_hotel,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -I evaluations/m13_multiwoz.py")
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()
    result = analyse(load(args.data))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
