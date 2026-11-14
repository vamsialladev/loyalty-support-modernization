# AI spend near its cap

**Alert:** `loyalty-ai-spend`: today's provider spend passed 80% of the daily cap (`loyalty_ai_spend` against
`loyalty_ai_cap`, both with `period="day"`). **Proposed owner:** AI operations owner (L3). In this project the model is
the mock (spend $0) unless the owner approves live calls; the alert is tested with planted spend.

**You notice:** the alert; `/metrics` shows "Model provider spend today" close to the cap.

1. The caps already stop spending: a run that would pass the per-run, daily or total cap stops with
   `budget_exhausted` (`app/ai/harness.py`, RFC-0002). The case stays open for a person; it costs no more.
2. More cases, or dearer cases? `/metrics` → AI runs, tokens and cost per case, per arm. Dearer cases mean more turns
   or more context; check the prompt version and model in the case's AI run.
3. If the cause isn't clear within an hour, stop live AI: set `FEATURE_LIVE_AI=false` and restart the worker. Arm C
   then shows the rules result for every case.
4. Raising a cap is the budget owner's decision, recorded in `CLAUDE.md` in this project. Never raise it to clear an
   alert.

**Check it worked:** spend stops rising or the day rolls over; budget stops appear as `ai_budget_exhausted` security
events, not errors.
