"""Arm B's plain rules, without any service or database (D01, D02, D13, D16, D18, D19, D20, D23)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.arms.conventional import identity as ident
from app.arms.conventional import signals
from app.arms.conventional.config import ConventionalConfig, conventional_config
from app.arms.conventional.identity import Candidate, IdentityClaim, IdentityStatus
from app.arms.conventional.investigation import explicit_arrival_dates
from app.domain.customer_records import Member
from benchmarks.intake import read_split

CONFIG = conventional_config("hg-demo")


def member(number: str = "GR-12345", first: str = "Elizabeth", last: str = "Núñez", **kw: Any) -> Member:
    base = {"email": "e.nunez@mail.test", "phone": "+1 201 555 0100", "tier": "gold", "status": "active"}
    return Member(number, first, last, **{**base, **kw})


def test_case_accents_dots_and_tags_dont_separate_people() -> None:
    assert ident.fold("  Núñez ") == "nunez"
    assert ident.normalize_email("E.Nunez+points@Mail.Test") == "enunez@mail.test"


@pytest.mark.parametrize(
    ("a", "b", "near"),
    [
        ("GR-59356", "GR-59536", True),  # adjacent digits swapped
        ("GR-85054", "GR-84054", True),  # one digit wrong
        ("GR-85054", "GR-85054", False),  # the same isn't "near"
        ("GR-11111", "GR-99999", False),
        ("GR-1234", "GR-12345", False),  # a different length isn't a slip of one digit in this format
    ],
)
def test_near_numbers(a: str, b: str, near: bool) -> None:
    assert ident.is_near_number(a, b) is near


def test_a_transposition_is_one_edit() -> None:
    assert ident.edit_distance("5935", "5395") == 1
    assert ident.edit_distance("abc", "abc") == 0
    assert ident.edit_distance("abc", "xyz") == 3


def test_listed_nicknames_and_dropped_accents_match_unlisted_forms_dont() -> None:
    m = member()
    assert ident.names_match("Liz Nunez", m, CONFIG)
    assert ident.names_match("elizabeth NÚÑEZ", m, CONFIG)
    assert not ident.names_match("Lisbet Nunez", m, CONFIG)  # for a person, or for arm C
    assert not ident.names_match("Elizabeth Okoro", m, CONFIG)  # a married name
    assert not ident.names_match("Elizabeth", m, CONFIG)


def _score(claim: IdentityClaim, m: Member) -> tuple[str, ...]:
    return ident.score(claim, m, CONFIG)


def test_identifiers_are_counted_separately() -> None:
    m = member()
    assert _score(IdentityClaim(("GR-12345",)), m) == (ident.EXACT_NUMBER,)
    assert _score(IdentityClaim(("GR-12354",)), m) == (ident.NEAR_NUMBER,)
    assert _score(IdentityClaim((), "E.NUNEZ@mail.test", "Liz Nunez"), m) == (ident.EMAIL, ident.NAME)


def test_an_exact_stay_on_the_profile_is_an_identifier_but_never_enough_alone() -> None:
    m = member()
    assert ident.score(IdentityClaim((), None, None), m, CONFIG, stay_owners=frozenset({m.member_number})) == (
        ident.STAY_ON_PROFILE,
    )
    alone = ident.choose([Candidate(m, (ident.STAY_ON_PROFILE,))])
    assert alone.status is IdentityStatus.NEEDS_SECOND_IDENTIFIER and alone.candidates == ()  # and it isn't shown
    both = ident.choose([Candidate(m, (ident.EMAIL, ident.STAY_ON_PROFILE))])
    assert both.status is IdentityStatus.CONFIRMED


def test_one_identifier_is_never_enough() -> None:
    m = member()
    alone = ident.choose([Candidate(m, (ident.EXACT_NUMBER,))])
    assert alone.status is IdentityStatus.NEEDS_SECOND_IDENTIFIER and alone.member is None
    assert ident.choose([]).status is IdentityStatus.NOT_FOUND


def test_two_identifiers_confirm_and_the_stronger_candidate_wins() -> None:
    right, other = member(), member("GR-99999", "Liz", "Nunez", phone="+1 201 555 0199", date_of_birth="1980-01-01")
    found = ident.choose(
        [Candidate(right, (ident.EXACT_NUMBER, ident.NAME)), Candidate(other, (ident.NEAR_NUMBER, ident.NAME))]
    )
    assert found.status is IdentityStatus.CONFIRMED and found.member == right


def test_two_different_people_with_equal_matches_are_never_guessed_between() -> None:
    a = member("GR-11111", date_of_birth="1980-01-01")
    b = member("GR-22222", phone="+1 201 555 0199", date_of_birth="1990-02-02")
    found = ident.choose([Candidate(a, (ident.EMAIL, ident.NAME)), Candidate(b, (ident.EMAIL, ident.NAME))])
    assert found.status is IdentityStatus.AMBIGUOUS and found.member is None


def test_duplicate_profiles_of_one_person_arent_ambiguous() -> None:
    a = member("GR-11111", date_of_birth="1980-01-01")
    b = member("GR-22222", date_of_birth="1980-01-01")
    assert ident.same_person(a, b)
    found = ident.choose([Candidate(a, (ident.EMAIL, ident.NAME)), Candidate(b, (ident.EMAIL, ident.NAME))])
    assert found.status is IdentityStatus.CONFIRMED


def test_a_missing_date_of_birth_never_counts_as_the_same_person() -> None:
    assert not ident.same_person(member("GR-11111"), member("GR-22222"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I stayed from July 2-3, 2026 at the resort", [date(2026, 7, 2)]),
        ("June 28 - July 1, 2026", [date(2026, 6, 28)]),
        ("May 10 to 13, 2026", [date(2026, 5, 10)]),
        ("Check-in was 12/17 if I remember right", []),  # D19: could be read two ways, so it's asked about
        ("sometime in October", []),
        ("February 30-31, 2026", []),
    ],
)
def test_only_unmistakable_dates_are_read(text: str, expected: list[date]) -> None:
    assert explicit_arrival_dates(text) == expected


def test_language_needs_two_unmistakable_words() -> None:
    assert signals.detect_language("Bonjour, merci pour votre aide") == "fr"
    assert signals.detect_language("Missing points. Beach Resort, May 10-13.") is None
    assert signals.detect_language("My friend said gracias at the desk.") is None


def test_identifiers_in_text_are_found_in_any_case() -> None:
    assert signals.member_numbers_in("my number is gr-12345") == ("GR-12345",)
    assert signals.confirmations_in("BR-1042 and trv-12345678, again BR-1042") == ("BR-1042", "TRV-12345678")


def test_the_signoff_name_is_read_from_the_last_line() -> None:
    assert signals.signoff_name("Hello\nThanks, Clara Kowalski") == "Clara Kowalski"
    assert signals.signoff_name("Hello\nPlease check this for me now today right away") is None


def test_rules_on_message_text_dont_fire_on_the_wrong_dev_cases(mock_template: dict[str, Any]) -> None:
    """Dev only. A rule that fires on ordinary messages sends everything to a person, which looks safe and isn't."""
    for item in read_split("dev", mock_template["datasets"]):
        scenarios = mock_template["labels"][item.case_id]["scenarios"]
        text = "\n".join(r.text for r in item.requests)
        assert (signals.detect_language(text) is not None) == ("D23" in scenarios), item.case_id
        assert bool(signals.out_of_scope_topics(text)) == ("D20" in scenarios), (item.case_id, text)
        assert signals.mentions_more_stays(text) == ("D16" in scenarios), (item.case_id, text)


def test_the_config_loads_lists_a_lead_can_read() -> None:
    assert isinstance(CONFIG, ConventionalConfig)
    assert "liz" in CONFIG.nicknames["elizabeth"]
    assert CONFIG.synonyms["retro credit"] == "missing points request"
