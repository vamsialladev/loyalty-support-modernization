# Policy retrieval: approach and limits

> POL-08. SYNTHETIC policies. Code: `app/services/policies.py`, `app/services/policy_publishing.py`; decision: ADR-0057.

## How it works
- **Source:** one Markdown file per policy version in `policies/<customer>/`, with front matter (ID, version, effective
  dates, status, section list, rule values). `app.seed` loads the committed set once. New versions go through the
  Configuration page as drafts.
- **Which version:** the one in force on the stay's **checkout date in the property's time zone**. Search looks only at
  those versions. A draft is never selected, cited or searched.
- **Chunking:** one chunk per `##` section, stored with its heading and exact text. A section is the unit of citation.
- **Search:** Postgres full-text search with English stemming over heading and text, through a GIN expression index.
  Query text goes through `websearch_to_tsquery` as a bound parameter, so it can't break the query.
- **Citations:** `policy@vN#section` opens `/policies/<policy>/v<N>/<section>`, the exact stored excerpt and version. Each
  citation carries the source checksum and the time it was read.
- **Publishing:** draft, then checks (rule fields, next version number, no gap or overlap in dates, golden outcomes),
  then published, with the previous version superseded. A stored version never changes: a changed file is refused.

## Limits, stated plainly
- **Every search word must match, after stemming.** "didn't get my points" needs the words "get" and "point" in one
  section, so paraphrases can find nothing. Synonyms are arm B's work (Milestone 7, D12). Embeddings need a controlled
  comparison first (spec 0.6).
- **English only.** Non-English queries find little (D23).
- **Search is not eligibility.** Rule values come from the front matter, not from retrieved text. A wrong or missing
  search result can't change what a stay is owed; it can only change what is cited.
- **The golden cases are hand-written** and cover 14 dated outcomes, not every combination. They guard against changing
  what an earlier date means; they don't prove a new policy is sensible.
- **Front matter and prose can disagree.** Nothing checks that the rule values match the sentences. A person must review
  a draft; one administrator can publish (ADR-0055, tech debt register).
- **Offline tests use SQLite, where a small word match stands in for search.** Only `tests/test_policy_postgres.py`
  proves the real search. Selection by date and excerpts are the same code on both.
- **Policy text is treated as sensitive once derived data exists.** There are no embeddings or caches of it today.
