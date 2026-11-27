"""Milestone 13: the MultiWOZ question count, on a small made-up fixture (CI never downloads the data)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluations import m13_multiwoz as mw


def _turn(
    speaker: str, intent: str = "find_hotel", requested: list[str] | None = None, name: str = ""
) -> dict[str, Any]:
    values = {"hotel-name": [name]} if name else {}
    state = {"active_intent": intent, "requested_slots": requested or [], "slot_values": values}
    return {"speaker": speaker, "utterance": "x", "frames": [{"service": "hotel", "state": state}]}


def _dialogues() -> list[dict[str, Any]]:
    return [
        {
            "dialogue_id": "D1",
            "services": ["hotel"],
            "turns": [
                _turn("USER"),
                _turn("SYSTEM"),
                _turn("USER", requested=["hotel-phone"], name="acorn"),
                _turn("USER", intent="book_hotel", requested=["hotel-ref"], name="acorn"),
            ],
        },
        {
            "dialogue_id": "D2",
            "services": ["hotel", "train"],
            "turns": [
                _turn("USER", requested=["hotel-phone"], name="acorn"),  # same hotel, same question: a safe repeat
                _turn("USER", requested=["hotel-phone"], name="bridge"),  # same question, another hotel
                _turn("USER", requested=["hotel-area"]),  # no hotel named yet
                _turn("USER", intent="NONE"),
            ],
        },
        {"dialogue_id": "D3", "services": ["train"], "turns": [_turn("USER", requested=["hotel-phone"])]},
    ]


def test_questions_are_split_into_private_unnamed_and_named_public() -> None:
    r = mw.analyse(_dialogues())
    assert r["hotel_dialogues"] == 2
    assert r["user_turns_about_the_hotel"] == 6
    assert r["user_turns_booking"] == 1
    assert r["user_turns_asking_a_question"] == 5
    assert r["question_turns_about_own_booking"] == 1
    assert r["question_turns_public_without_a_hotel_name"] == 1
    assert r["question_turns_public_about_a_named_hotel"] == 3
    assert r["named_public_repeats_keyed_by_hotel_and_slots"] == 1
    assert r["named_public_repeats_keyed_by_slots_only"] == 2
    # Without the property in the key, the "bridge" question would reuse "acorn"'s phone number.
    assert r["slot_only_repeats_where_an_earlier_one_was_another_hotel"] == 1


def test_files_that_are_not_the_pinned_ones_are_refused(tmp_path: Path) -> None:
    for name in mw.FILES:
        (tmp_path / name).write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        mw.load(tmp_path)


def test_the_committed_counts_carry_the_label_and_no_utterances() -> None:
    stored = json.loads(mw.OUT.read_text(encoding="utf-8"))
    assert stored["label"].startswith("Real public conversation data")
    assert stored["files_sha256"] == mw.FILES
    assert "utterance" not in json.dumps(stored)
