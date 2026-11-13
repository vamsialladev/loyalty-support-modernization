"""The A2A specialist against an independent peer: the A2A TCK (spec G.4, G.13; Appendix C, M11).

Opt in, because it needs a pinned checkout of the TCK with its own environment:

    git clone https://github.com/a2aproject/a2a-tck <scratch>\\a2a-tck
    git -C <scratch>\\a2a-tck checkout 70f6f73c30208e80c889141907e094899e6e9f05
    cd <scratch>\\a2a-tck; uv sync --frozen --python 3.12
    $env:RUN_INTEROP = "1"; $env:A2A_TCK_DIR = "<scratch>\\a2a-tck"; uv run pytest tests/interop/test_a2a_tck.py -s

The TCK is not our code and doesn't use our SDK: it has its own httpx JSON-RPC client and its own schema checks. The
specialist runs as a real HTTP server on a free local port, reading synthetic stays.

**One thing the harness does for the TCK:** this TCK commit has no way to send a bearer token (its docs describe
`A2A_AUTH_*` settings, but the code at the pinned commit doesn't read them). So the harness adds a token signed by a
key made for this run to each request that arrives without one. The specialist still checks that token in full. The
TCK therefore doesn't test our authentication; `tests/test_a2a.py` and the real-Keycloak check do.

The test records what the TCK reported and fails only if the TCK didn't run or the agent card checks didn't pass.
Scenario checks need the agent to act out the TCK's Gherkin scenarios, keyed on `messageId` prefixes. The specialist
doesn't, by design, so those results are recorded, not asserted.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from starlette.types import ASGIApp, Receive, Scope, Send

from protocols.a2a.specialist import SCOPE, SpecialistConfig, build_app
from protocols.common.tokens import ResourceServer, StaticKeys, TokenVerifier
from tests.arm_a import ArmA, make_arm_a
from tests.conftest import ROOT
from tests.protocol_tokens import ISSUER, TestIssuer

TCK_COMMIT = "70f6f73c30208e80c889141907e094899e6e9f05"
TCK_DIR = Path(os.environ.get("A2A_TCK_DIR", ""))
EVIDENCE = ROOT / "security" / "evidence" / "a2a-tck-run.txt"
REPORT_COPY = ROOT / "security" / "evidence" / "a2a-tck-compatibility.json"
RESULT = re.compile(r"^(tests/compatibility/\S+) (PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\b", re.MULTILINE)
SKIP = re.compile(r"^SKIPPED \[(\d+)\] [^:]+:\d+: (.+)$", re.MULTILINE)

pytestmark = [
    pytest.mark.interop,
    pytest.mark.skipif(os.environ.get("RUN_INTEROP") != "1", reason="opt-in: set RUN_INTEROP=1"),
    pytest.mark.skipif(not (TCK_DIR / "run_tck.py").is_file(), reason="A2A_TCK_DIR isn't a TCK checkout"),
]


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class AddToken:
    """Adds a bearer token to requests that arrive without one, because the pinned TCK can't send one. Notes each
    request's method, path and A2A-Version header (never the token)."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.header = (b"authorization", f"Bearer {token}".encode())
        self.seen: list[tuple[str, str, str]] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            self.seen.append((scope["method"], scope["path"], headers.get(b"a2a-version", b"-").decode()))
            if b"authorization" not in headers:
                scope = {**scope, "headers": [*scope["headers"], self.header]}
        await self.app(scope, receive, send)


def tck_python() -> Path:
    windows = TCK_DIR / ".venv" / "Scripts" / "python.exe"
    return windows if windows.is_file() else TCK_DIR / ".venv" / "bin" / "python"


