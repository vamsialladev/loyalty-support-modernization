# Rollout stages, with stop and rollback criteria (ROLL-01; spec F.3)

How this system would go from offline evaluation to everyday use at a real customer. This is a **simulated
engagement**: stages 1 and 2 have been run here on synthetic data, and stages 3 to 5 need a real customer and real
participants (BIZ-02 is still open). Each stage names who decides (`docs/governance.md`: the sponsor is accountable
for rollout gates), what must be true to enter, what stops it, and how to go back.

| Stage | What runs | Enter when | Stop at once if | Roll back by |
|---|---|---|---|---|
| **1. Offline evaluation** | The benchmark on synthetic and held-out cases (`benchmarks/`), the frozen mock regression in the release gate (`scripts/release_gate.py`), red-team suite | Every pre-registered threshold is written down before any run (Milestone 10) | A held-out result misses its threshold, or a red-team test fails | Nothing to roll back: nothing is live |
| **2. Shadow recommendations** | Arm C proposes for live cases, but **nothing executes**: `FEATURE_ADJUSTMENT_EXECUTION=false`, or the kill switch engaged. Agents work the case as today and compare | Stage 1 passed and the release gate is green on the exact build | An `action_mismatch` rate above the drift threshold (`app.services.drift`); any proposal reaching a request without a person; a security event of severity 4 | Turn arm C off for new cases. Shadow writes nothing that matters |
| **3. Limited pilot** | A named group of agents and supervisors uses arm C on real cases. Execution stays human-approved, and the supervisor approves every adjustment | Stage 2 ran for an agreed period with drift inside its thresholds, the runbooks have owners, and the drills in `docs/drills.md` pass on the target platform | The `error-rate`, `dead-jobs` or `ai-quality-drift` alert fires and stays; a wrong adjustment is approved (an AI incident of severity 2); spend reaches its cap | **Kill switch on** (stops all postings at once); route the pilot group back to arm B; roll the image back, not the schema (`docs/rollback.md`) |
| **4. Human-approved execution** | All agents, still with supervisor approval on every adjustment | The pilot met its acceptance criteria (sponsor), with no unresolved severity 1 or 2 incident | As stage 3, or a reconciliation finds a posting the app didn't record | As stage 3, then reconcile every case touched since the last good build (`docs/rollback.md`, "Cases in progress") |
| **5. Broader rollout** | Other properties or a second customer configuration (Milestone 14) | Stage 4 is stable for an agreed period, and the second configuration passes its own stage 1 | As stage 3, per customer | Per customer: their configuration off, and everyone else unaffected |

## Rules for every stage
- **The stop is always available and tested:** the kill switch stops every posting in under a second (drill D7:
  the first refusal came 0.04 s after the switch). Releasing it posts each approved adjustment once.
- **A posting is never undone by rolling back code.** Reversals go through the customer's own adjustment process,
  and reconciliation tells you what really posted (drill D5).
- **Recovery is drilled:** a worker crash (D3), a customer-system outage (D2), a model outage (D1), and a measured
  restore (D4). See `docs/drills.md` for the results, and their limits.
- **Every stage change is a decision on record:** an ADR or a sponsor's sign-off, with the evidence that met the
  entry criteria.
