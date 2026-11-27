"""The wake page for vamsialla.com (LIVE-06): `site/loyalty-demo.html` and `site/assets/demo-wake.js`.

Static checks hold the page to the portfolio site's rules (CSP without 'unsafe-inline', every inline script hashed,
the demo's origin in connect-src only, external links with rel="noopener noreferrer") and to the demo's facts (poll
/login, never /healthz; the 5.9 labels; the honest "paused" note). A browser test serves both files from a fake
vamsialla.com and fakes a sleeping demo: two failed tries, then an answer, then the page must open the demo.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Any

import pytest

from tests.browser.test_legacy_e2e import chromium, playwright_api  # noqa: F401  (pytest fixtures)

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "site" / "loyalty-demo.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "site" / "assets" / "demo-wake.js").read_text(encoding="utf-8")
DEMO = "https://loyalty-demo-1023835827965.us-east5.run.app"


def csp() -> dict[str, list[str]]:
    content = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', PAGE)
    assert content, "the page has no CSP meta tag"
    return {part.split()[0]: part.split()[1:] for part in content.group(1).split("; ")}


def test_the_demo_url_matches_the_readme_and_the_hosting_guide() -> None:
    assert DEMO in (ROOT / "README.md").read_text(encoding="utf-8")
    assert f'id="wake-link" href="{DEMO}/login"' in PAGE  # the script reads its target from this one link


def test_it_polls_login_never_healthz() -> None:
    assert "healthz" not in PAGE
    assert "healthz" not in SCRIPT.replace("never /healthz", "")  # only the comment explaining why may name it
    assert "fetch(target" in SCRIPT and 'mode: "no-cors"' in SCRIPT


def test_the_csp_allows_the_demo_for_connections_only_and_no_unsafe_inline() -> None:
    policy = csp()
    assert DEMO in policy["connect-src"]
    for directive, sources in policy.items():
        assert "'unsafe-inline'" not in sources, directive
        if directive != "connect-src":
            assert DEMO not in sources, directive
    assert policy["default-src"] == ["'self'"]


def test_every_inline_script_is_allowed_by_its_hash() -> None:
    allowed = set(csp()["script-src"])
    inline = re.findall(r"<script>(.*?)</script>", PAGE, re.S)
    assert len(inline) == 2  # the site's theme and GoatCounter checks, byte for byte
    for body in inline:
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
        assert f"'sha256-{digest}'" in allowed
    assert '<script src="assets/demo-wake.js" defer></script>' in PAGE
    assert ' style="' not in PAGE  # the site allows no inline styles


def test_external_links_open_safely_and_the_page_is_labelled_honestly() -> None:
    for link in re.findall(r'<a [^>]*href="https://[^"]+"[^>]*>', PAGE):
        if "vamsialla.com" not in link:
            assert 'rel="noopener noreferrer"' in link, link
    text = " ".join(PAGE.split())
    assert "mock AI and synthetic data" in text and "fictional hotel group" in text
    label = "about 10 seconds after a quiet spell (longer on the first visit of the day, when the daily reset runs)"
    assert label in text  # the 5.9 label (owner, 2026-11-27), measured (M12 row 47)
    assert "20 s" not in text and "20 seconds" not in text and "about 90" not in text  # the old wait is gone
    assert "spending cap" in text and "can't tell" in text
    assert '<meta name="robots" content="noindex, follow">' in PAGE
    assert PAGE.count("<h1>") == 1 and 'role="status"' in PAGE


def test_no_nav_item_is_marked_current() -> None:
    """The page isn't a section of the site, so the site's own `site_sync.py --check` wants no current item. The
    first copy, taken from now.html, still marked Now as current and failed that check (verification log M12 row 46)."""
    assert 'aria-current="page"' not in PAGE
    assert 'class="more current"' not in PAGE


@pytest.mark.browser
def test_the_page_waits_for_the_demo_then_opens_it(chromium: Any) -> None:  # noqa: F811
    site = "https://vamsialla.test"
    fast = PAGE.replace('<html lang="en">', '<html lang="en" data-wake-retry-ms="200" data-wake-slow-ms="300">')
    tries: list[str] = []
    context = chromium.new_context()
    page = context.new_page()

    def serve(route: Any) -> None:
        url = route.request.url
        if url == f"{site}/loyalty-demo.html":
            route.fulfill(status=200, content_type="text/html", body=fast)
        elif url == f"{site}/assets/demo-wake.js":
            route.fulfill(status=200, content_type="text/javascript", body=SCRIPT)
        elif url.startswith(DEMO):
            tries.append(url)
            if len(tries) <= 2:
                route.abort("connectionrefused")  # still starting
            else:
                route.fulfill(status=200, content_type="text/html", body="<title>Sign in</title>the demo")
        else:
            route.fulfill(status=404, body="")  # fonts, styles, analytics: not needed here

    context.route("**/*", serve)
    try:
        page.goto(f"{site}/loyalty-demo.html")
        page.wait_for_url(f"{DEMO}/login", timeout=15_000)
        assert page.title() == "Sign in"
        assert all(url == f"{DEMO}/login" for url in tries)
        assert len(tries) >= 3  # two refused tries, then the answer
    finally:
        context.close()


@pytest.mark.browser
def test_a_slow_demo_shows_the_paused_note_and_keeps_the_link(chromium: Any) -> None:  # noqa: F811
    site = "https://vamsialla.test"
    fast = PAGE.replace('<html lang="en">', '<html lang="en" data-wake-retry-ms="100" data-wake-slow-ms="500">')
    context = chromium.new_context()
    page = context.new_page()

    def serve(route: Any) -> None:
        url = route.request.url
        if url == f"{site}/loyalty-demo.html":
            route.fulfill(status=200, content_type="text/html", body=fast)
        elif url == f"{site}/assets/demo-wake.js":
            route.fulfill(status=200, content_type="text/javascript", body=SCRIPT)
        elif url.startswith(DEMO):
            route.abort("connectionrefused")  # never answers
        else:
            route.fulfill(status=404, body="")

    context.route("**/*", serve)
    try:
        page.goto(f"{site}/loyalty-demo.html")
        playwright_api.expect(page.locator("#wake-slow")).to_be_visible(timeout=10_000)
        assert page.url == f"{site}/loyalty-demo.html"  # it never sends the visitor to a page that didn't answer
        assert page.locator("#wake-link").get_attribute("href") == f"{DEMO}/login"
    finally:
        context.close()
