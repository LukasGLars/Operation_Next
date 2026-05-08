import anthropic
import requests
import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path

ROOT               = Path(__file__).parent.parent
JOBLIST_PATH       = ROOT / "jobsearch" / "joblist.md"
SKILL_PATH         = ROOT / "jobsearch" / "skill" / "SKILL.md"
VALIDATION_SKILL   = ROOT / "jobsearch" / "skill" / "URL_VALIDATION_SKILL.md"
RESULTS_PATH       = Path(__file__).parent / "results.json"
ERROR_LOG          = Path(__file__).parent / "error.log"

logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

BLOCKED_DOMAINS = {
    "ledigajobb.se", "jobbland.se", "indeed.com", "monster.se",
    "jobbet.se", "platsbanken.arbetsformedlingen.se", "reed.co.uk",
    "totaljobs.com", "cv-biblioteket.se",
}


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
                jobs.append({"company": company, "role": role, "status": status, "url": url})
    return jobs


def load_skill():
    if not SKILL_PATH.exists():
        return ""
    with open(SKILL_PATH, encoding="utf-8") as f:
        return f.read()


def load_validation_skill():
    if not VALIDATION_SKILL.exists():
        return ""
    with open(VALIDATION_SKILL, encoding="utf-8") as f:
        return f.read()


# ── URL helpers ────────────────────────────────────────────

def _is_blocked_domain(url):
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)
    except Exception:
        return False


def validate_url(url):
    if not url or url in ("—", ""):
        return None
    try:
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code == 200
    except Exception as e:
        logging.error(f"validate_url({url}): {e}")
        return None


def fetch_page_text(url):
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:4000]
    except Exception as e:
        logging.error(f"fetch_page_text({url}): {e}")
        return ""


def validate_url_quality(url, validation_skill):
    """Call Claude with URL_VALIDATION_SKILL to assess page quality."""
    if not validation_skill:
        return "uncertain", "validation skill not loaded"

    page_text = fetch_page_text(url)
    if not page_text:
        return "uncertain", "could not fetch page content"

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=validation_skill,
            messages=[{
                "role": "user",
                "content": (
                    f"Validate this URL: {url}\n\n"
                    f"Page content (truncated):\n{page_text}\n\n"
                    "Return only the JSON verdict."
                ),
            }],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        result = json.loads(text)
        return result.get("verdict", "uncertain"), result.get("reason", "")
    except Exception as e:
        logging.error(f"URL quality validation failed for {url}: {e}")
        return "uncertain", str(e)[:80]


# ── Claude web search ──────────────────────────────────────

def _call_claude_search(skill_content, known_urls):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    skip_block    = "\n".join(known_urls) if known_urls else "(none)"
    profile_block = skill_content.strip() or (
        "No skill profile loaded — search broadly for: "
        "Business Analyst, Technical Sales, Product Manager roles in Sweden."
    )

    system = f"""You are a job search assistant for a candidate based in Sweden.
Use the candidate profile below to find relevant new job postings.
Search in both Swedish and English.
Return up to 5 new roles not already in the known URL list.

URL QUALITY RULES — CRITICAL:
- Only return URLs pointing to a single specific job posting page.
- The URL must contain a unique job ID or slug identifying exactly one role.
- Prefer employer career pages on Teamtailor, Jobylon, Greenhouse, or similar ATS platforms.
- Never return aggregator sites: ledigajobb.se, jobbland.se, indeed.com, monster.se, jobbet.se
- Never return category pages, search result pages, or listing hubs.
- Good example: collaborate.checkwatt.se/jobs/4669704-customer-success-manager
- Bad example: ledigajobb.se/jobb/business-analyst-goteborg
- Bad example: biner.se/en/career (general careers page)

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
                "matching my profile. Prioritise roles posted in the last 2 weeks. "
                "Only return direct links to individual job posting pages — "
                "never aggregator listings or category pages."
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
        jobs          = load_joblist()
        skill_content = load_skill()
        val_skill     = load_validation_skill()
        print(f"  Loaded {len(jobs)} jobs | SKILL.md: {'loaded' if skill_content.strip() else 'empty'} | validation skill: {'loaded' if val_skill.strip() else 'missing'}")
    except Exception as e:
        logging.error(f"Context load failed: {e}")
        raise

    # Check known URLs
    closed_jobs = []
    known_urls  = []
    active_statuses = {"identifierad", "spontanansökan", "spontanansokan", "genererat"}

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

    # Validate candidates
    new_jobs = []
    for candidate in raw_candidates:
        url = candidate.get("url", "").strip()
        if not url:
            continue
        if url in known_urls:
            print(f"  SKIP (known): {url}")
            continue

        # Block known aggregator domains immediately
        if _is_blocked_domain(url):
            logging.error(f"BLOCKED (aggregator domain): {url}")
            print(f"  SKIP (aggregator): {url}")
            continue

        # HTTP reachability check
        try:
            if not validate_url(url):
                print(f"  SKIP (bad URL): {url}")
                continue
        except Exception as e:
            logging.error(f"Validation failed for {url}: {e}")
            continue

        # Quality validation via URL_VALIDATION_SKILL
        verdict, reason = validate_url_quality(url, val_skill)
        if verdict == "valid":
            print(f"  NEW: {candidate.get('company')} — {candidate.get('role')}")
            new_jobs.append(candidate)
        else:
            logging.error(f"URL rejected [{verdict}] ({reason}): {url}")
            print(f"  SKIP ({verdict} — {reason[:60]}): {url}")

    # Save results
    results = {
        "timestamp":   datetime.now().isoformat(),
        "new_jobs":    new_jobs,
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
