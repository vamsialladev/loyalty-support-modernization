# Known limitations

Kept current at every milestone. Each line says what is limited, why, and what would change it.

## Added after Milestone 5 (2026-11-03 to 2026-11-04)
- **A note's length is not its quality** (ADR-0054). `deny_other` with 20 characters can still close a case wrongly, and
  a rule-based code against complete evidence is still an override with any non-empty note. Both are logged as overrides
  for review. Evidence-free rule-based closes are now refused (TD-17, closed).
- **Exactly-once isn't promised.** A posting can land between the re-check and the submit, a platform's lag can outlast the
  settle window, and a platform can forget keys (RFC-0001, risks). These are stated, and a pilot must measure them.
- **The settle window (60 s) and approval expiry (24 h) are assumptions** (TD-21).
- **Changed evidence is noticed at approve and execute, not when it changes** (TD-18). Nothing stale executes.
- **Search needs every word to match, in English** (`docs/retrieval.md`). Rule values come from front matter, so search can't
  change what a stay is owed.
- **The kill switch can't recall a submission already on its way:** at most one per worker (ADR-0061).
- **Arm B and C don't exist yet.** The eligibility engine is tested but not used by the console until Milestone 7.
- **Reopening keeps the history but is a person's judgment.** A length check can't judge a reason (`cases.reopen`).
- **Audit history is append-only for the app role only.** The owner role, a superuser and anyone with the backups can
  still rewrite it. It isn't tamper-proof (ADR-0058).
- **The owner's "unhealthy" run has no proven cause** (ADR-0052). The reproduction didn't fail, and Docker no longer holds
  that run's health events. Any repeat now prints its cause.
- **CI is a first version** (ADR-0053): no image builds or compose check; those run locally until Milestone 12.

## Added in Milestone 5 (2026-10-29)
- **Approvals are not yet bound to an evidence snapshot**, and concurrent executes are not locked (TD-12, TD-13). The
  thin shared write path refuses a second credit for a stay and reconciles uncertain outcomes by key, but the
  binding hash, invalidation, row locks and durable jobs are Milestone 6. No benchmark runs before then.
- **Sign-in is local demo sign-in**: six accounts share one local password; no login rate limit, lockout or recovery
  yet (TD-15, Milestone 9). Fine for local synthetic data; not for a hosted demo.
- **Arm A has not been scored.** The scripted agent ran over the dev split for mechanics only. Arm A's accuracy on
  held-out cases is measured in Milestone 10, after the thresholds file is committed.
- **The scripted agent is one reading of the legacy tool**, fixed in its docstring. A human using the same screens
  might do better or worse; only the timing protocol with real participants measures that (E.7).
- **The legacy limits are modelled, not observed.** They come from the pre-registered catalog, not from a real
  company's tool; a real engagement would observe the client's tool instead (swap guide, Milestone 5 section).
- **The browser test covers the happy path and self-approval only.** Escalation, rejection, reconciliation and
  reopening are tested at service level; their browser tests are Milestone 7 (TEST-05).
- **The console is a first version**: basic accessibility only (labels, keyboard, focus, AA colours); the full
  UI-03 pass, the metrics page and the day-one dashboard are Milestone 7.
- **The "app is a placeholder" limitation from Milestone 4 no longer applies.**

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
- **No remote repository and no CI yet.** Checks ran locally only. (Superseded 2026-11-03: private repository and a first CI workflow, ADR-0053.)
- **Local tools missing:** gitleaks, Terraform, Trivy, syft, AWS CLI, Supabase CLI (see `docs/tool-access-matrix.md`).

## Added in Milestone 7 (2026-11-06)
- **Arm B has no OCR yet:** attachments aren't read, and the case says so with the flag `attachment_not_read`. Planned with Milestone 8's
  extraction, before the benchmark (TD-31).
- **Language:** the console is English only. Spanish, French, Portuguese and German messages are detected and sent to a person. Other
  languages aren't detected and go through the rules as they are. Dates and numbers aren't localized; times show on the property's clock.
- **Member replies are typed in by staff.** There's no inbound email or portal in this simulation.
- **Arm A's screens keep their UTC times.** They're part of the registered baseline (D04).
- **Metrics are counts, not scores.** Whether an outcome was right is only known in the benchmark, against labels the app never sees.
- **Scripted runs say nothing about human time** (spec E.7).

## Added in Milestone 8 (2026-11-06)
- **No real model has run.** Everything about arm C is verified on a mock and scripted models only. `scripts/live_smoke_ai.py` is NOT RUN until the owner approves it.
- **Redaction is pattern matching.** It catches emails, phone numbers, card numbers and API-key shapes. It misses a number written in words, and addresses. Names stay, because reading a request needs them.
- **Provider data terms aren't checked.** Check retention and any data agreement before sending real data.
- **Image OCR is blocked** (Tesseract isn't installed). A scanned PDF has no text layer, so it goes to a person.
- **Routing can't be judged from these numbers:** see `docs/model-card-routing.md`. Two Appendix I classes aren't in the dataset.
- **Injection is contained, not prevented.** A model may repeat an injected instruction in its draft. Drafts aren't sent, and business effects are what the tests check.
- **Non-English messages:** arm C's drafts in other languages are unreviewed machine text until staff read them, and staff may not read that language.
