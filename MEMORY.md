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

## Cross-run role dedup (2026-08-31)

A full scan of the 40-row list on four keys — aplitrak prefix, Platsbanken ad id,
company+role, apply-path id — plus fuzzy title matching found exactly one true
duplicate. The interesting part is why it got in.

Both rows had **identical company and role**, which is supposedly already a dedup
key. It was not caught because the two dedup passes cover different things and
neither covers this:

- `jobtech.fetch_candidates` keys on `(company, role)` but only **within a single
  run** — `seen_roles` is local to the call.
- `updater.update_joblist` dedups **across runs** but only on **URL**, and the
  aplitrak tracking id differs per sighting.

The two sightings were seven days apart (08-21 and 08-28), so they were never in
the same batch, and their URLs differed. Both passes let it through.

`updater.known_role_keys()` now closes it: `(company, role)` checked against the
rows already in joblist.md, not just against the current batch.

### Decisions worth keeping
- **Closed rows are excluded from the key set.** If the earlier posting ended, the
  same role appearing again is a real opening, not a duplicate of a live row.
  Blocking it would silently hide reposts of jobs that reopened.
- **Applied rows still block.** `Ansökt`/`Intervju`/`Genererat` are live states.
- **The key normalises case and whitespace only.** Nothing else is stripped:
  Bustos advertises "Inköpare bygg" and "Inköpare anläggning" as separate
  openings, and aggressive normalisation would collapse four real roles into one.
- **The skip is printed and logged**, unlike the URL and rejected skips. It is
  the one skip that can be wrong, and a false positive would otherwise be
  invisible — a genuinely new role would just never appear.

Verified against the live list: 39 rows → 35 live keys, replaying the deleted
repost is blocked, and zero collisions among existing rows.

### Not duplicates, though they look like it
Checked and deliberately left alone — #21–24 Bustos (bygg/anläggning ×
inköpare/entreprenadingenjör, four real roles), #26/#27 Eqwiry (operativ vs
strategisk), #9/#15 Peab (Peab Anläggning vs Peab Sverige, two ad systems, two
weeks apart — ambiguous, and #9 is Stängd so it prunes itself), #33/#40 SAAB
direct vs Poolia agency (different ad ids, deadlines and application channels —
worth keeping both).

### Gotcha
Row numbers are renumbered on every delete and prune, so they are useless as
identifiers in notes. An earlier entry here named "#20 and #23"; by the time it
was acted on, both pointed at unrelated roles. Record the URL or the aplitrak
prefix.

## Zero-diff edit examples (2026-08-31)

The review pass learns from the *diff* between its own draft and the human edit:
`_matched_edited_examples` labels the draft "REJECTED patterns, avoid repeating
these" and the edit "match this instead". When the two are byte-identical, that
is an instruction to avoid and copy the same text.

Four of the seventeen saved applications carried such a pair. Two of them —
`experis_ab_aff_rskoordinator` and `experis_ab_ink_pare` — were zero-diff on
*both* documents, and the first is "Affärskoordinator / Business Analyst /
Lyreco", the nearest neighbour to a Business Analyst role. So for the roles most
often applied for, the matcher was most likely to pick the one example that could
teach nothing.

**Cause:** `_save_docs` writes both documents on every save. Editing only the CV
and pressing save minted a cover letter "edit" identical to the draft.

**Fix:** `_save_docs` no longer writes an unchanged document, and deletes a
previously saved edit that has been reverted. `_edited_stems()` reports only the
stems that actually differ; it gates both candidate selection and block building,
so the four pairs already on disk are inert without deleting anything.

Effect on the corpus: 12 candidate folders → 10; cilbuper and oddwork trimmed to
their real half.

### Decisions worth keeping
- **An edit with no draft still counts.** `peab_anl_ggning_ab_entreprenadingenj_r`
  has edited files and no originals — there is no diff to show, but the finished
  version is still a usable model, and the builder already handles that branch.
- **Existing zero-diff files are left on disk, not deleted.** The code ignores
  them, and they are a record that save was pressed. They self-heal on the next
  save of that application.
- **`_original` is still never overwritten.** It is the "before" half of the
  diff; rewriting it on a re-generate would destroy the signal.

## Relevance gate (2026-09-02)