def test_the_a2a_tck_runs_against_the_specialist(arm: ArmA) -> None:
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    idp = TestIssuer()
    config = SpecialistConfig(url, ISSUER, "hg-demo", ("http://localhost",))
    verifier = TokenVerifier(ResourceServer("a2a-specialist", ISSUER, url, frozenset({SCOPE})), StaticKeys(idp.jwks()))
    token = idp.token(audience=url, scope=SCOPE, client_id="a2a-tck", expires_in=3600)
    app = AddToken(build_app(config, verifier, lambda: arm.systems()), token)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    reports = TCK_DIR / "reports"
    shutil.rmtree(reports, ignore_errors=True)
    try:
        run = subprocess.run(  # a fixed command: the pinned TCK checkout and a local URL
            [str(tck_python()), "run_tck.py", "--sut-host", url, "--transport", "jsonrpc", "-v", "--", "-rs"],
            cwd=TCK_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            timeout=1800,
            check=False,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    commit = subprocess.run(
        ["git", "-C", str(TCK_DIR), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    report_file = reports / "compatibility.json"
    assert report_file.is_file(), (run.stdout + run.stderr)[-3000:]
    report = json.loads(report_file.read_text(encoding="utf-8"))
    shutil.copyfile(report_file, REPORT_COPY)

    results = [m.groups() for m in RESULT.finditer(run.stdout)]
    outcomes = Counter(outcome for _, outcome in results)
    failed = [test for test, outcome in results if outcome in ("FAILED", "ERROR")]
    skips: Counter[str] = Counter()
    for m in SKIP.finditer(run.stdout):
        skips[re.sub(r"Task [0-9a-f-]{36}", "Task <id>", m.group(2).strip())] += int(m.group(1))
    tail = [line for line in run.stdout.splitlines() if line.startswith("=") and ("passed" in line or "failed" in line)]
    versions = sorted({v for _, _, v in app.seen if v != "-"})
    by_level = {k: v for k, v in report["summary"].items() if k.endswith("_compatibility")}
    requirement_fails = sorted(
        f"{rid} ({req.get('level')})" for rid, req in report["per_requirement"].items() if req.get("status") == "FAIL"
    )
    lines = [
        "A2A specialist against the A2A TCK (an independent peer; spec G.4, Appendix C M11)",
        f"Date: {datetime.now(UTC).date().isoformat()}",
        "Command: $env:RUN_INTEROP='1'; $env:A2A_TCK_DIR='<scratch>\\a2a-tck'; "
        "uv run pytest tests/interop/test_a2a_tck.py -s",
        f"Peer: a2aproject/a2a-tck at {commit} (pinned {TCK_COMMIT}); its own httpx client, no a2a-sdk",
        f"TCK command: run_tck.py --sut-host {url} --transport jsonrpc -v; exit {run.returncode}",
        "Server: protocols/a2a/specialist.py on a2a-sdk 1.3.0, A2A 1.0, JSON-RPC over HTTP, 127.0.0.1",
        f"A2A-Version headers the TCK sent: {', '.join(repr(v) for v in versions) or 'none sent'}",
        f"Requests the specialist received: {len(app.seen)}",
        "Tokens: the TCK can't send one at this commit, so the harness added a test-signed token "
        "(scope reservation.evidence) to each request without one; the specialist verified it",
        f"pytest summary: {tail[-1].strip('= ') if tail else 'not found'}",
        f"Outcomes: {dict(sorted(outcomes.items()))}",
        f"TCK compatibility by level (automated checks only): {by_level}",
        f"TCK per transport: {report['per_transport']}",
        f"Requirements marked FAIL: {requirement_fails or 'none'}",
        "Failed tests:",
        *[f"  {test}" for test in failed],
        "Skip reasons (count):",
        *[f"  {count} x {reason}" for reason, count in skips.most_common()],
        "Full report: security/evidence/a2a-tck-compatibility.json; pytest output: a2a-tck-pytest-output.txt",
    ]
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    output = run.stdout[-200_000:]
    for local in (str(TCK_DIR.resolve()), TCK_DIR.resolve().as_posix()):  # no local folder names in the evidence
        output = output.replace(local, "<a2a-tck>")
    (ROOT / "security" / "evidence" / "a2a-tck-pytest-output.txt").write_text(output, encoding="utf-8")

    assert run.returncode in (0, 1), (run.stdout + run.stderr)[-3000:]  # 0 all passed, 1 some failed: it ran
    assert outcomes["PASSED"] > 0
    assert not [test for test in failed if "/agent_card/" in test], "the agent card should pass every TCK check"
