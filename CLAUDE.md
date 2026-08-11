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

## Layout
- `pipeline/search.py` — finds and validates postings, uses `jobsearch/skill/search_skill.md`
- `pipeline/jobtech.py` — second source: Arbetsförmedlingen's open JobSearch API
- `pipeline/updater.py` — writes `jobsearch/joblist.md`
- `pipeline/mailer.py` — daily digest from `results.json`
- `app/app.py` — Flask UI on port 5003, generates CV + cover letter, uses `generation_skill.md` then `review_skill.md` as a second pass
- `jobsearch/cv/master_cv.md` — single source of truth for work history and projects

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
