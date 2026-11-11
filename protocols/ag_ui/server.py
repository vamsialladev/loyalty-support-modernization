"""Start the console with the AG-UI endpoint on (spec G.2: an independent start command per protocol).

    FEATURE_AG_UI=true uv run python -m protocols.ag_ui.server

AG-UI talks to a frontend, and the frontend here is the console, so the endpoint lives in the console's process and
uses its session and CSRF checks rather than a token of its own. With the flag off, nothing starts and the normal
`uvicorn --factory app.main:create_app` serves the console without the endpoint.
"""

from __future__ import annotations


def main() -> int:  # pragma: no cover - the start command; tests build the app directly
    import uvicorn

    from app.settings import AppSettings

    if not AppSettings.from_env().feature_ag_ui:
        print("FEATURE_AG_UI is off: the AG-UI endpoint doesn't start. The console works without it.")
        return 2
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=8010)  # the console's usual port
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
