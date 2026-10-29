# Owner exercises (spec Part K, tracked separately from assistant-built work)

Generated code never counts as the owner's demonstrated understanding. This log records the owner's own answers to
the end-of-milestone exercises (K.1) and, later, the K.2 exercises and the K.3 assessment. Requirement PERS-01.

| Milestone | Exercise | Owner's answer (summary) | Assessment |
|---|---|---|---|
| 1 | With `AI_PROVIDER=anthropic` and no key, why does preflight say NOT READY instead of falling back to mock? | A silent fallback would make mock answers look like live results and break the "never describe mock as live" rule. Failing loudly with the exact missing settings lets the operator fix the configuration, and nobody is misled about which model produced an answer. (2026-10-28) | Correct and complete: names both the honesty rule (spec B.2, E.5) and the operational benefit |
| 2 | Why is D21 (corporate exception buried in policy text) predicted to be fixed by B, not C? | The exception is a fixed, findable rule (`CORP*` rate codes on travel-agent bookings); once it's in the rules engine and indexed, a deterministic check handles it every time. AI helps where the input is messy or unpredictable, not where a stable rule is badly documented. (2026-10-28) | Correct: states the core principle that stable rules belong in the rules engine |

## K.2 exercises (planned; see spec Part K.2)
None completed yet. They start once the product exists (Milestones 6 onward).
