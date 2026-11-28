# Loyalty Support Modernization

**A loyalty support team investigates "my points are missing" requests. This project builds the workflow three
ways (the legacy tool, an improved non-AI tool, and an AI-assisted tool) and measures which one gets the member's
points ledger right, with a supervisor approving every adjustment.**

> **Stage 9 of a simulated client engagement** for a fictional hotel group (Beach Resort, Mountain Lodge) and its
> Guest Rewards program. All data is synthetic. Independent portfolio project; no real customer, users or results.
> Discovery and scoping (stage 0): [hotel-ai-discovery](https://github.com/vamsialladev/hotel-ai-discovery).

> **Status: work in progress. Milestones 1–11 of 20 are complete; Milestone 12 (performance, observability, CI/CD,
> hardening) is under way.** Progress and every requirement's status:
> [docs/implementation-status.md](docs/implementation-status.md).

**[Loyalty Support demo (live) →](https://loyalty-demo-1023835827965.us-east5.run.app)** Live demo: mock AI, synthetic
data. Free hosting: the first page takes about 10 seconds after a quiet spell (longer on the first visit of the day,
when the daily reset runs). Paused if the month's cap is reached. How it's hosted and capped:
[docs/hosting-cloud-run.md](docs/hosting-cloud-run.md).

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

## Safe AI caching: results (Milestone 13)
**In this workflow, answer caching is unsafe (910 look-alike pairs, 0 shared correct answers); prompt caching is the
safe win: 26.0% lower cost per case, with the same quality.**

- **Measured first:** in the 280 frozen cases, 0 of 910 pairs with word-for-word identical masked messages share a
  correct answer, so no answer cache was built ([baseline](docs/m13-baseline.md)).
- **Then tested live** (claude-haiku-5-5, SYNTHETIC cases, 3 runs per arm on the same 80 held-out cases):
  - case success was 78 of 80 and false approvals 0 in every run, with caching and without;
  - cost per case fell from $0.001723 to $0.001275 (−26.0%), and by 30.4% in runs 1 and 2, the clean comparison;
  - no model calls were avoided: the same calls cost less. Live spend was $0.81 of a $1.55 cap
    ([results](docs/m13-results.md)).
- **Flags that travel with it:** one requeued job in run A3 (the SQLite race, TD-57); runs A3 and D3 shared the laptop
  with another batch; D3 had 5 invalid model results against 0 or 1 in the other runs, cause not established.
- **Recommendation:** turn it on, with four conditions ([decision memo](docs/m13-decision-memo.md)). It's off by
  default (`FEATURE_PROMPT_CACHE`), and the `/admin` switch turns it off without a restart.

## Run the checks (Windows PowerShell)

```powershell
uv sync
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

The whole CI pipeline, on your machine (needs Docker Desktop):

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
- **Safe AI caching (Milestone 13):** [Baseline](docs/m13-baseline.md) · [Phase 3 plan](docs/m13-phase3-plan.md) ·
  [Results](docs/m13-results.md) · [Decision memo](docs/m13-decision-memo.md) · [Datasets](docs/datasets.md) ·
  [Prompt-cache runbook](docs/runbooks/prompt-cache.md)
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
