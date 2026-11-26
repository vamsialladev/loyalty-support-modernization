"""The demo smoke test waits for a hosted demo on a page Cloud Run passes to the app (verification log, Milestone 12).

On the live demo (2026-11-23), `GET /healthz` answered 404 with an empty body in 0.6 s, from Google's front end: Cloud
Run reserves some paths ending in `z` and recommends avoiding all of them. The smoke test waited three minutes on that
404 and failed before it checked anything, and the 404 never woke the instance.
"""

from __future__ import annotations

from pathlib import Path

from scripts import demo_smoke


def test_the_smoke_test_waits_on_a_path_cloud_run_passes_to_the_app() -> None:
    assert demo_smoke.WAKE_PATH == "/login"
    assert not demo_smoke.WAKE_PATH.rstrip("/").endswith("z")


def test_waiting_on_the_wake_path_is_what_the_first_check_reports() -> None:
    source = Path(demo_smoke.__file__).read_text(encoding="utf-8")
    assert 'f"{base}/healthz"' not in source  # never the reserved path again
    assert "{WAKE_PATH}" in source
