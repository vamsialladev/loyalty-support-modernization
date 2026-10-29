# Technical debt register

> **Early draft** (PURP-04). Deliberate shortcuts only: why each was taken, its risk, and the trigger to pay it
> down. Accidental debt found later goes here too, marked as such.

| ID | Shortcut | Why | Risk | Trigger to fix | Since |
|---|---|---|---|---|---|
| TD-01 | Preflight checks formats, not live validity of keys | No network calls in offline checks | A revoked key passes preflight | Live smoke test in M8 covers it; fold into a `--live` preflight option if operators need it | M1 |
| TD-02 | No CI yet; checks run locally | No remote repository until the owner approves | A broken commit isn't caught automatically | Repository created (M12 at the latest) | M1 |
| TD-03 | ~~Line endings: Git warns LF → CRLF on every file~~ **Paid down in M3** with `.gitattributes` (LF everywhere; CRLF only for `.ps1` and `.csv`), needed so data checksums match across machines | Windows default `core.autocrlf` | — | Done | M1 |
| TD-04 | Mermaid diagrams never rendered | No renderer installed | Broken diagrams on GitHub | First push to GitHub | M2 |
| TD-05 | ~~Generator and analysis libraries sit in the main dependency group~~ **Paid down in M4** (ADR-0041: groups `api`, `data`, `dev`; images install `api` only) | One `uv sync` for everything while there's no app image | A heavier runtime image than the app needs | Move them to a `data` dependency group before the first Dockerfile (M4) | M3 |
| TD-06 | Request text comes from templates written in this repo; non-English templates not checked by native speakers | Deterministic, free, reviewable (ADR-0032) | Template wording can flatter an arm tuned on it | Model-written slice reported separately in M15 (EVAL-06); native-speaker review if a pilot needs those languages | M3 |
| TD-07 | Datasets are JSONL files that the mock API loads into Postgres on seed | **Updated M4:** the files are now the import source only; the database is the working copy | A stale database after regenerating | `scripts\stack.ps1 -Action reset-demo` after every regeneration; a check that compares counts with the manifest (in the Postgres tests) | M3 |
| TD-09 | Tests use Starlette's `TestClient`, which warns that it will move from `httpx` to `httpx2` | It works today; switching libraries mid-milestone adds risk | A future Starlette release breaks the tests | Starlette drops `httpx` support, or before M12 CI: pin or migrate to `httpx2` | M4 |
| TD-10 | Fault-rule counters (`times`) are in memory | The mock is durable about data, not about faults (ADR-0038) | A restart resets which seeded faults have fired | Faults that must span restarts (then a fault table) | M4 |
| TD-11 | The mock API's control endpoints (seed, reset) use the same token as its data endpoints | Fewer local secrets for the owner; control is off in public demo mode | Anyone with the read token can reset the local mock | Before any hosted demo: a separate control credential or no control endpoints at all (C.8) | M4 |
| TD-08 | Pure-Python generation (about 5 s warm, 70 s cold on the owner's machine); the test suite regenerates once per session | Simplicity over speed (ADR-0028) | Slow feedback; CI minutes | Vectorise the background world, or cache a session fixture across runs, if CI time exceeds about 5 minutes | M3 |
