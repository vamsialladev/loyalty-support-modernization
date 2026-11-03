# Vendored front-end files

Served from the app itself, so the console needs no CDN at runtime and its Content-Security-Policy stays
`script-src 'self'` (ADR-0045, ADR-0049).

| File | Source | Version | SHA-256 | License |
|---|---|---|---|---|
| `htmx-2.0.11.min.js` | npm package `htmx.org`, file `dist/htmx.min.js` | 2.0.11 (published 2026-09-22) | `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717` | Zero-Clause BSD (`htmx-LICENSE.txt`) |

How it was fetched (2026-10-29): the tarball `https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.11.tgz` was
downloaded, its SHA-512 matched the registry's published `dist.integrity`, and `package/dist/htmx.min.js` was
extracted unchanged. `tests/test_arm_a_boundaries.py` checks the hash above. To upgrade, repeat those steps for the
new version and update this table and the test.
