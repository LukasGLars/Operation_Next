# Operation Next — Memory

## What this is
Automated job search and application pipeline. Finds roles, tracks them in joblist.md, generates tailored CV and cover letter via a Flask UI at localhost:5003.

## Current state (August 2026)

### Architecture
- `pipeline/search.py` — finds and validates new job postings, uses `search_skill.md`
- `app/app.py` — Flask UI on port 5003, generates CV + cover letter on demand, uses `generation_skill.md`
- `jobsearch/cv/master_cv.md` — single source of truth for all work history and projects (replaced 5 static PDF CV bases)
- `jobsearch/skill/generation_skill.md` — generation instructions, framing angles, approved reference examples
- `jobsearch/skill/search_skill.md` — search queries, role filters, location rules
- `jobsearch/skill/review_skill.md` — review prompt, runs automatically as a second pass in `/generate`
- `pipeline/jobtech.py` — second job source, Arbetsförmedlingen's open JobSearch API
- `jobsearch/sales_philosophy.md` — loaded into generation prompt for technical sales roles

### Generation prompt inputs (app.py)
1. generation_skill.md
2. master_cv.md
3. sales_philosophy.md
4. Einride cover letter .docx (tone reference)
5. Job posting (fetched live)

### Key decisions made
- **master_cv.md over PDF bases** — adding a new project = update one file, automatically available in next generation
- **SKILL.md split** — generation_skill.md for the app, search_skill.md for the pipeline. Keeps Claude context clean and focused
- **Einride as the only reference** — CheckWatt removed. Einride CV + cover letter are the benchmark for both English and Swedish output
- **Language follows job posting** — CV and cover letter both match the language of the posting (was incorrectly hardcoded to Swedish)
- **Primary target: Einride-like roles** — BA, analyst, AI/automation. BD roles (affärsutvecklare) as secondary with BHG rollout + MedTech as the lead, analytical work as differentiator

## Review pass — built, no button

Planned as a "Review" button the user would click after generation. It shipped as
an automatic second Claude call inside `POST /generate` (`app/app.py`), so there is
no button and no `/review` route. It re-reads the job posting, mirrors the ad's
register, and naturalises Swedish that otherwise reads like translated English.
Falls back to the unreviewed draft if the call fails.

It also receives the most recent human edits as draft/final pairs — see the
edit-feedback section below.

## Location filter (August 2026)

### What was wrong
Ads far outside commuting range were reaching the joblist — Umeå, Örnsköldsvik,
Borlänge, Södertälje, five Stockholm roles. 14 of 16 rows failed the location
rule. Three causes:
- The "40 minute commute from Alingsås" rule existed only as prose in the search
  prompt. An LLM cannot compute commute times, so it guessed.
- The search model returned a `location` field, but `updater.py` dropped it.
  joblist.md had no location column, so a Umeå ad looked like a Göteborg ad.
- `URL_VALIDATION_SKILL.md` (the second gate) has no location rules at all — it
  only checks that a location exists on the page, never that it is acceptable.

### What was built
- `location_verdict()` in `pipeline/search.py` — deterministic gate, runs as
  stage 1.5 between reachability and quality validation. Page text is fetched
  once there and reused by `batch_validate_urls`.
- `COMMUTABLE_PLACES` — the tunable knob. Municipalities within ~40 min of
  Alingsås. Widen or narrow this set rather than touching the logic.
- `_remote_status()` — reads Teamtailor's `<dt>Remote status</dt><dd>Hybrid</dd>`
  definition list. This is the reliable work-model signal; prose matching on
  "hybrid" alone gives false positives ("hybrid cloud", "remote sensing").
- `Plats` column in joblist.md, written by `updater.py` and `app.py`, rendered in
  `templates/index.html`.
- `tests/` — first test suite in the repo (pytest, 16 tests). Run with
  `python -m pytest tests/`.

### Decision: hybrid needs a local office
Fully remote passes from anywhere. Hybrid passes only when the office itself is
within range — a Stockholm hybrid still means two or three days a week in
Stockholm. Chosen deliberately over the looser "any hybrid tag passes" reading,
which would have kept an Örnsköldsvik and a Knivsta role.

Fallback path worth knowing: when JSON-LD carries no city, the gate re-checks
against the full visible page text (`visible_page_text`), because some ATS pages
tag hybrid/remote in page chrome that `fetch_page_text` discards. Without this,
valid Göteborg roles (both Novacura ads) were silently dropped.

