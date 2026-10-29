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

## 4a. The data layer (Milestone 3)

**What it is.** A deterministic generator (`seed_data/generator/`) builds a synthetic world (members, stay records,
points ledger, posting queue), 280 benchmark cases with ground-truth labels, a 12-month legacy history, and folio
PDFs, receipt images and OTA emails. Same seed, same bytes.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action verify
```

| Where | What | Committed? |
|---|---|---|
| `seed_data/v1/` | What the customer's systems hold (the mock API reads it from Milestone 4), plus history and documents | No: regenerate with `-Action generate` |
| `benchmarks/datasets/v1/<split>.jsonl` | What an arm receives: the request(s) only | Yes |
| `benchmarks/datasets/v1/labels/` | Ground truth and the planted facts | Yes, but **the app must never read it** (a test enforces this) |
| `benchmarks/datasets/v1/manifest.json` | Checksums of every generated file | Yes |
| `policies/hg-demo/` | The written policy; rule parameters are in each file's front matter | Yes |
| `config/customers/hg-demo.yaml` | How this customer names its fields; how a blank channel is derived | Yes |

**How a label is made (ADR-0029).** Each scenario builder plants facts and says what the right outcome is;
`evaluations/labeler.py` recomputes the label from those facts and the policy files. If they disagree, generation
stops. That check has already caught one builder error (a multi-stay case over the supervisor limit).

**Why the app can't see labels.** If any arm could read expected answers, the benchmark would measure nothing. Labels
live only under `benchmarks/datasets/v1/labels/`, and `tests/test_generator.py` fails if `app/` mentions it.

**First task in this layer.** Add a variant to an existing scenario (for example a D17 case where the confirmation
number has an extra digit): change its builder in `seed_data/generator/scenarios.py`, regenerate, and see whether
the labeler agrees. Then explain what the manifest diff tells you.

## 5. Common failure modes so far
- **`ModuleNotFoundError: app`** when running pytest outside `uv run`: use `uv run pytest`.
- **Preflight says NOT READY:** expected with an empty `.env`; it lists exactly which settings are missing.
- **A test about the matrix fails:** a row cites a test that doesn't exist, or uses an unknown status label.
- **`labeler (...) != builder intent (...)` during generation:** a scenario builder and the policy disagree. Read
  the policy section first; the labeler is usually right.
- **`test_committed_manifest_is_reproduced` fails:** generator output changed. If the change is intended, regenerate
  and commit the new manifest with a reason; if held-out labels changed, that is a new dataset version.
- **Generation feels slow:** the first run on a cold machine took about 70 s (later runs about 5 s). Use
  `--scale 0.1 --no-documents` while iterating.

## 6. First tasks to try
1. Run the checks and read the preflight output for each profile.
2. Pick one `Planned` row in the matrix and find where the spec defines it.
3. Read one ADR and write down what would make you reverse it.
