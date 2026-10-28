"""Find `.env` secret values inside Git-tracked files (Appendix K2.6). Reports file and variable names, never values.

python -m app.env_leaks          # exit 1 if any secret value from .env appears in a tracked file
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from dotenv import dotenv_values

from app.preflight import SECRET_NAMES

SECRET_LIKE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)$")
MIN_LENGTH = 8


def secret_values(values: Mapping[str, str | None], template: Mapping[str, str | None] | None = None) -> dict[str, str]:
    """Values worth searching for: secret-flagged or secret-looking names, at least MIN_LENGTH characters.

    A value equal to the template's own value (an unchanged default from .env.example) is not a secret.
    """
    template = template or {}
    return {
        name: value
        for name, value in values.items()
        if value
        and len(value.strip()) >= MIN_LENGTH
        and (name in SECRET_NAMES or SECRET_LIKE.search(name))
        and value != template.get(name)
    }


def find_leaks(secrets: Mapping[str, str], files: Iterable[Path]) -> list[tuple[str, str]]:
    """(file, variable name) for every secret value found in a file. Binary files are searched as bytes."""
    needles = {name: value.strip().encode() for name, value in secrets.items()}
    leaks: list[tuple[str, str]] = []
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        leaks.extend((str(path), name) for name, needle in needles.items() if needle in data)
    return leaks


def tracked_files(repo: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True, check=True).stdout
    return [repo / name for name in out.decode().split("\0") if name]


def main(repo: Path = Path(".")) -> int:
    env = repo / ".env"
    if not env.is_file():
        print("No .env file: nothing to check.")
        return 0
    template = repo / ".env.example"
    secrets = secret_values(dotenv_values(env), dotenv_values(template) if template.is_file() else None)
    leaks = find_leaks(secrets, tracked_files(repo))
    for path, name in leaks:
        print(f"LEAK: the value of {name} from .env appears in {path}")
    print(f"Checked {len(secrets)} secret value(s) from .env against tracked files: {len(leaks)} leak(s).")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
