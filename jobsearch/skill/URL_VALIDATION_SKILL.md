---
name: url-validation
description: Validates whether a URL is a specific, accessible job posting page suitable for application generation. Use when checking job links, filtering out aggregators, category pages, search results, expired postings, or pages without complete job details.
---
# URL Validation Skill

## Purpose
Decide whether a URL is a valid source for a single job posting.

## Goal
Pass only URLs that point to one specific job ad with enough content to support CV and cover-letter generation.

## Reject immediately if the URL is:
- A search results page.
- A category page.
- A filtered listing page.
- An aggregator hub page.
- A duplicate copy when a canonical job page exists.
- Behind login.
- Expired.
- Missing a way to apply.
- Missing clear job content.

## Accept only if the page is:
- A single job posting page.
- Publicly accessible.
- Specific to one role.
- Canonical or clearly the best available source.
- Rich enough to support downstream document generation.

## Validation workflow
1. Open the URL.
2. Classify the page type.
3. Check whether the page is a single job posting.
4. Check whether the page is accessible without login.
5. Check whether the page contains core job details.
6. Check whether the page is canonical or a duplicate.
7. Return a final verdict.

## Required signals
The page should clearly contain most of these:
- Job title.
- Company or hiring organization.
- Location.
- Job description.
- Qualifications or requirements.
- Application path or apply CTA.
- Posting date or validity information when available.

## Hard rejection rules
Reject if any of the following are true:
- The page is clearly a list page or search page.
- The page is a category landing page.
- The page is an aggregator page with many jobs.
- The page has no concrete role details.
- The page requires sign-in to read the posting.
- The page is expired and still marked as active.
- The URL redirects to a generic feed or listing instead of a single role.
- The page content does not match the role implied by the URL or title.
- The page contains any of these phrases or close equivalents:
  - "This position is no longer active"
  - "This job is no longer available"
  - "This job is no longer accepting applications"
  - "This position has been filled"
  - "This ad has expired"
  - "No longer accepting applications"
  - "Applications are closed"
  - "Applications closed"
  - "Position filled"
  - "Role has been filled"
  - "Denna tjänst är inte längre aktiv"
  - "Tjänsten är tillsatt"
  - "Annonsen har utgått"
  - "Ansökan är stängd"
  - "Ansökan stängd"
  - "Vi tar inte längre emot ansökningar"
  - "Rekryteringen är avslutad"
  - "Tjänsten är stängd"
  - "See open jobs" as the primary call-to-action (indicates the specific posting is gone)
  - Any message indicating the role has closed, been filled, or been removed.
- The posting date is explicitly stated and is more than 5 weeks ago.

## Canonicality rules
Prefer the canonical page for the job posting.
If multiple URLs show the same role, choose the one that:
- Is the employer's own page.
- Has the most complete job description.
- Is clearly the primary posting URL.
- Is not a filtered or tracking URL.

## Remote-job handling
If the role is remote:
- Accept only if the page clearly states remote or hybrid status.
- Prefer pages that specify applicant location requirements.
- Reject if remote status is implied but not explicit.

## Output
Return JSON in this shape:
```json
{
  "url": "string",
  "verdict": "valid | invalid | uncertain",
  "page_type": "job_posting | aggregator | category | search_results | unknown",
  "canonical_url": "string",
  "reason": "short sentence",
  "signals": {
    "job_title_present": true,
    "company_present": true,
    "location_present": true,
    "description_present": true,
    "apply_cta_present": true,
    "login_required": false,
    "expired": false
  }
}
```

## Decision rules
- Use `valid` only when the page is clearly a single job posting and contains enough detail.
- Use `invalid` when the page is clearly not suitable.
- Use `uncertain` only when the page might be usable but key signals are missing.
- Prefer precision over recall.
