# Known limitations

Kept current at every milestone. Each line says what is limited, why, and what would change it.

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
