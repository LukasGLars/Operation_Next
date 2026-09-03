# Operation Next — repo notes

Read `MEMORY.md` first. It carries the current state, decisions and gotchas.

## Git workflow (overrides the global branch+PR rule)

Solo repo, no other reviewers — PRs here get merged in the same sitting they're
opened, so the branch+PR step buys a diff to glance at, not real review.

- Small/safe code changes (bug fixes, docs, config) — push straight to `main`.
- Riskier changes (auth, credentials, anything that mutates data destructively,
  changes to the location gate or exclude rules' logic) — still branch + PR,
  so there's a reviewable diff before it's live.
- `jobsearch/` content (joblist rows, application docs, skill files) already
  goes straight to `main` — matches the app's own auto-commit behavior, see
  Gotchas below.
- Standing merge authorization (2026-08-14): merge clean PRs by default once
  opened, no need to wait for an explicit "merge it" each time.

## Layout
- `pipeline/search.py` — finds and validates postings, uses `jobsearch/skill/search_skill.md`
- `pipeline/jobtech.py` — second source: Arbetsförmedlingen's open JobSearch API
- `pipeline/updater.py` — writes `jobsearch/joblist.md`
- `pipeline/mailer.py` — daily digest from `results.json`
- `app/app.py` — Flask UI on port 5003, generates CV + cover letter, uses `generation_skill.md` then `review_skill.md` as a second pass
- `jobsearch/cv/master_cv.md` — single source of truth for work history and projects
- `jobsearch/rejected.md` — URLs manually deleted from the joblist; `pipeline/updater.py`
  checks this before re-adding a posting so a rejected job can't resurface

## Tests
`python -m pytest tests/` — run before claiming anything is done.

## Location rules
- Fully remote passes from anywhere. Hybrid passes only when the office itself is
  within a 40 minute commute of Alingsås — a Stockholm hybrid still means two or
  three days a week in Stockholm.
- `COMMUTABLE_PLACES` in `pipeline/search.py` is the knob. Widen or narrow that
  set rather than reworking `location_verdict()`.
- Never infer the work model from prose alone: "hybrid cloud" and "remote
  sensing" are false positives. Read the ATS remote-status field
  (`<dt>Remote status</dt><dd>Hybrid</dd>`), which `fetch_page_text` appends as a
  `Remote status:` line.
- Keep `search_skill.md`'s Location Rules in sync with the code. The skill text
  steers the search model; the code is what actually enforces.

## Relevance rules
`pipeline/relevance.py` is the gate; it runs as stage 1.6 in `search.py`, after
location and before the batched Claude validation, so an unwinnable role costs
nothing to reject. `updater.recheck_dead_ads()` applies the dead-ad half to rows
already in the list.

- **Match on the title or an explicit number, never a bare body keyword.**
  Measured against the live joblist, body-keyword matching had a 46%
  false-positive rate: "du har *gärna* erfarenhet av inköp" and "minst *fem* års
  erfarenhet av projektinköp" share the same words and only the second one
  disqualifies. `_soft_wish` voids any match inside a *gärna* / *meriterande* /
  *ett plus* / *fördel om* sentence — that check alone flipped 6 of 13 verdicts.
- **Swedish ads spell numbers out.** "minst fem års erfarenhet" is at least as
  common as "minst 5 år". A digits-only pattern silently missed every one.
- **A year range reports its floor, not its ceiling.** "3–7 års" will accept 3,
  so it is not a 4+ gate.
- **Seniority is only a gate in procurement.** The candidate converts in
  technical sales at any stated level — all four Intervju rows are teknisk
  säljare or affärsutvecklare — so a "Senior Sales Engineer" must pass.
- **registerkontroll and belastningsregister are NOT security clearance.** They
  are background checks on whoever is hired. Every Göteborgs Kommun ad carries
  one; treating them as gates dropped four applicable roles. Only
  säkerhetsprövning / säkerhetsskyddslagen / svenskt medborgarskap count.
- **Högskoleingenjör passes, civilingenjör/MSc does not.**
- Keep `search_skill.md`'s Relevance gate section in sync with the code, same as
  the Location Rules.

## Job sources
Two, merged into one candidate list before the shared validation stages:
- **Claude web search** — ATS-hosted ads. Queries live in `QUERIES_PASS1/2/3`.
  `max_uses` on the tool must cover the query count, or the tail of every pass
  silently never runs.
- **JobTech / Platsbanken** (`pipeline/jobtech.py`) — most of the Swedish market.
  Always quote role queries: unquoted `product specialist` matches "HR-specialist"
  and "Legitimerad Läkare" (271 hits vs 2). A role must be named in the headline
  or the taxonomy occupation, not merely mentioned in the ad text.

JobTech candidates carry `_source: "jobtech"` and a prebuilt `_page_text`, so they
skip `_url_looks_specific` (their job id often sits in a query parameter) but are
still checked for careers-hub URLs and reachability. Keys prefixed `_` are
stripped before `results.json` is written.

## Gotchas
- The app auto-commits and pushes `jobsearch/` on use. Commits titled
  "App: update jobsearch/" are the app's, not yours.
- This repo moves in sessions you were not part of. `git fetch` and diff against
  origin before editing `app.py` — local checkouts have been a full generation of
  work behind.
- The repo is public. Secrets belong in `.env` only.
- `fetch_page_text` returns JSON-LD when present, which drops page chrome. Some
  ATS pages carry the location or work model only in that chrome — hence the
  `visible_page_text` fallback in the location gate.
- Rejection is matched on `canonical_url()` (apply-form suffix and
  promotion/utm tags stripped) **and** on company+role, because aplitrak's
  `adid` is opaque and differs on every sighting of the same job. Both copies of
  `canonical_url` — `app/app.py` and `pipeline/updater.py` — must agree;
  `tests/test_canonical_url.py` asserts it.
- `Avslag` is a terminal status: the row stays visible but is written to
  `rejected.md` at once, and `recheck_dead_ads`/`close_expired` skip it
  (`CLOSED_STATUSES`) so the outcome isn't overwritten with `Stängd`.
- The 30-day prune appends what it drops to `rejected.md`. Without that the URL
  left `known_urls` and the next pass re-added the posting as Identifierad.
- `update_joblist()` returns early when a pass found nothing, so the prune, the
  deadline check and the dead-ad recheck only run on a pass with results.
- Platsbanken publishes the Teamtailor *apply form* URL
  (`/jobs/<slug>/applications/new?promotion=...`), not the ad. That page has the
  cookie banner and the form fields, no ad text, so anything generated from it is
  written off the job title alone. `app.py:_ad_page_url` trims it back to
  `/jobs/<slug>` before fetching. `pipeline/search.py:fetch_page_text` does not
  yet do this — the relevance gate still reads such rows off the form page.
