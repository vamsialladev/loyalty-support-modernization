# Break-glass: emergency administrator access (ENT-26)

Code: `app/services/break_glass.py`. Tests: `tests/test_break_glass.py`. Decision: ADR-0093. Owner's rules, 2026-11-27.

## When to use it
Only when configuration must change now, the usual administrator can't be reached, and waiting would cause harm.
For example: the kill switch is stuck on during an incident, or a bad policy must be withdrawn. It is never a way to
skip an approval. Administrators don't work cases, so a grant can't approve, execute or post an adjustment.

## The rules
| Rule | What the code does |
|---|---|
| At most 60 minutes | `--minutes` is 1 to 60 (default 30), and anything else is refused |
| A reason | At least 15 characters. It's kept on the grant and in the audit row, and never exported to the SIEM |
| Two people | The grantor is a different, active supervisor or administrator of the same customer. No one can grant to themselves |
| No hand-on | Someone under an open grant can't grant or revoke one |
| No renewal | There's no "extend". A second grant while one is open is refused, even from another grantor. Only a new grant, after the first ends, gives more time, and it gets a new number |
| Who can be raised | An active agent or supervisor. An auditor stays independent, an administrator needs none, and a `svc-`, `system-` or `scripted-` account is never raised |
| Off in the public demo | The command refuses with `PUBLIC_DEMO_MODE=true`, and the console ignores grants there |
| Ends on its own | The raise is checked on every request. At the expiry minute the person is back to their own role, and the expiry is recorded |
| Audited and alerted | Granted (severity 4), refused (3), revoked (3) and expired (2) are security events. Everything done under a grant carries `break_glass_grant` in its audit row |

## How
Run on a machine that can reach the database, with `DATABASE_URL` set, never from the console:

```powershell
uv run python -m app.services.break_glass grant --user ana --by sam --minutes 30 --reason "INC-12: kill switch stuck on"
```
```powershell
uv run python -m app.services.break_glass revoke --grant 7 --by sam --reason "INC-12 resolved, access ended"
```
```powershell
uv run python -m app.services.break_glass list
```

`list` first closes and records any grant past its time, then shows the open ones. A refusal prints its code and
exits with 2.

## Afterwards (within one working day)
1. Export the security events for the window (`python -m app.services.security_events --since <date>`).
2. List everything that carries the grant's number in `break_glass_grant`.
3. Write it up in the incident report (`docs/drills.md`, then the incident guide), with the reason and who granted
   it.
4. If the grant was misused, treat it as a security incident: revoke the person's sessions, and rotate
   `APP_SECRET_KEY` if needed (`docs/credential-rotation.md`).

## Limits
- **An expiry is recorded when it's seen:** on the person's next request, or by `list`. If neither happens, the grant
  row still holds its expiry time, and the raise has ended anyway, because every request checks it.
- **The grantor is named, not proven.** The command runs where someone already has database access, so a
  real deployment would put it behind its own sign-in (SSO plus a second approver). That's the real-system swap.
- **Not drilled yet.** The Milestone 13b drills (`docs/drills.md`) will exercise it on the throwaway stack once the
  machine is free.
