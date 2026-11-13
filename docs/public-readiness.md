# Public-readiness check

> Prepared on 2026-11-13 for the owner's decision whether to make this repository public. **The repository is still
> private; making it public is the owner's decision.** Every result below comes from a command run that day; the
> commands are in `docs/verification-log.md`, Milestone 12.

## Result

**No blocker found.** Five things for the owner to know or decide first, under "Decide before flipping".

| Check | How | Result |
|---|---|---|
| Secrets in the full history | gitleaks v8.30.1 over every commit, all branches (`scripts\ci_local.ps1`, job `secrets`) | No leaks found (104 non-merge commits; the 45 merges add one line of their own, checked by hand) |
| Every remote branch is in that scan | `git ls-remote` tips checked against the local clone | 21 branches, 0 tags; 0 missing |
| Private key files or blocks, ever | file names (`.pem`, `.key`, `id_rsa`, `.p12`, `.pfx`) added in any commit; `BEGIN … PRIVATE KEY` in any revision | none; 0 revisions |
| `.env` files, ever | any `.env*` file added in any commit | only `.env.example`; `.env`, `.env.*` are Git-ignored (`.env.bak` too) |
| Key-shaped strings | Anthropic, AWS, GitHub and Slack key patterns in tracked files | 4, all obvious fakes in tests (`sk-ant-fake-…`, `…thisShouldNeverLeave`, …); the one gitleaks exception is pinned by fingerprint in `.gitleaksignore` |
| The owner's private email address | searched in every revision, in all 37 pull requests and their comments | 0 |
| Email addresses in tracked files | every address, grouped by domain | synthetic domains only (`mail.test`, `example.com`, `example.org`, `*.test`, `*.example`), plus the public portfolio address in `pyproject.toml` and `docs/tool-access-matrix.md` |
| Phone numbers | phone-shaped strings in tracked files | 7, all in the fictional 555-0100 to 555-0199 range |
| Work authorization, visa, home location | keyword search of every revision | 0 |
| Local machine paths (user folder) | tracked files | 0 |
| GitHub-side content | Actions secrets, variables, artifacts, issues | none, none, 0 artifacts, 0 issues |
| Synthetic data | `seed_data/v1/` (the generated world) is Git-ignored and regenerated; the benchmark cases and labels are committed by decision (ADR-0030) | as designed |

## Decide before flipping

1. **Commit author email.** 40 of 149 commits (2026-10-25 to 2026-11-03) carry the portfolio address
   `vamsialla.dev@gmail.com`; the rest use the GitHub noreply address. That address is already public (on
   vamsialla.com and in `pyproject.toml`), so this isn't a leak, but a public repository shows it on every one of
   those commits. Hiding it would mean rewriting history and force-pushing, which changes every cited commit hash.
   Recommendation: leave it.
2. **Held-out labels become visible.** All labels, held-out included, are committed (ADR-0030), kept out of every
   image and out of every arm's code path (tests enforce both). Once public, anyone (and any future model trained on
   public code) can see the held-out answers. The Milestone 10 results stand, because they were run and frozen
   before. Any later held-out claim needs a new split written after the flip. Recorded in `docs/known-limitations.md`.
3. **The sealed list for the Codex exercise** (`docs/exercises/codex-sealed-list.md`) is committed. The exercise
   points Codex at an earlier commit that doesn't contain it, so making the repository public doesn't change that; its
   SHA-256 is in the verification log.
4. **Actions logs become public.** Every past and future CI log is readable by anyone. They hold only throwaway
   values (`ci-only-throwaway`, a container-only database); no repository secret exists.
5. **After the flip** (from `docs/session-handoff.md`): turn on secret scanning and push protection, and keep the
   email-privacy setting "Block command line pushes that expose my email" on. Actions minutes on a public repository
   are free, so the minute limit in ADR-0076 could be relaxed then.

## The command, when the owner decides

```powershell
gh repo edit vamsialladev/loyalty-support-modernization --visibility public --accept-visibility-change-consequences
```
