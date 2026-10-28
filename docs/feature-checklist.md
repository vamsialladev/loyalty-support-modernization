# Feature checklist

A plain view of what the product does today. A box is ticked only when its requirement is "Implemented and verified"
in `docs/requirements-matrix.md`.

## Developer setup (Milestone 1)
- [x] `.env` is Git-ignored; `.env.example` holds no secrets (ACC-01, ACC-02)
- [x] `python -m app.preflight --profile <name>` reports set / missing / invalid format, never values (PROF-04, ACC-05)
- [x] A test fails if any `.env` secret value appears in a tracked file (ACC-07)
- [x] One offline test command: `scripts\test.ps1` (Windows) / `make test` (TEST-06)
- [ ] Claude Code deny rules for `.env` confirmed working in a session started in this folder (ACC-03)

## Product (Milestones 3–8)
- [ ] Synthetic members, stays, ledger, policies, requests (DATA-*)
- [ ] Mock customer API with failure injection (MOCK-*)
- [ ] Legacy arm A end to end in the browser (ARMA-01)
- [ ] Deterministic eligibility and policy-by-date retrieval (ELIG-01, POL-04)
- [ ] Case state machine, supervisor approval, no self-approval, approval binding (WP-01–WP-06)
- [ ] Idempotent execution, reconciliation after a lost response, kill switch (WP-07–WP-10)
- [ ] Durable job queue with leases and recovery (JOB-*)
- [ ] Arm B and the full console (ARMB-01, UI-01)
- [ ] Arm C with a bounded loop and cited recommendations (ARMC-01, AI-*)

## Evidence (Milestones 2–3, 10)
- [ ] Defect catalog and hypotheses committed before arms B and C (LGF-01)
- [ ] ≥60 labelled cases in four splits (EVAL-01)
- [ ] A vs B vs C benchmark on held-out cases with final-ledger accuracy (LGF-08)
- [ ] Business-value report chosen by the evidence (BIZ-04)

## Security, protocols, operations, portfolio
Tracked in the matrix (SEC-*, PROTO-*, OPS-*, DEL-*, PA-*). Boxes are added here as each milestone starts.
