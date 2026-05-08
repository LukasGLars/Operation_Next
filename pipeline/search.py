import anthropic
import requests
import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path

ROOT          = Path(__file__).parent.parent
JOBLIST_PATH  = ROOT / "jobsearch" / "joblist.md"
SKILL_PATH    = ROOT / "jobsearch" / "skill" / "SKILL.md"
RESULTS_PATH  = Path(__file__).parent / "results.json"
ERROR_LOG     = Path(__file__).parent / "error.log"

logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ── Loaders ────────────────────────────────────────────────

def load_joblist():
    jobs = []
    if not JOBLIST_PATH.exists():
        return jobs
    with open(JOBLIST_PATH, encoding="utf-8") as f:
        for line in f:
            m = re.match(
                r'\|\s*\d+\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|',
                line
            )
            if m:
                company = m.group(1).strip()
                role    = m.group(2).strip()
                status  = m.group(4).strip()
                url     = m.group(5).strip()
                if company.lower() in ("företag", "---"):
                    continue
                jobs.append({
                    "company": company,
                    "role":    role,
                    "status":  status,
                    "url":     url,
                })
    return jobs


def load_skill():
    if not SKILL_PATH.exists():
        return ""
    with open(SKILL_PATH, encoding="utf-8") as f:
        return f.read()


# ── URL validation ─────────────────────────────────────────

def validate_url(url):
    if not url or url in ("—", ""):
        return None
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        return r.status_code == 200
    except Exception as e:
        logging.error(f"validate_url({url}): {e}")
        return None


# ── Claude web search ──────────────────────────────────────

def _call_claude_search(skill_content, known_urls):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    skip_block = "\n".join(known_urls) if known_urls else "(none)"
    profile_block = skill_content.strip() or (
        "No skill profile loaded — search broadly for: "
        "Business Analyst, Management Consultant, Technical Sales, "
        "Product Manager roles in Sweden."
    )

    system = f"""You are a job search assistant for a candidate based in Sweden.
Use the candidate profile below to find relevant new job postings.
Search in both Swedish and English.
Return exactly up to 5 new roles not already in the known URL list.
For each role return: company, role title, direct application URL, role_type, cv_base, location, status (always "Identifierad"), date_added (today's date in YYYY-MM-DD).

CANDIDATE PROFILE:
{profile_block}

URLS ALREADY IN JOBLIST — SKIP THESE:
{skip_block}

Respond with ONLY a JSON array:
[{{"company": "...", "role": "...", "url": "...", "role_type": "...", "cv_base": "...", "location": "...", "status": "Identifierad", "date_added": "YYYY-MM-DD"}}]"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10,
        }],
        messages=[{
            "role": "user",
            "content": (
                "Search for the 5 most relevant new job postings in Sweden "
                "matching my profile. Prioritise roles posted in the last 2 weeks."
            ),
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return []


# ── Main ───────────────────────────────────────────────────

def search_new_jobs():
    print(f"[{datetime.now().isoformat()}] search.py starting")

    try:
        jobs = load_joblist()
        skill_content = load_skill()
        print(f"  Loaded {len(jobs)} jobs | SKILL.md: {'loaded' if skill_content.strip() else 'empty'}")
    except Exception as e:
        logging.error(f"Context load failed: {e}")
        raise

    # Validate known URLs
    closed_jobs = []
    known_urls  = []
    active_statuses = {"identifierad", "spontanansökan", "spontanansokan"}

    for job in jobs:
        url = job["url"]
        if url and url != "—":
            known_urls.append(url)
        if job["status"].lower() in active_statuses:
            try:
                result = validate_url(url)
                if result is False:
                    print(f"  CLOSED: {job['company']} — {url}")
                    closed_jobs.append({
                        "company": job["company"],
                        "role":    job["role"],
                        "url":     url,
                        "reason":  "non-200 response",
                    })
                elif result is True:
                    print(f"  ACTIVE: {job['company']}")
            except Exception as e:
                logging.error(f"URL check failed for {job['company']}: {e}")

    print(f"  Closed: {len(closed_jobs)}")

    # Search for new roles
    print("  Calling Claude web search...")
    raw_candidates = []
    try:
        raw_candidates = _call_claude_search(skill_content, known_urls)
        print(f"  Claude returned {len(raw_candidates)} candidates")
    except Exception as e:
        logging.error(f"Claude search failed: {e}")
        print(f"  ERROR: Claude search failed: {e}")

    # Validate new results
    new_jobs = []
    for candidate in raw_candidates:
        url = candidate.get("url", "").strip()
        if not url:
            continue
        if url in known_urls:
            print(f"  SKIP (known): {url}")
            continue
        try:
            if validate_url(url):
                print(f"  NEW: {candidate.get('company')} — {candidate.get('role')}")
                new_jobs.append(candidate)
            else:
                print(f"  SKIP (bad URL): {url}")
        except Exception as e:
            logging.error(f"Validation failed for {url}: {e}")


    # Save results
    results = {
        "timestamp":  datetime.now().isoformat(),
        "new_jobs":   new_jobs,
        "closed_jobs": closed_jobs,
    }
    try:
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"  Saved results.json — {len(new_jobs)} new, {len(closed_jobs)} closed")
    except Exception as e:
        logging.error(f"Failed to write results.json: {e}")
        raise

    print(f"[{datetime.now().isoformat()}] search.py done")
    return results


if __name__ == "__main__":
    search_new_jobs()
