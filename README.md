# Loyalty Support Modernization

**A loyalty support team investigates "my points are missing" requests. This project builds the workflow three
ways (the legacy tool, an improved non-AI tool, and an AI-assisted tool) and measures which one gets the member's
points ledger right, with a supervisor approving every adjustment.**

> **Stage 9 of a simulated client engagement** for a fictional hotel group (Beach Resort, Mountain Lodge) and its
> Guest Rewards program. All data is synthetic. Independent portfolio project; no real customer, users or results.
> Discovery and scoping (stage 0): [hotel-ai-discovery](https://github.com/vamsialladev/hotel-ai-discovery).

> **Status: work in progress. Milestones 1–11 of 20 are complete; Milestone 12 (performance, observability, CI/CD,
> hardening) is under way.** Nothing here is deployed or published yet. Progress and every requirement's status:
> [docs/implementation-status.md](docs/implementation-status.md).

## What exists today (Milestones 1–11)
- **Discovery and plans:** business case, pre-registered legacy defects and hypotheses, architecture, threat model
  ([documentation](#documentation) below).
- **Synthetic data and labels:** a reproducible generator, independent labels, fixed dataset splits
  ([composition](benchmarks/datasets/v1/composition.md), [label review](evaluations/label-review/README.md)).
- **Three ways to do the work:** the legacy tool (arm A), an improved non-AI tool (arm B) and an AI-assisted tool
  (arm C), each with a supervisor approving every adjustment, durable jobs, idempotent execution and reconciliation.
- **Security:** local and OpenID Connect sign-in, per-customer authorization, CSRF, rate limits, redaction and a
  red-team suite ([threat model](security/threat-model.md)).
- **A benchmark of the three arms** on synthetic cases, with its thresholds committed before the runs. Results and
  their limits (including the ones that must travel with them) are in the reports under `benchmarks/reports/` and in
  [known limitations](docs/known-limitations.md); none are claimed here.
- **Optional protocol doors** (MCP, A2A, AG-UI), off by default and read-only; the A2A result is verified with
  limitations ([protocol test results](docs/protocol-test-results.md)).
- A configuration check that never prints secrets: `python -m app.preflight`.

## Run the checks (Windows PowerShell)

```powershell
uv sync
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

The whole CI pipeline, on your machine (needs Docker Desktop; uses no GitHub Actions minutes):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ci_local.ps1
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

Prerequisites: Python 3.12 and [uv](https://docs.astral.sh/uv/). Docker Desktop is needed for the local stack, and
the browser tests need Chromium once: `uv run playwright install chromium` (they show SKIPPED without it). No API
key is needed for any offline check.

## Documentation
- **Start here:** [Project purpose](docs/project-purpose.md) · [Onboarding](docs/onboarding.md) ·
  [Executive brief](docs/executive-brief.md) · [Role coverage map](docs/role-coverage-map.md)
- **Principal view:** [Technical strategy](docs/technical-strategy.md) · [Scaling and limits](docs/scaling-and-limits.md) ·
  [Tech-debt register](docs/tech-debt-register.md) · [TCO](docs/tco.md) · [RFCs](docs/rfcs/README.md) ·
  [Real-system swap guide](docs/real-system-swap-guide.md) · [FDE tool map](docs/fde-tool-map.md) ·
  [Data sources](docs/data-sources.md) · [Using this at a company](docs/using-at-a-company.md)
- **Pre-registered before any arm was built (2026-10-28):** [Legacy defect catalog](docs/legacy-defect-catalog.md) ·
  [Hypotheses H1–H7](docs/hypotheses.md)
- **Data (Milestone 3):** [Day-one discovery](docs/day-one-discovery.md) · [Problem statement](docs/problem-statement.md) ·
  [Data dictionary](docs/data-dictionary.md) · [Benchmark composition](benchmarks/datasets/v1/composition.md) ·
  [Label review](evaluations/label-review/README.md)
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
