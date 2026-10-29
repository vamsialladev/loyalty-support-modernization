# Technical debt register

> **Early draft** (PURP-04). Deliberate shortcuts only: why each was taken, its risk, and the trigger to pay it
> down. Accidental debt found later goes here too, marked as such.

| ID | Shortcut | Why | Risk | Trigger to fix | Since |
|---|---|---|---|---|---|
| TD-01 | Preflight checks formats, not live validity of keys | No network calls in offline checks | A revoked key passes preflight | Live smoke test in M8 covers it; fold into a `--live` preflight option if operators need it | M1 |
| TD-02 | No CI yet; checks run locally | No remote repository until the owner approves | A broken commit isn't caught automatically | Repository created (M12 at the latest) | M1 |
| TD-03 | Line endings: Git warns LF → CRLF on every file | Windows default `core.autocrlf` | Shell scripts in containers may break with CRLF | Add `.gitattributes` before the first Dockerfile (M4) | M1 |
| TD-04 | Mermaid diagrams never rendered | No renderer installed | Broken diagrams on GitHub | First push to GitHub | M2 |
