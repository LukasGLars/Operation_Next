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
Falls back to the unreviewed draft if the call fails. It also receives the
matched edited example described below.

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
  cookie notice, ~379 characters. Never *fetch* `webpage_url`; the pipeline reads
  the employer apply URL, normalised to the posting page where the ATS path
  carries the id. Query-string ids (recman, ponty) must be kept intact.
  This is about fetching only — `webpage_url` renders fine in a browser and is
  now kept as the `Annons` column. See "Ad URL vs apply URL" below.
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

## Matched edited examples by role (PR #8, merged before this entry)

`_matched_edited_examples` in `app/app.py` replaced "always show the newest
edit" with a Claude call that picks the past edited example whose role is
closest to the one being drafted, then feeds the *original vs. edited* diff
(not just the finished edit) into the review pass. The diff is the sharper
signal — it shows exactly what gets rejected (reused anecdotes, bulleted
metrics, wrong company name), not just what a finished draft looks like.
Matching reads `meta.json` (`{"company", "role"}`) per application folder;
falls back to the folder slug if `meta.json` is missing, so a missing file
degrades match quality but doesn't break anything.

### Gotcha: meta.json goes missing when an example is saved outside `/save`
Both `/generate` and `/save` call `_save_meta` automatically, so `meta.json`
should always exist for anything the app itself wrote. It's gone missing
twice now (`8fb94b1`, and again 2026-08-05 for the Vitec/Infometric example,
fixed in PR #9) — both times for a folder that has `_edited.md` files but no
`meta.json`, consistent with the docs having been created outside the app's
own save flow rather than a code bug. When you notice a new application
folder without `meta.json`, backfill it manually from `joblist.md`'s
company/role columns rather than assuming the app is broken.

## Notifications (August 2026)

`search.py` records a `run_errors` list and per-stage counts in `results.json`;
`mailer.py` mails only on new roles or errors. Closed ads are written to the
joblist as Stängd without a mail, and a clean run with nothing new stays silent.

Silence is only safe because a missing or stale `results.json` counts as an error
(so a pipeline that dies without crashing still mails) and a hard crash fails the
Actions job, which notifies separately. Keep both of those intact if this is
touched.

## `/save` didn't push (fixed 2026-08-11)

`/save` wrote edited docs to disk via `_save_docs`/`_save_meta` but never called
`_push_joblist()`, unlike `/generate`. Edited docs sat untracked locally until an
unrelated `/generate` call happened to sweep them into its commit — which also
meant the matched-edited-examples feature above couldn't see them until then.
Fixed by adding the `_push_joblist()` call to `/save` too.

## Manually rejected jobs resurfaced (fixed 2026-08-14)

Found while auditing the joblist: `update_joblist()`'s dedup only checked
`known_urls`, built from whatever rows currently sit in `joblist.md`. Once a
row was manually removed (via the app's `/delete` button, or a manual cleanup
commit like `b2bc87a`), nothing remembered that it had been rejected — the
next search/JobTech pass would find the same URL again with nothing to skip
it. Two postings had round-tripped this way: SEVR "Customer Success –
Fintech" and Friday Väst "Strategisk Inköpare", both dropped 2026-08-11 as
dead/mismatched, both back in the list by 2026-08-12/14 under the same job
IDs.

Fix: `jobsearch/rejected.md`, a markdown table of `Företag | Roll/Typ | Datum
| URL`, checked by URL in `pipeline/updater.py::load_rejected_urls()` before a
new row is added (`SKIP (rejected)` in the log, alongside the existing `SKIP
(duplicate)`). `app/app.py::_delete_job_row` now appends to it automatically
via `_append_rejected` before removing the row, so clicking delete in the UI
is enough going forward — no separate step needed. Backfilled with the two
resurfaced rows plus two more from the same 2026-08-11 cleanup (Poolia AB,
ICOMERA AB) that hadn't resurfaced yet but are equally liable to. Covered by
`tests/test_rejected.py`.

Only URL is checked, matching the dedup key `known_urls` already uses — no
fuzzy company/role matching, so a genuinely new posting from a previously
rejected employer is unaffected.

## aplitrak.com meta-refresh redirect (fixed 2026-08-14)

Doc generation failed with "No JSON found in response" for an Experis /
Alingsås Energi role. Root cause: `aplitrak.com` (used by Experis, Manpower,
Jefferson Wells) wraps the real posting behind a client-side `<meta
http-equiv="refresh">`, not a real HTTP redirect — `requests` never follows
it, so `fetch_page_text`/`visible_page_text` (`search.py`) and
`fetch_job_posting` (`app.py`) all read an empty spinner page. Claude then had
nothing to work with and replied in prose instead of JSON.

Likely also silently starved the location gate for any aplitrak-sourced ad
already in the pipeline — an empty page reads as "no location stated" and
gets dropped rather than evaluated. No way to know how many were lost.

Fix: `_meta_refresh_target()` (duplicated in both files, same pattern as the
table read/write helpers) parses the `<meta refresh>` target and the three
fetch functions follow it once before parsing. The stored apply URL in
`joblist.md` is untouched — only the content-fetching path changed. Covered
by `tests/test_meta_refresh.py`.

Also confirmed while investigating: rows #20/#23 (both "Experis AB —
Inköpare/ Upphandlare / Alingsås Energi") were the same underlying job —
the aplitrak URL embeds a job ref (`13765`) that matched on both, only the
tracking id differed. Not fixed by this PR; still sitting in the joblist as
of this writing.

## Ad URL vs apply URL, and ad expiry (2026-08-31)

Symptom: clicking a role in the joblist opened a bare application form — name,
e-mail, CV upload — with no ad text anywhere. You could not read what you were
applying for. Separately, ads stayed in the list long after their deadline.

One cause for both: `jobtech.py` stored exactly one URL per job, the apply link,
and read nothing about expiry. `webpage_url` and `application_deadline` were in
every API response and both discarded.

The apply-link choice was deliberate (see the JobTech gotchas above) but
over-applied. It conflated two different needs: the URL the *pipeline fetches*
for ad text, which must be the employer page, and the URL a *human clicks* to
read the ad, which wants the ad page. The cookie-notice problem only affects the
scraper — Platsbanken renders fine in a browser.

### Shape
- `jobtech.ad_url()` / `jobtech.deadline()` / `jobtech.is_open()`.
- Two new joblist columns, `Annons` and `Deadline`. **`URL` keeps its exact
  meaning** — it is the identity key for dedup, `rejected.md`, status updates and
  `closed_jobs`, so repointing it would break continuity with every existing row
  and every rejected URL. `URL` also stays the last column; some readers take it
  positionally.
- `is_open()` gates hits before relevance in `fetch_candidates` — cheapest first,
  and an expired ad is not worth judging.
- `updater.close_expired()` flips past-deadline rows to `Stängd`, which hands
  them to the existing 30-day `Stängd` prune rather than adding a second
  deletion path. It skips rows already `Stängd`, otherwise `Datum` would be
  bumped every run and the prune could never reach them.
- UI: the title links `Annons` (falling back to `URL` for rows without one), with
  a small "Ansök" chip for the form.

### Decisions worth keeping
- **A missing deadline counts as open.** Absence is not evidence of expiry;
  dropping those would lose every ad that never set one.
- **The closing day itself is still open.** `due >= today`, not `>`.
- **The backfill never deletes.** `pipeline/backfill_ads.py` is a one-off that
  fills the columns on pre-existing rows; a row it cannot match is left alone and
  printed. A no-match does not mean expired — web-search-sourced rows were never
  in Platsbanken at all, and a live ad can miss on query drift or the per-query
  limit. It filled 18 of 41 rows; the other 23 are listed on the run.

### Gotchas found the hard way
- **The employer's own ad page can carry a stale deadline.** cilbuper's page said
  3 Aug; the API said 31 Aug and the form was still live. Platsbanken is the
  authoritative date — do not trust the scraped page.
- The employer's ad page is *not* in the API and is not derivable from the apply
  URL. `Annons` is the Platsbanken page, which carries the full ad text.
- `tests/fixtures/jobtech_search.json` predated both fields. Their deadlines are
  pinned to 2099 rather than restored to the real recorded values: the real ones
  have all passed, and a fixture that expires fails the suite on a date rather
  than on a change.
- `backfill_ads.py` reconfigures stdout to UTF-8. The scheduled run is UTF-8, but
  run by hand on Windows the console is cp1252 and the first `→` or `ä` aborts
  the run on a `print`.

## Pending / known issues
- ~~Duplicate row: the Experis/Alingsås Energi posting under two aplitrak
  tracking ids~~ — deleted 2026-08-31 via the app; the `Ansökt` row was kept and
  the `Identifierad` twin is now in `rejected.md`.
- **Second duplicate pair, not yet resolved:** Experis "Affärskoordinator /
  Business Analyst / Lyreco / Borås" appears twice, `Ansökt` and `Identifierad`,
  under two aplitrak tracking ids *and* two different Platsbanken ad ids
  (31366439, 31370158). Same fix — delete the `Identifierad` one via the app.
- Row numbers are not stable identifiers. This entry used to name "#20 and #23";
  both had drifted to different roles by the time anyone acted on it. Record the
  URL or the aplitrak prefix instead.
- Deduplication misses these because it keys on (company, role) and URL, and the
  aplitrak tracking id differs per row while the role string is identical. The
  stable identifier is the aplitrak local-part prefix — `eekdah`, `stakah` —
  base64-decoded out of the `adid` query parameter; the trailing 13765 is the
  customer id and is the same across unrelated employers.
- Next scheduled pipeline run: Wednesdays and Fridays 07:00 CET.
