"""A real worker process that dies hard part way through a job (spec Part D: worker restart recovery).

    python -m tests.crash_worker <database url> <marker file>

It claims one job through the real `Worker`, writes the marker file, then ends the process with `os._exit`: no
`finally`, no commit, no signal handler, as a power cut would. The parent test checks the next claim recovers the job.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.persistence.database import make_engine, make_sessions
from app.services.jobs import ClaimedJob
from app.worker import Worker


def main() -> None:
    url, marker = sys.argv[1], Path(sys.argv[2])

    def die(_s: Session, _job: ClaimedJob) -> None:
        marker.write_text("started", encoding="utf-8")
        os._exit(9)

    Worker(make_sessions(make_engine(url)), {"crash_me": die}, lease_seconds=1.0, heartbeat_seconds=10.0).run_once()
    sys.exit(3)  # it found no job: the parent's test fails on the exit code


if __name__ == "__main__":
    main()
