"""The gauges the dashboards and alerts read (OPS-04, ADR-0080): one snapshot from the stored tables, exported as
OpenTelemetry gauges with counts and money only."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.ai.harness import add_spend
from app.observability import ops_metrics
from app.persistence.models import SystemEvent
from app.services import jobs
from tests.arm_a import ArmA, make_arm_a

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def _seed(arm: ArmA) -> None:
    with arm.sessions() as s:
        jobs.enqueue(s, "probe", {}, clock=lambda _s: "2026-11-14T11:50:00Z")
        for action, at in (
            ("sign_in_failed", "2026-11-14T11:55:00.000Z"),
            ("sign_in_failed", "2026-11-14T11:56:00.000Z"),
            ("authorization_denied", "2026-11-14T11:57:00.000Z"),
            ("sign_in_failed", "2026-11-14T10:00:00.000Z"),  # outside the 15-minute window
            ("mcp_call", "2026-11-14T11:58:00.000Z"),
        ):
            s.add(SystemEvent(actor="system-test", actor_kind="system", action=action, detail={}, at_utc=at))
        s.commit()
        add_spend(s, 1_250_000, now=NOW)


def test_the_snapshot_counts_queue_age_spend_refusals_and_protocol_calls(arm: ArmA) -> None:
    _seed(arm)
    with arm.sessions() as s:
        snap = ops_metrics.snapshot(s, {"day": 5.0, "month": 5.0}, now=NOW)
    assert snap["jobs_queued"] == 1 and snap["jobs_oldest_age"] == 600.0 and snap["jobs_dead"] == 0
    assert snap["ai_spend"] == {"day": 1.25, "month": 1.25} and snap["ai_cap"] == {"day": 5.0, "month": 5.0}
    assert snap["refusals"] == {"sign_in_failed": 2, "authorization_denied": 1, "rate_limited": 0, "csrf_failed": 0}
    assert snap["protocol_calls"] == {"mcp": 1, "a2a": 0}


def test_the_gauges_export_the_snapshot_with_only_code_labels(arm: ArmA) -> None:
    _seed(arm)
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    calls = []

    def take() -> dict[str, Any]:
        calls.append(1)
        with arm.sessions() as s:
            return ops_metrics.snapshot(s, {"day": 5.0, "month": 5.0}, now=NOW)

    ops_metrics.register(provider.get_meter("test"), take)
    data = reader.get_metrics_data()
    points: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                points[metric.name] = [(dict(p.attributes or {}), p.value) for p in metric.data.data_points]
    assert len(calls) == 1  # one database snapshot for all seven gauges
    assert points["loyalty.jobs.oldest_age"] == [({}, 600.0)]
    assert ({"period": "day"}, 1.25) in points["loyalty.ai.spend"]
    assert ({"action": "sign_in_failed"}, 2) in points["loyalty.security.refusals"]
    assert ({"protocol": "mcp"}, 1) in points["loyalty.protocol.calls"]
    labels = {k for series in points.values() for attrs, _ in series for k in attrs}
    assert labels <= {"period", "action", "protocol"}
    provider.shutdown()


def test_a_failed_snapshot_skips_one_round_instead_of_breaking_the_export() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])

    def broken() -> dict[str, Any]:
        raise RuntimeError("database away")

    ops_metrics.register(provider.get_meter("test"), broken)
    data = reader.get_metrics_data()
    exported = [m for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics] if data else []
    assert all(not m.data.data_points for m in exported)
    provider.shutdown()


def test_the_app_reports_up_even_before_its_first_request() -> None:
    """HTTP metrics appear only after a request; an idle app must still look alive to the app-silent rule."""
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    ops_metrics.register_up(provider.get_meter("test"))
    data = reader.get_metrics_data()
    assert data is not None
    (metric,) = [m for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics]
    assert metric.name == "loyalty.app.up" and [p.value for p in metric.data.data_points] == [1]
    provider.shutdown()


def test_nothing_is_installed_without_an_otlp_endpoint() -> None:
    assert ops_metrics.install("loyalty-worker", None, {}, {}) is None


def test_every_alert_rule_links_a_runbook_that_exists_and_every_runbook_is_listed() -> None:
    import yaml

    root = Path(__file__).resolve().parent.parent
    rules = yaml.safe_load((root / "observability/grafana/alerting/rules.yaml").read_text(encoding="utf-8"))
    found = [r for g in rules["groups"] for r in g["rules"]]
    assert len(found) >= 6
    index = (root / "docs/runbooks/README.md").read_text(encoding="utf-8")
    for rule in found:
        url = rule["annotations"]["runbook_url"]
        assert (root / url).is_file(), url
        assert Path(url).name in index, url
        assert rule["labels"]["owner"] and rule["labels"]["severity"] in {"warning", "critical"}
        assert json.dumps(rule).count("loyalty_") + json.dumps(rule).count("http_server") >= 1
