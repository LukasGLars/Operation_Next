# Operation Next — Memory

## What this is
Automated job search and application pipeline. Finds roles, tracks them in joblist.md, generates tailored CV and cover letter via a Flask UI at localhost:5003.

## Current state (June 2026)

### Architecture
- `pipeline/search.py` — finds and validates new job postings, uses `search_skill.md`
- `app/app.py` — Flask UI on port 5003, generates CV + cover letter on demand, uses `generation_skill.md`
- `jobsearch/cv/master_cv.md` — single source of truth for all work history and projects (replaced 5 static PDF CV bases)
- `jobsearch/skill/generation_skill.md` — generation instructions, framing angles, approved reference examples
- `jobsearch/skill/search_skill.md` — search queries, role filters, location rules
- `jobsearch/skill/review_skill.md` — review prompt (not yet wired into app, next build task)
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

## Next build task — Review button

### What it is
A second Claude pass after generation. User generates, reads the output, clicks Review. A second call re-reads the job posting and rewrites the output to mirror the company's actual need and register.

### Why
Generated Swedish reads like translated English — clunky compound nouns, unnatural sentence structure, corporate phrasing. The review pass has one focused job: naturalise the language and reframe the content to answer what the company is actually anxious about, in their own register.

### How to build it
1. New route in `app/app.py` — `/review` POST endpoint
2. Inputs: job posting URL (refetch or pass text), current cv, current cover_letter
3. Reads `review_skill.md` as the instruction
4. Returns same JSON structure as `/generate`: `{"cv": "...", "cover_letter": "..."}`
5. New "Review" button in `templates/generate.html` — triggers after generation, replaces content in the same editor panels

### Prompt anchoring
The review prompt must receive the raw job posting text so it can identify the 2–3 real anxieties behind the role and mirror the ad's register back. See `review_skill.md` for full instruction.

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

## Pending / known issues
- Review button not yet built (next session)
- Valeryd Toolkit deployment discussed — Railway recommended over Vercel (PyMuPDF native binaries, timeout risk on serverless)
- Silent pipeline failure — mailer sends nothing when no new/closed jobs, can't distinguish from crash
