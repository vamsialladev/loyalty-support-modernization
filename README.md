# Loyalty Support Modernization

**A loyalty support team investigates "my points are missing" requests. This project builds the workflow three
ways (the legacy tool, an improved non-AI tool, and an AI-assisted tool) and measures which one gets the member's
points ledger right, with a supervisor approving every adjustment.**

> **Stage 9 of a simulated client engagement** for a fictional hotel group (Beach Resort, Mountain Lodge) and its
> Guest Rewards program. All data is synthetic. Independent portfolio project; no real customer, users or results.
> Discovery and scoping (stage 0): [hotel-ai-discovery](https://github.com/vamsialladev/hotel-ai-discovery).

**Status: Milestone 2 of 20 (discovery, architecture, pre-registered defect catalog and hypotheses).** There is no
app to run yet. Results, a demo and a live link will
appear here only when they exist and are measured. Progress: [docs/implementation-status.md](docs/implementation-status.md).

## What exists today
- The build specification: [docs/MASTER-SPEC.md](docs/MASTER-SPEC.md)
- How this stage fits the published engagement: [docs/continuity.md](docs/continuity.md)
- Every requirement with its tier, milestone and status: [docs/requirements-matrix.md](docs/requirements-matrix.md)
- A configuration check that never prints secrets: `python -m app.preflight`

## Run the checks (Windows PowerShell)

```powershell
uv sync
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
copy .env.example .env
```

```powershell
uv run python -m app.preflight --profile portfolio
```

## Run the checks (macOS / Linux)

```bash
uv sync
```

```bash
make test
```

```bash
cp .env.example .env
```

```bash
make preflight PROFILE=portfolio
```

Prerequisites: Python 3.12 and [uv](https://docs.astral.sh/uv/). Docker Desktop and Node.js are needed from
Milestone 4 on. No API key is needed for any offline check.

## Documentation
- **Pre-registered before any arm was built (2026-10-28):** [Legacy defect catalog](docs/legacy-defect-catalog.md) ·
  [Hypotheses H1–H7](docs/hypotheses.md)
- **Discovery:** [Customer discovery](docs/customer-discovery.md) ·
  [Stage 0 loyalty addendum](docs/stage0-loyalty-addendum.md) ·
  [Business requirements](docs/business-requirements.md) · [Product requirements](docs/product-requirements.md) ·
  [Workflow](docs/workflow.md) · [Legacy discovery](docs/legacy-discovery.md) · [KPI tree](docs/kpi-tree.md)
- **Design and plans:** [Architecture](docs/architecture.md) ·
  [Baseline measurement plan](docs/baseline-measurement-plan.md) · [Experiment plan](docs/experiment-plan.md) ·
  [Threat model](security/threat-model.md) · [Governance and RACI](docs/governance.md) ·
  [Registers](docs/registers.md)
- [Implementation plan](docs/implementation-plan.md) · [Status](docs/implementation-status.md) ·
  [Decisions](docs/decisions.md) · [Known limitations](docs/known-limitations.md) ·
  [Verification log](docs/verification-log.md) · [Session handoff](docs/session-handoff.md)
- [Tool access matrix](docs/tool-access-matrix.md) · [Accounts setup](docs/accounts-setup.md) ·
  [Backlog](docs/backlog.md) · [Portfolio coverage map](docs/portfolio-coverage-map.md)

## Author
Vamsi Alla · [vamsialla.com](https://vamsialla.com) · [GitHub](https://github.com/vamsialladev) ·
[LinkedIn](https://www.linkedin.com/in/vamsi-alla/)

## License
MIT. See [LICENSE](LICENSE).
