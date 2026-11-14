# AI quality drift

**Signal:** `python -m app.services.drift --baseline <window> --current <window>` exits 1 and lists the signals that
moved past their thresholds (ADR-0078). Run it weekly, for example as a scheduled job; it isn't a Grafana alert,
because the signals compare two windows of cases, not a live number. Online QA reviews with a rising share of `wrong`
or `misleading` answers point here too. **Proposed owner:** AI operations owner (L3). Synthetic data only; thresholds
are assumptions.

1. Read which signal moved, and by how much, in the report's `alerts`.
2. **Escalation or override rate up:** compare the case mix first (`category_mix_distance`). A new kind of request can
   raise escalations with nothing wrong in the AI. Then look at the overridden cases' QA reviews.
3. **Validation or citation failures up:** a policy changed (`policy_published` events) or the prompt or model
   changed. Check the AI runs' `prompt_version` and `model_id` against the baseline window.
4. **Tool errors up:** usually the customer system. See [error-rate.md](error-rate.md).
5. **Tokens per case up:** longer cases or more turns; costs follow ([ai-spend.md](ai-spend.md)).
6. If the AI's quality really fell: switch arm C off for new cases (`FEATURE_LIVE_AI=false`) while you investigate.
   Promote reviewed disagreements to the regression set only through label review (ENT-21), never automatically.

**Check it worked:** the next window's report has no alerts, and QA reviews return to their usual answers.
