"""A real worker process that dies at a chosen moment during an execution (spec Part D, Appendix C).

    CRASH_APP_URL=... CRASH_MOCK_URL=... CRASH_MOCK_TOKEN=... python -m tests.crash_execution <before|after>

`before` dies at the moment it would submit; `after` dies right after the platform committed the credit. Either way
`os._exit` ends the process with no `finally`, no commit and no signal handler, as a power cut would. It uses the real
worker, real handlers and real adapter over HTTP. The parent test then proves recovery by reconciliation.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.domain.customer_records import AdjustmentRequest, AdjustmentResult
from app.persistence.database import make_engine, make_sessions
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.worker import Worker
from customer_shapes import CustomerShape

EXIT_CODE = 9


class DiesAtSubmit:
    def __init__(self, inner: MockCustomerApiAdapter, moment: str) -> None:
        self.inner, self.moment = inner, moment

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
        if self.moment == "after":
            self.inner.submit_adjustment(request, key)
        os._exit(EXIT_CODE)


def main() -> None:
    moment = sys.argv[1]
    app_url, mock_url, token = os.environ["CRASH_APP_URL"], os.environ["CRASH_MOCK_URL"], os.environ["CRASH_MOCK_TOKEN"]
    shape = CustomerShape.load("hg-demo")

    def systems(sim_time: str | None) -> DiesAtSubmit:
        return DiesAtSubmit(MockCustomerApiAdapter(mock_url, token, shape, sim_time=sim_time), moment)

    handlers = build_handlers(SharedWritePath(settle_seconds=0), systems)  # type: ignore[arg-type]
    Worker(make_sessions(make_engine(app_url)), handlers, lease_seconds=1.0, heartbeat_seconds=30.0).run_once()
    sys.exit(3)  # it never reached the submission: the parent test fails on this exit code


if __name__ == "__main__":
    main()
