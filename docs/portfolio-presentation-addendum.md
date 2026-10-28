# Portfolio presentation addendum (match vamsialla.com house style)

> Supplied by the owner on 2026-10-28 with the Stage 9 kickoff. Saved verbatim. Followed from Milestone 1 onward
> and fully in Milestone 19. Each item is tracked in `docs/requirements-matrix.md` (Tier 4, IDs `PA-01` to
> `PA-10`). The exact site conventions it refers to are recorded in `docs/continuity.md`.

1. Stage card, same structure as existing stages: a real output example at the top; exactly three headline metrics with count/denominator, runs, held-out result, and date + version; badge "Live" only with a verified live link, otherwise "Built"; links: "<App> (live) →" (only when deployed and verified, with the wake note if on free hosting), Watch the demo, Case study, GitHub; the label "Independent project · simulated hotel group, synthetic data". One metric must be the A vs B vs C final-ledger result, one a safety result, one cost per 1,000 cases.

2. Case study: same sections as the current case studies (real output, problem, approach, architecture diagram, results with dates/denominators, demo video, live link or "not hosted", trade-offs, limitations, what's next). Lead with the problem and the measured outcome; include where AI did not help.

3. Site integration (prepare as website PRs, never merge or publish without my OK): Stage 9 entry in the stage list and "How I work" table, OG image and alt text matching the card numbers, projects.json and the no-JavaScript card copies kept in sync.

4. Demo video: recorded with Playwright from the real running app, using the same video-kit approach as the other stages: narration in plain, first-person style, captions and transcript, real duration in the heading, "Narrated with a generated voice; captions included." Run the audio audit. Open it in my player and wait for my OK before it goes into any PR.

5. README consistent with my existing repos: label, CI badge, the three metrics with dates, real output, demo link to the case-study player, quickstart (Windows PowerShell and macOS/Linux), Mermaid architecture, what AI does and doesn't control, A/B/C results table, how to reproduce, security summary, limitations, links to the other stages.

6. Notes post: draft one honest note in my existing notes style (for example, what the legacy benchmark revealed, or where AI lost to the non-AI fix). Draft only.

7. Visibility drafts (never post): a short LinkedIn post and two or three résumé bullets, using only this stage's verified numbers, labelled as a simulated project. Never reuse employer metrics.

8. Writing tone everywhere: plain English, specific numbers, honest about limits. Every number shown must trace to a stored result file.

9. Secrets: never ask me to paste secrets in chat or show them in output; use .env and dashboard secrets only (Appendix K). After any credential rotation, prove the old credential fails.

10. Lessons from the stages PS–8 cleanup (apply them from the start):
   - Video narration: every claim in the narration must match a stored report (no "every time" when the report says 5 of 6). Record when the demo data looks natural (for example, upcoming rather than "finished" items), and check rendering issues such as dollar signs or special characters before recording. Keep the script ready so I can later re-record the narration in my own voice; when I do, remove the generated-voice label.
   - Latency: label each latency figure with what it measures (model + tools time vs. in-browser time on the live app), and report both.
   - Live links: deploy only from main, never from an unmerged branch. Verify every live link and the live app's real behavior before adding "(live) →". Keep README "Try it live" lines in sync with the actual deployment.
   - Site consistency: when any number changes, update the card, case study, OG image and alt text, README and résumé line in the same change set. Verify the live site with cache-busting.
   - Spending caps: daily and monthly caps must persist across app restarts (stored in the database), and be tested before public deployment.
   - Secrets in hosting dashboards: give me the secrets block in valid TOML with every value quoted, and tell me how to confirm the app actually receives them (for example, a config-loaded line showing set/missing).
