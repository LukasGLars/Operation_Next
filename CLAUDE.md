# Operation Next — repo notes

Read `MEMORY.md` first. It carries the current state, decisions and gotchas.

## Layout
- `pipeline/search.py` — finds and validates postings, uses `jobsearch/skill/search_skill.md`
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