### Gotchas
- Securitas "Business Analyst (Client Engagement)" was a **Warsaw, Poland** role
  all along — generated documents exist for it. The old pipeline surfaced it
  because nothing checked location.
- 11 rows were removed from joblist.md, two of them `Genererat`
  (Rekryteringsgruppen Stockholm, Securitas Warsaw). Their generated documents in
  `jobsearch/applications/` were left untouched, and the rows are recoverable
  from git history.
- `page_location()` must use `[ \t]*`, not `\s*`. With `\s*` a blank
  `Location:` line swallowed the newline and captured `Description:` as the city.

## Second job source — JobTech / Platsbanken (August 2026)

### Why
After the location filter the joblist was down to 5 roles, three of them
borderline. The web search alone only reaches what it can find on ATS platforms.

### What was built
`pipeline/jobtech.py` — Arbetsförmedlingen's open JobSearch API
(`jobsearch.api.jobtechdev.se`, no auth). Candidates are shaped exactly like the
search model's output and merged into the same dedup → reachability → location →
validation stages. A live dry run returned 30 in-range, on-topic roles in
Göteborg, Alingsås, Mölndal and Borås, against 5 rows in the whole joblist.

Filtering happens in this order, cheapest first:
1. Quoted role queries, server-side municipality filter (concept ids in
   `COMMUTABLE_MUNICIPALITY_IDS`), newest first.
2. Deterministic relevance — headline or taxonomy occupation must name the role;
   headline/employer exclude rules for support, phone sales, internships and the
   management consultancies.
3. The location gate, injected as `location_ok` so jobtech does not import
   search.py. It runs *before* the cap, otherwise the nationwide remote pass
   fills the cap with Stockholm ads.
4. One batched Claude call (`judge_fit`) for the exclude rules that need reading.

### Gotchas found the hard way
- Unquoted free text is useless: `product specialist` returns 271 hits including
  "HR-specialist" and "Legitimerad Läkare"; `"product specialist"` returns 2.
- Platsbanken's own ad pages are client-side rendered — fetching one returns a
  cookie notice, ~379 characters. Never use `webpage_url` as the joblist URL; use
  the employer apply URL, normalised to the posting page where the ATS path
  carries the id. Query-string ids (recman, ponty) must be kept intact.
- `remote_work` in the API does not distinguish hybrid from fully remote, so no
  remote status is synthesised — the ad text is passed through and
  `location_verdict` stays the only place that decides.
- Ads applied to via Arbetsförmedlingen (`via_af: true`) have no employer URL and
  are dropped; there would be nothing for document generation to read.
- Same role often appears twice under different ad ids, so candidates are
  deduplicated on (company, role) as well as URL.

### Also fixed here
`max_uses` on the web_search tool was hardcoded to 8 while the query lists held
12, 8 and 12 — roughly a third of every pass never ran and nothing logged it. Now
`len(queries) + 2`. Queries were also retuned to the region plus explicit remote,
since Sweden-wide on-site results are discarded by the location gate anyway.

## Notifications (August 2026)

`search.py` records a `run_errors` list and per-stage counts in `results.json`;
`mailer.py` mails only on new roles or errors. Closed ads are written to the
joblist as Stängd without a mail, and a clean run with nothing new stays silent.

Silence is only safe because a missing or stale `results.json` counts as an error
(so a pipeline that dies without crashing still mails) and a hard crash fails the
Actions job, which notifies separately. Keep both of those intact if this is
touched.

## Learning from human edits (August 2026)

`_recent_edited_examples()` in `app.py` pairs each generated draft with the
hand-edited final and feeds both to the review pass, labelled rejected/approved.
It read cover letters only until the Rekryteringsgruppen CV edits showed the CV
carries the heavier corrections: inflated job titles (Platschef → Arbetsledare),
legal entity names instead of brands, seven tool-listing competencies cut to four
stances, internal tech names in bullets, five bullets cut to three, and em-dashes
replaced with commas throughout. Those rules now also live in
`generation_skill.md` so the first draft aims for them.

Newest edit per document only. Two pulled in the May CheckWatt edits, which were
retired as a reference on purpose, and doubled the prompt for older taste.

Not backfilled deliberately: the edited Securitas CV in the old Desktop\Privat
checkout runs the other way — inflated titles, more tool detail, an invented
headcount — so feeding it back would teach the opposite of the current direction.

## Pending / known issues
- Nothing tracked. Next scheduled pipeline run: Wednesdays and Fridays 07:00 CET.