### Why
An audit of the 42-row list found it had drifted off target. Live rows were 34%
inköp and 28% bygg against **one** Business Analyst row — while all four
`Intervju` rows were teknisk säljare or affärsutvecklare. The category that
converts was 16% of the list; the two that never have were 62%.

Cause is mechanical, not judgement: `search_skill.md` weights all 22
include-keywords equally, and JobTech/Platsbanken is the volume source.
"Inköpare" is a high-volume Swedish taxonomy occupation, "business analyst"
barely exists as an ad headline, so the highest-supply keyword wins.

### What was built
`pipeline/relevance.py` — five rules, run as stage 1.6 between the location gate
and the batched Claude validation. Both sources pass through it (JobTech
candidates merge into `raw_candidates` before stage 1). Plus
`updater.recheck_dead_ads()` for rows already in the list.

### The one thing to keep
**Match on the title or an explicit number, never a bare body keyword.** The
first draft matched body keywords and had a **46% false-positive rate** — 6 of
13 flagged rows were fine. Every false positive was a preference sentence:
"du har *gärna* utbildning inom inköp", "*meriterande* om du har erfarenhet av
kategoristyrt inköp", "vi ser *gärna* att du har erfarenhet av LOU". `_soft_wish`
voids those. Verify any new rule the same way — print the matched sentence, do
not trust the count.

### Decisions worth keeping
- **`Ansökt`/`Intervju` are exempt from the dead-ad check.** A pulled ad is the
  *expected* state once you are in a process — row #1 (Platsa/UK Portservice)
  reads "jobbet tillsatt" while at final stage. Closing on it would delete
  exactly the rows that matter most.
- **Seniority gates only procurement.** Explicit user call: they convert in
  technical sales regardless of stated level, so "Senior Sales Engineer" passes.
- **Högskoleingenjör passes; civilingenjör/MSc does not.** Also the user's call.
- **registerkontroll ≠ säkerhetsprövning.** Background check on hire, not a gate
  on applying. Cost four Göteborgs Kommun roles before this was separated out.
- **A year range reports its floor.** "3–7 års" accepts 3, so it is not a gate.
- **Dead rows are set `Stängd`, not deleted**, handing them to the existing
  30-day prune rather than adding a second deletion path — same reasoning as
  `close_expired`.

### The purge that came with it
42 rows → 32. Seven relevance failures went to `rejected.md` (Bustos ×2 at
*minst fem års*, Eqwiry Strategisk, Göteborgs Kommun ×2, SAAB Senior Strategic
Purchaser, Friday Väst Erfaren strategisk). Three dead ads were deleted outright
(PEAB ×2, Fortifikationsverket) rather than rejected — a repost from those
employers is a genuine new opening, not a resurfacing.

### Still open
The **mix** problem is not solved. This gate removes unwinnable roles; it does
not stop procurement and bygg out-supplying the target categories on the next
run. That needs keyword weighting or a per-category cap in the JobTech pass, and
a `Fit` score column — neither is built. Note the evidence base is thin: 4
interviews, and only 1 of 11 inköp rows was ever actually applied to.

### Correcting an earlier read
Agency-brokered ads are **not** a drag and must not be filtered out — 3 of the 4
interviews came through them (Platsa, Oddwork ×2). Only Vitec was direct.

## Pending / known issues
- ~~Duplicate row: the Experis/Alingsås Energi posting under two aplitrak
  tracking ids~~ — deleted 2026-08-31 via the app; the `Ansökt` row was kept and
  the `Identifierad` twin is now in `rejected.md`.
- ~~Second duplicate pair: Experis "Affärskoordinator / Business Analyst /
  Lyreco / Borås"~~ — deleted 2026-08-31, and the hole that let it in is now
  closed (see "Cross-run role dedup" below).
- Row numbers are not stable identifiers. This entry used to name "#20 and #23";
  both had drifted to different roles by the time anyone acted on it. Record the
  URL or the aplitrak prefix instead.
- Deduplication misses these because it keys on (company, role) and URL, and the
  aplitrak tracking id differs per row while the role string is identical. The
  stable identifier is the aplitrak local-part prefix — `eekdah`, `stakah` —
  base64-decoded out of the `adid` query parameter; the trailing 13765 is the
  customer id and is the same across unrelated employers.
- Next scheduled pipeline run: Wednesdays and Fridays 07:00 CET.
