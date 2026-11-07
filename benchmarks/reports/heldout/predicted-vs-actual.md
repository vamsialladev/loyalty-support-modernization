# Predicted against actual, per defect (F8)

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed yet.

Predictions from `docs/legacy-defect-catalog.md`, written before any arm existed. Measured on held-out case success; arm C by majority of runs.

## Where arm A's failures went (`docs/day-one-discovery.md` predicted about 61% B, 21% C only, 9% split)

| Of arm A's failed held-out cases | Count | Share | Re-weighted to the history |
|---|---|---|---|
| Fixed by B | 33 | 84.6% | 89.5% |
| Fixed only by C | 4 | 10.3% | 9.8% |
| Fixed by neither | 2 | 5.1% | 0.7% |

## Where the catalog was wrong about arm A, and why

- **D04 and D08:** arm A says "wait" (first action wrong, as predicted), the simulated member comes back when told, and it's credited. Right in the end, one contact and some days later. The catalog didn't allow for the return.
- **D13:** these held-out messages carry a number or an exact name, so exact search finds the member.
- **D20:** these held-out complaints are about noise, so nothing routes them to billing. Arm A credits the points and ignores the complaint. Case success doesn't check that.
- **D06:** 1 of 3 over-credits. The other two are Mountain Lodge stays, where D08's stale wait masks it by accident.

## Per defect

| Defect | What | A predicted | A actual | B predicted | B actual | C predicted | C actual |
|---|---|---|---|---|---|---|---|
| D01 | Duplicate member profiles [+ UI] | Wrong (not found) | 0/2, first action 0/2: yes | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D04 | UTC timestamps read as local dates [+ config] | Wrong on boundary days | 2/2, first action 0/2: **no: it got them all right** | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D03 | Missing booking channel [+ data] | Wrong (denies) | 0/3, first action 0/3: yes | Fixes, or asks when underivable | 3/3: yes | Fixes, or asks | 3/3: yes |
| D08 | Old 30-day wait still set at Mountain Lodge | Wrong (says wait) | 2/2, first action 0/2: **no: it got them all right** | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D09 | New OTA rule missing from legacy rules and index | Wrong (denies) | 0/2, first action 0/2: yes | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D21 | Corporate exception buried in policy text | Wrong (denies) | 0/2, first action 0/2: yes | Fixes (rule encoded) | 2/2: yes | Fixes (adds a cited explanation) | 2/2: yes |
| D02 | Stays on a merged member number | Wrong (not found) | 0/2, first action 0/2: yes | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D05 | OTA confirmation format not searchable | Wrong (not found) | 0/2, first action 0/2: yes | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D06 | Late postings, visible only in the posting feed [+ UI] | Wrong (over-credits) | 2/3, first action 0/3: yes | Fixes | 3/3: yes | Fixes | 3/3: yes |
| D07 | Reversed and re-posted transactions | Wrong (over-credits) | 0/2, first action 0/2: yes | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D12 | Search misses synonyms | Slower, wrong citation | 3/3, first action 3/3: read the note | Fixes most | 3/3: yes | Fixes (incl. long tail) | 3/3: yes |
| D13 | Member lookup needs an exact match | Wrong (not found) | 3/3, first action 3/3: **no: it got them all right** | Fixes | 3/3: yes | Fixes | 3/3: yes |
| D14 | Evidence spread across four screens | More steps (accuracy unaffected) | 0/0, first action 0/0: not in held-out | Fewer steps | 0/0: not in held-out | Fewer steps | 0/0: not in held-out |
| D15 | No policy version by stay date [+ config] | Wrong (credits early) | 0/2, first action 0/2: yes | Fixes | 2/2: yes | Fixes | 2/2: yes |
| D17 | Wrong or partial confirmation numbers | Wrong (not found) | 0/3, first action 0/3: yes | Fixes | 3/3: yes | Fixes | 3/3: yes |
| D10 | No duplicate check across cases [process control, enforced by the write path] | Prevented by the shared write path. **A as-is: occurs** (measured, §2b) | 2/2, first action 2/2: read the note | Same as A | 2/2: read the note | Same as A | 2/2: read the note |
| D11 | No approval binding [process control, enforced by the write path] | Prevented by the shared write path. **A as-is: occurs** (measured, §2b) | 0/2, first action 2/2: read the note | Same as A | 0/2: read the note | Same as A | 0/2: read the note |
| D16 | Several stays in one message | Wrong (handles one) | 0/3, first action 3/3: yes | Partial (explicit numbers only; asks about the rest) | 3/3: read the note | Fixes | 3/3: yes |
| D18 | Nicknames and name formats [+ UI] | Wrong (not found) | 1/2, first action 1/2: yes | Partial (listed nicknames) | 2/2: read the note | Fixes | 2/2: yes |
| D19 | Dates in mixed formats | Wrong | 2/3, first action 1/3: yes | Asks | 2/3: read the note | Fixes when the member's stays make it unique; asks otherwise | 3/3: yes |
| D20 | Points claim mixed with a complaint [+ process] | Wrong (claim lost in the billing queue) | 3/3, first action 3/3: **no: it got them all right** | Sends whole message to a person (delayed) | 0/3: read the note | Fixes (handles points, routes the rest) | 3/3: yes |
| D22 | Evidence only in an attached folio or receipt [+ UI] | Wrong (asks again) | 1/3, first action 0/3: yes | Partial (clean folios via OCR) | 3/3: read the note | Fixes (noisy photos too) | 3/3: yes |
| D23 | Non-English requests | Wrong (asks for English) | 0/3, first action 0/3: yes | Routes to a person | 0/3: read the note | Fixes | 3/3: yes |
| D24 | Stay record genuinely missing upstream | Wrong (denies) | 0/3, first action 0/3: yes | Escalates (correct) | 3/3: yes | Escalates (correct) | 3/3: yes |
| D25 | Conflicting records | Wrong (acts on the first record) | 0/3, first action 0/3: yes | Escalates (correct) | 3/3: yes | Escalates (correct) | 3/3: yes |

Every number comes from a stored run in `benchmarks/results/`. Simulated member and supervisor.
