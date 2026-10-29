# Onboarding: your first day on Stage 9

> **Early draft**, updated at the end of every milestone (project purpose, PURP-03). Written for a newly joined
> engineer. If something here is wrong or missing, fixing it is a good first pull request.

## 1. What this project is
A simulated client engagement for a fictional hotel group's loyalty team: members write "my points are missing", and
the project builds and measures three ways to handle it: the legacy tool (arm A), an improved non-AI tool (arm B)
and an AI-assisted tool (arm C), all with a supervisor approving every points adjustment. All data is synthetic.
Start with `README.md`, then `docs/project-purpose.md`.

## 2. How to run it today

```powershell
uv sync
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
uv run python -m app.preflight --profile portfolio
```

On macOS/Linux use `make test` and `make preflight`. No API key is needed for anything offline.

## 3. Where things live

| Path | What |
|---|---|
| `docs/MASTER-SPEC.md` | The binding specification. Read the Part for your task |
| `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/` | Rules every contributor and coding assistant follows |
| `docs/requirements-matrix.md` | Every requirement with tier, milestone and status. Pick work from here |
| `docs/decisions.md` | ADRs: why things are the way they are |
| `docs/legacy-defect-catalog.md`, `docs/hypotheses.md` | Pre-registered experiment design. Don't edit without a change-log entry |
| `app/preflight.py` | Configuration readiness check (never prints values) |
| `app/env_leaks.py` | Finds `.env` secret values in tracked files |
| `scripts/matrix_scores.py` | Completion scores counted from the matrix |
| `tests/` | Every check above has a test |

## 4. Why the key decisions were made (read these ADRs first)
- ADR-0019: AI may interpret and explain; eligibility, points, approval and execution stay deterministic.
- ADR-0016 and ADR-0018: why the defect catalog and hypotheses were committed before any arm existed, and why an
  "A as-is" variant runs without the safe write path.
- ADR-0014: why preflight fails loudly instead of falling back to the mock provider.
- ADR-0005: why this isn't on free Streamlit hosting like the other stages.

## 5. Common failure modes so far
- **`ModuleNotFoundError: app`** when running pytest outside `uv run`: use `uv run pytest`.
- **Preflight says NOT READY:** expected with an empty `.env`; it lists exactly which settings are missing.
- **A test about the matrix fails:** a row cites a test that doesn't exist, or uses an unknown status label.

## 6. First tasks to try
1. Run the checks and read the preflight output for each profile.
2. Pick one `Planned` row in the matrix and find where the spec defines it.
3. Read one ADR and write down what would make you reverse it.
