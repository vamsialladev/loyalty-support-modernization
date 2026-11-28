# AI incident register (ENT-20)

Every time the AI, or the measurement of it, went wrong or nearly did: what happened, the harm or near harm, how it
was found, which controls held or failed, the fix and the test that holds it, and its status. Entries are real:
from drills (marked **drill**), from evaluation and benchmark runs, and from live use if there ever is any. Nothing
here is invented. This is a simulated engagement with synthetic data and mock AI by default, so no real member was
ever affected.

Severity: **1** a real member or real money affected; **2** a wrong result reached a person, who had to catch it;
**3** a wrong result was caught by code before anyone saw it; **4** a measurement or reporting error.

| ID | Date | Source | What happened | Severity | Found by | Controls that held / failed | Fix and the test that holds it | Status |
|---|---|---|---|---|---|---|---|---|
| AI-INC-001 | 2026-11-28 | **drill** D6 (run 46100411460) | The model, made to fail on purpose (`MOCK_MODEL_FAULT=wrong_action`), recommended the opposite action twice. It said "no adjustment" on DV-001, which is owed 14,840 points, and "adjust" on DV-002, which is owed nothing | 3 | The proposal check (`app/ai/validation.py`: `action_mismatch`) | **Held:** the validation flagged both, the run fell back (`invalid_result`), and the engine's result stood. A request takes the engine's amount (14,840) and is refused where nothing is owed (409). **Didn't apply:** a proposal has no amount field, so it couldn't name a wrong amount | None needed. Held by `scripts/drill.py d6` in `.github/workflows/drills.yml`, and by the validation's unit tests | Closed (drill) |
