# Known limitations

Kept current at every milestone. Each line says what is limited, why, and what would change it.

## Added in Milestone 4 (2026-10-29)
- **No load test**: concurrency is proven for correctness (20 requests, one key), not for throughput (Milestone 12).
- **The mock API is a simplification**: real platforms differ in pagination, idempotency windows, lookup lag and
  error styles; the swap guide lists what to verify against a vendor sandbox.
- **Seeded fault counters are in memory** and reset when the mock API restarts (TD-10).
- **Control endpoints share the data token** locally and are off in public demo mode (TD-11).
- **The app is a placeholder**: health, readiness, migrations and the seed command only.

## Added in Milestone 3 (2026-10-29)
- **The history restates our assumptions.** Its outcomes come from the outcome model in
  `seed_data/generator/config/scenario_mix.yaml`, so the day-one numbers (27% wrong; 61% of failures predicted
  fixable without AI, 21% AI-only) demonstrate the method, not a finding.
- **Labels were written by the same author as the generator and (later) the arms.** The independent labeler and the
  owner's 30-label review reduce that risk; the review hasn't happened yet.
- **Request text is templated** (ADR-0032); the Spanish, French, Portuguese and German templates are unchecked by
  native speakers. A model-written slice comes in Milestone 15 (EVAL-06).
- **D15 held-out cases are dated July 2026**, outside the Sep–Oct held-out window, because the policy change pins
  them there (catalog change log).
- **D19's two-stay variant labels the unclaimed stay `not_claimed`** (no credit without a claim). This is a judgement
  call flagged for the label review.
- **The day-one dashboard page is deferred to Milestone 7** (ADR-0034); only the report and charts exist.
- **Generation speed depends on the machine:** about 5 s warm, about 70 s on a cold first run here.

## Added in Milestone 2 (2026-10-28)
- **The discovery sessions are fictional.** Stakeholder answers, volumes (about 320 requests a month), handling time
  (about 14 minutes) and costs ($32 per hour, $0.008 per point) are assumptions A1–A7, not measurements.
- **The defect catalog was written by the same author who will build the arms.** Pre-registration (commit
  `1f8b8e6`), control cases, unfixable cases and the A as-is variant reduce the bias; they don't remove it. Not
  independently reviewed.
- **Arm A in the benchmark looks better than a real legacy tool would**, because it runs on the shared safe write
  path; the A as-is variant shows the difference for D10, D11 and lost responses only.
- **Mermaid diagrams have not been rendered**; only checked for closed code blocks.
- **Threat model is a draft** (v0.1); the control matrix, test results and standards baseline come in Milestone 9.
- **Pricing in the stage 0 addendum is a method only**; Stage 9's model cost is not measured yet.

## As of Milestone 1 (2026-10-28)
- **No product yet.** Only setup, guidance, tracking and the preflight command exist. Everything else in the
  requirements matrix is `Planned`.
- **Preflight checks format, not validity.** It catches empty values, typos and wrong shapes (for example a key that
  doesn't start with `sk-ant-`). It cannot tell whether a key is revoked or has spend left; the live smoke test in
  Milestone 8 does that.
- **`.env` deny rules are configured but not confirmed.** `.claude/settings.json` denies reading `.env`, but this
  session was started from the parent folder, so whether Claude Code applies the rules has not been observed. Owner
  check: start Claude Code inside this folder and ask it to read `.env`; it must be refused.
- **No independent review.** The continuity review, the requirements matrix and the coverage map were written by
  Claude Code from the live site and repos. Nobody else has reviewed them.
- **Coverage map cells for stages PS–8 are taken from their published READMEs and case studies**, not re-measured.
- **Accounts setup is a first version.** Free-tier limits and some menu paths are marked unverified until each
  tool's milestone.
- **`make` is not installed on the owner's Windows machine.** The Makefile is untested there; the
  `scripts\*.ps1` equivalents are what was run.
- **No remote repository and no CI yet.** Checks ran locally only. CI arrives with the GitHub repo (owner's OK).
- **Local tools missing:** gitleaks, Terraform, Trivy, syft, AWS CLI, Supabase CLI (see `docs/tool-access-matrix.md`).
