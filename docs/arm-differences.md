# What differs between the arms (ARMS-01, spec B.8, F9)

**SYNTHETIC.** Every record here is fictional. Nothing on this page is a result: Milestone 10 measures these predictions.

**The same in every arm:** sign-in and roles, separation of duties, approval binding, the re-check before approval and before
execution, idempotency keys, the one-credit-per-stay index, reconciliation, the kill switch, and the audit log
(`app/services/write_path.py`). Authorization, approval and execution are never credited to arm B or arm C.

**Arm A is fenced:** `tests/test_arm_a_fence.py` holds its source hashes and what its scripted agent does on all 100 dev cases,
recorded before any arm B code (ADR-0063).

## Each arm B fix, and the pre-registered defect it answers

| Defect | Arm A (kept as registered) | Arm B | Where |
|---|---|---|---|
| D01 duplicate profiles | Searches one profile | Finds the same person's other profiles by phone, birth date and name; a credit on either counts | `conventional/identity.py` `linked_profiles` |
| D02 merged numbers | Not found | Follows `merged_into` both ways | `identity.py` `current_profile`, `investigation.py` `on_members_profile` |
| D03 blank channel | Denies | Engine derives it from the source code; otherwise a structured question | `domain/eligibility.py`, `services/conventional.py` `PROMPTS` |
| D04 UTC dates | Compares UTC dates | Business date on the property's clock | `domain/eligibility.py` |
| D05 partner numbers | Not searchable | `find_stays(partner_confirmation=...)` | `investigation.py` `resolve_confirmation` |
| D06 posting queue | Not on any screen | Read and shown; a pending posting blocks a credit | `investigation.py` `read_claim` |
| D07 reversals | Groups by date | Nets by stay across profiles | `investigation.py`, `domain/eligibility.py` |
| D08, D09 stale rules | Old wait, old channels, frozen index | Rules from the published policy version | `domain/eligibility.py`, `services/policies.py` |
| D12 synonyms | Exact keywords | Full-text search plus a synonym list a lead can read | `config/conventional/hg-demo.yaml`, `conventional.search_policy` |
| D13 exact lookup | Exact only | Normalized email, name search, near numbers, candidate list; two identifiers needed | `identity.py` |
| D14 four screens | Member, stay, ledger, policy | One view. **Scripted step counts only, never human time** | `templates/case_b.html` |
| D15 current policy only | Current rules | The version in force on the checkout date | `domain/policy.py`, `conventional.search_policy` |
| D16 several stays | One stay | **Partial:** explicit numbers become linked cases; asks about the rest | `conventional._split_group`, `mention_more_stays` |
| D17 wrong numbers | Not found | Missing prefix, or one near match within the member's own stays that doesn't contradict a stated date | `investigation.py` `resolve_confirmation` |
| D18 name forms | Not found | Listed nicknames and dropped accents; a different surname passes only with two other identifiers (exact email, and an exact confirmation number on that profile); anything else asks. **Goes further than the catalog's prediction:** RFC-0002 explains why | `identity.py`, `config/conventional/hg-demo.yaml` |
| D19 mixed dates | Wrong | Reads only dates with the month in words and a year; asks otherwise, never guesses | `investigation.py` `explicit_arrival_dates` |
| D20 mixed issues | Claim lost in billing | Stays in the points queue, flagged `multi_issue`, sent to a person | `conventional/signals.py`, `investigation.py` `_gate` |
| D21 corporate exception | Denies | Encoded in the published rules | `domain/eligibility.py` |
| D22 attached folios | Asks again | **Partial, deferred:** an explicit date in the text can find the stay; clean-folio OCR arrives with Milestone 8's extraction, before the benchmark | `investigation.py` `stay_by_date` |
| D23 other languages | Asks for English | Detects it and sends it to a person | `signals.py` `detect_language` |
| D24, D25 | Denies, or acts on the first record | Escalates, including a guest name that isn't the member's | `domain/eligibility.py`, `investigation.py` |
| D10, D11 | Platform, not arm B | The shared write path | `services/write_path.py` |

## Other differences a reader should know about

- **The name filter.** Mock API contract 1.1.0 adds `familyName`. Arm A's screens don't call it, and a test says so. A real platform
  may not offer one: then D13 and D18 fall back to asking (`docs/real-system-swap-guide.md`).
- **Intake routing.** Arm A sends any message with "refund" to billing (D20). Arm B does that only when the message has nothing
  about points.
- **Identity bar.** Arm A accepts an exact member number alone. Arm B wants two identifiers, so it asks more often on thin messages.
  That can cost arm B on a case arm A happens to get right, and it's reported, not tuned away.
- **Interface gains aren't AI gains.** Arm C is arm B plus the AI layer, so anything above comes with arm C too and isn't credited to AI.
- **Fallback.** With no model at all, arm B still works. That's the manual fallback the spec asks for.

## What arm C adds, and what it can't decide

Arm C is arm B plus a model. Arm B's investigation runs first, always. **The model can't decide:** the action must equal the engine's, and it has no field for an amount. Everything above comes with arm C too, and isn't credited to AI.

| Defect | Arm B | Arm C adds | Limit |
|---|---|---|---|
| D16 several stays | Explicit numbers; asks about the rest | Works out vague ones, from this member's own stays | Only stays the tools returned; several fits means ask |
| D19 mixed dates | Asks | Resolves a date when one stay fits | Never guesses between two |
| D20 mixed issues | Sends the whole message to a person | Carries on with points; notes the rest for a person | The engine and a supervisor still decide |
| D22 attached evidence | Text-layer PDFs and emails | Reads photos through vision | A number counts only if it's this member's stay |
| D23 other languages | Sends it to a person | Reads it and drafts in that language | Staff review and send the draft |
| Any case | The engine's reasons | A plain explanation with checked citations, and a draft reply | Labelled AI-written, after the evidence |

**Other differences:** arm C always costs at least what arm B costs, plus model calls. If the model is off or fails, the case holds arm B's result, flagged `ai_fallback`. **D18 isn't in this table:** it moved to arm B (ADR-0067).
