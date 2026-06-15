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

## Pending / known issues
- Review button not yet built (next session)
- Valeryd Toolkit deployment discussed — Railway recommended over Vercel (PyMuPDF native binaries, timeout risk on serverless)
- Silent pipeline failure — mailer sends nothing when no new/closed jobs, can't distinguish from crash
