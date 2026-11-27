# Wake page for vamsialla.com (LIVE-06)

The live demo sleeps when nobody uses it. Its first page takes about 10 seconds after a quiet spell, longer on the
first visit of the day, when the daily reset runs (verification log, Milestone 12, row 47). This page shows
"Starting the live demo (~10 s)…" during that wait. It asks the demo for `/login` and opens it when it answers.

| File | Goes to (on vamsialla.com) | What it is |
|---|---|---|
| `loyalty-demo.html` | `/loyalty-demo.html` | The page. Its head, header, footer, theme check and GoatCounter check are copied byte for byte from the site's `now.html`, so the two inline-script hashes in its CSP are the site's own |
| `assets/demo-wake.js` | `/assets/demo-wake.js` | The waiting logic. No inline script, so the CSP needs no new hash |

## Install (the owner's step; nothing here publishes anything)
1. Copy both files into `vamsi-portfolio` at the paths above.
2. **CSP:** this page's `connect-src` adds `https://loyalty-demo-1023835827965.us-east5.run.app`. The site's rule
   says a new connection goes into the CSP on every page, so add it to the other pages too, or keep it on this page
   only and record why. It's only needed here.
3. Point the Stage 9 "(live)" link at `/loyalty-demo.html` instead of the `run.app` address.
4. Run the site's own checks before pushing: `python scripts/site_sync.py --check` (passes with this page added,
   checked 2026-11-27 on a copy of the site), html-validate, lychee and Lighthouse.

## What it can't do
- **It can't tell "awake" from "paused".** The request is `no-cors`, so the browser hides the demo's reply from
  vamsialla.com. Any answer counts as awake, including Google's page when the monthly spending cap has paused the
  demo. The page says so in plain words.
- **It never polls `/healthz`.** Cloud Run reserves some paths ending in `z` and answers them itself, without waking
  the instance (verification log, M12 row 43).
- After 2 minutes it shows a "may be paused" note. After 5 minutes it stops trying. The link works throughout.

Tests: `tests/test_demo_wake_page.py` covers the static rules, and two browser tests fake a sleeping demo.
