# Error rate high

**Alert:** `loyalty-error-rate`: more than 5% of the app's requests answered 5xx over 10 minutes, with at least 20
requests (`http_server_duration_milliseconds_count`, by `http_status_code`). **Proposed owner:** application team (L2). Synthetic data
only.

**You notice:** the alert; staff see "Something went wrong on our side. The reference is …".

1. Take a reference from a staff report, or find recent errors: `docker compose logs --tail 200 app`, looking for
   `"level": "ERROR"` lines. The reference is the `correlation_id`; the same line has the `trace_id`.
2. Open the trace: Grafana → Explore → Tempo → paste the `trace_id`. The red span shows where it failed: the app, a
   database statement, a call to the customer system, or a model call.
3. **Customer system failing** (502s, `CustomerSystemError`): staff can keep working; investigations retry with
   backoff. Tell the customer's system owner.
4. **Database** (`OperationalError` spans): see [app-not-ready.md](app-not-ready.md).
5. **A new release**: compare the error's first time with the deployment; roll back the image (`docs/rollback.md`).

**Check it worked:** the 5xx share falls under 1%, and the alert clears.
