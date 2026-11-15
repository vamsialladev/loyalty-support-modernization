"""The browser stack's Postgres databases are named safely, one pair per module (TD-57)."""

from __future__ import annotations

import re

from tests.browser.postgres_stack import names_for


def test_each_module_gets_its_own_databases_and_shares_the_roles() -> None:
    a, b = names_for("tests.browser.test_legacy_e2e"), names_for("tests.browser.test_arm_b_e2e")
    assert {a.app_db, a.mock_db}.isdisjoint({b.app_db, b.mock_db})
    assert a.app_db != a.mock_db
    assert (a.owner, a.app, a.mock) == (b.owner, b.app, b.mock)
    # never the demo's or the stack's own names, so a wrong URL can't drop a real database
    assert not {a.app_db, a.mock_db} & {"loyalty", "mock_customer_api", "loyalty_test", "mock_customer_api_test"}


def test_names_are_plain_identifiers_within_postgres_limits() -> None:
    names = names_for("tests.browser.Test-With.Odd chars and a very long module name that goes on and on")
    for name in (names.app_db, names.mock_db, names.owner, names.app, names.mock):
        assert re.fullmatch(r"[a-z0-9_]+", name), name
        assert len(name) <= 63, name  # Postgres truncates longer identifiers
