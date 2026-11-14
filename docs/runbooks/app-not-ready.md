# App not ready

**Alert:** `loyalty-app-silent`: nothing from the app (`loyalty_app_up`) for 5 minutes, while the worker still reports.
**Proposed owner:** application team (L2). Synthetic data only.

**You notice:** the alert; the console doesn't load; `/readyz` answers 503 or nothing.

1. `curl http://127.0.0.1:8010/readyz`. It names what isn't ready:
   - `database: unreachable`: `docker compose ps db`, then `docker compose logs --tail 50 db`.
   - `database: not_migrated`: the code is newer than the schema. Run the migrate service:
     `docker compose run --rm migrate`.
   - `customer_systems: unreachable`: the mock API (or the real system) is down: `docker compose ps mock-api`.
2. The app container is restarting: `docker compose logs --tail 100 app`. A startup error appears as a JSON line with
   an `exception` field (scrubbed).
3. After a release, roll the image back (`docs/rollback.md`). Only the migrations marked safe in that document roll
   back.

**Check it worked:** `/readyz` answers `{"status": "ready", …}`, the console signs in, and the alert clears.
