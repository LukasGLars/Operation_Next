import anthropic
import requests
import json
import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, date
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

# Active statuses — partial match so "Ansökt 2026-05-02" is caught by "ansökt"
ACTIVE_STATUS_TOKENS = {"identifierad", "spontanansökan", "spontanansokan", "genererat", "ansökt"}

# Search queries split into two thematic passes
QUERIES_PASS1 = [
    "business analyst Göteborg",
    "teknisk säljare hybrid Sverige",
    "affärsutvecklare scale-up Göteborg",
    "implementation consultant Sverige",
    "sales engineer Göteborg",
    "customer success manager Sverige",
    "product specialist Göteborg",
    "business analyst Gothenburg",
    "solutions engineer Sweden hybrid",
    "implementation manager Sweden",
    "technical sales Gothenburg",
    "customer success manager Sweden",
]

QUERIES_PASS2 = [
    "entreprenadingenjör Göteborg",
    "kalkylingenjör bygg hybrid",
    "projekteringsingenjör anläggning Sverige",
    "inköpare bygg Sverige",
    "procurement engineer Sverige",
    "civil engineer Gothenburg hybrid",
    "construction project engineer Sweden",
    "quantity surveyor Sweden",
]

SEARCH_TIMEOUT_SECS = 300


# ── Loaders ────────────────────────────────────────────────

def load_joblist():
    """Parse joblist.md table. Handles both 6-column (no Datum) and 7-column (with Datum) tables."""
    jobs = []
    if not JOBLIST_PATH.exists():
        return jobs
    with open(JOBLIST_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    header_cols = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # Header row
        if cells and cells[0] == "#":
            header_cols = [c.lower() for c in cells]
            continue
        # Separator row
        if header_cols and all(re.match(r"^-+$", c) for c in cells if c):
            continue
        if not header_cols:
            continue
        try:
            idx = {h: i for i, h in enumerate(header_cols)}
            company = cells[idx["företag"]]   if "företag"  in idx and idx["företag"]  < len(cells) else ""
            role    = cells[idx["roll/typ"]]   if "roll/typ" in idx and idx["roll/typ"] < len(cells) else ""
            status  = cells[idx["status"]]     if "status"   in idx and idx["status"]   < len(cells) else ""
            url     = cells[idx["url"]]        if "url"      in idx and idx["url"]      < len(cells) else ""
        except Exception:
            continue
        if company.lower() in ("företag", "---", ""):
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


def _is_active_status(status_str):
    s = status_str.lower()
    return any(token in s for token in ACTIVE_STATUS_TOKENS)


def validate_url(url):
    if not url or url in ("—", ""):
        return None
    if not url.startswith("http"):
        return None
    try:
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code == 200
    except Exception as e:
        logging.error(f"validate_url({url}): {e}")
        return None


def _extract_jsonld_job(soup):
    """Extract job content from JSON-LD structured data."""
    from bs4 import BeautifulSoup as _BS
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = next((x for x in data if isinstance(x, dict) and x.get("@type") in ("JobPosting", "Job")), None)
            if isinstance(data, dict) and "@graph" in data:
                data = next((x for x in data["@graph"] if isinstance(x, dict) and x.get("@type") in ("JobPosting", "Job")), data)
            if not isinstance(data, dict) or data.get("@type") not in ("JobPosting", "Job"):
                continue
            parts = []
            if data.get("title"):
                parts.append(f"Title: {data['title']}")
            org = data.get("hiringOrganization")
            if org:
                parts.append(f"Company: {org.get('name', org) if isinstance(org, dict) else org}")
            loc = data.get("jobLocation")
            if loc:
                if isinstance(loc, list):
                    loc = loc[0]
                if isinstance(loc, dict):
                    addr = loc.get("address", {})
                    city = addr.get("addressLocality", "") if isinstance(addr, dict) else str(addr)
                    parts.append(f"Location: {city}")
            for field in ["description", "qualifications", "responsibilities", "skills"]:
                val = data.get(field)
                if val and isinstance(val, str):
                    clean = _BS(val, "html.parser").get_text(separator="\n", strip=True)
                    parts.append(f"{field.capitalize()}:\n{clean[:2000]}")
            if data.get("datePosted"):
                parts.append(f"Posted: {data['datePosted']}")
            if parts:
                return "\n\n".join(parts)
        except Exception:
            continue
    return None


def fetch_page_text(url):
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        jsonld = _extract_jsonld_job(soup)
        if jsonld:
            return jsonld[:4000]
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:4000]
    except Exception as e:
        logging.error(f"fetch_page_text({url}): {e}")
        return ""


def batch_validate_urls(candidates, validation_skill):
    """Validate all candidate URLs in a single Claude call. Returns dict url -> (verdict, reason)."""
    if not validation_skill or not candidates:
        return {c.get("url", ""): ("uncertain", "no skill or no candidates") for c in candidates}

    entries = []
    for c in candidates:
        url = c.get("url", "").strip()
        if not url:
            continue
        page_text = fetch_page_text(url)
        entries.append({"url": url, "content": page_text or "(could not fetch)"})

    if not entries:
        return {}

    items = "\n\n".join(
        f"--- URL {i+1} ---\nURL: {e['url']}\nPage content:\n{e['content'][:2000]}"
        for i, e in enumerate(entries)
    )

    prompt = (
        f"Validate each of the following {len(entries)} URLs against the skill rules.\n\n"
        f"{items}\n\n"
        "Return a JSON array with one object per URL in the same order:\n"
        '[{"url": "...", "verdict": "valid|invalid|uncertain", "reason": "..."}]'
    )

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=validation_skill,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON array in response: {text[:200]}")
        results = json.loads(match.group())
        return {r["url"]: (r.get("verdict", "uncertain"), r.get("reason", "")) for r in results}
    except Exception as exc:
        logging.error(f"Batch URL validation failed: {exc}")
        return {entry["url"]: ("uncertain", f"validation error: {str(exc)[:60]}") for entry in entries}


# ── Claude web search ──────────────────────────────────────

def _call_claude_search(skill_content, known_urls, queries, pass_label):
    """One search pass. Uses explicit query list and no arbitrary result cap."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    skip_block    = "\n".join(known_urls) if known_urls else "(none)"
    profile_block = skill_content.strip() or (
        "No skill profile loaded — search broadly for: "
        "Business Analyst, Technical Sales, Product Manager roles in Sweden."
    )
    queries_block = "\n".join(f"- {q}" for q in queries)
    today         = date.today().isoformat()

    system = f"""You are a job search assistant for a candidate based in Sweden (commute from Alingsås).
Find all relevant new job postings matching the candidate profile.
Return every qualifying role found — no upper limit on results.

URL QUALITY RULES — CRITICAL:
- Only return URLs pointing to a single specific job posting page.
- The URL must contain a unique job ID or slug identifying exactly one role.
- Prefer employer career pages on Teamtailor, Jobylon, Greenhouse, Workable, or similar ATS platforms.
- Never return aggregator sites: ledigajobb.se, jobbland.se, indeed.com, monster.se, jobbet.se
- Never return category pages, search result pages, or listing hubs.
- Good example: collaborate.checkwatt.se/jobs/4669704-customer-success-manager
- Bad example: ledigajobb.se/jobb/business-analyst-goteborg
- Bad example: company.com/career (general careers page)

CANDIDATE PROFILE:
{profile_block}

URLS ALREADY IN JOBLIST — NEVER RETURN THESE:
{skip_block}

Respond with ONLY a JSON array (empty array if no qualifying roles found):
[{{"company": "...", "role": "...", "url": "...", "role_type": "...", "cv_base": "...", "location": "...", "status": "Identifierad", "date_added": "{today}"}}]"""

    user_msg = (
        f"Run the following {len(queries)} search queries and return all qualifying job postings found. "
        f"Prioritise roles posted in the last 3 weeks. "
        f"Only return direct links to individual job posting pages.\n\n"
        f"Search queries to run ({pass_label}):\n{queries_block}\n\n"
        f"For each query, search and collect results. "
        f"After all searches, return every qualifying role as a JSON array."
    )

    def _do_call():
        return client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 15,
            }],
            messages=[{"role": "user", "content": user_msg}],
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_call)
        try:
            response = future.result(timeout=SEARCH_TIMEOUT_SECS)
        except FuturesTimeout:
            logging.error(f"Claude search timed out after {SEARCH_TIMEOUT_SECS}s ({pass_label})")
            print(f"  TIMEOUT: Claude search ({pass_label}) exceeded {SEARCH_TIMEOUT_SECS}s")
            return []

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            logging.error(f"JSON parse failed ({pass_label}): {e} — raw: {text[:300]}")
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

    # Check known URLs — active jobs only, with partial status match
    closed_jobs = []
    known_urls  = []

    for job in jobs:
        url = job["url"]
        if url and url != "—" and url.startswith("http"):
            known_urls.append(url)
        if _is_active_status(job["status"]):
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

    print(f"  Closed: {len(closed_jobs)} | Known URLs: {len(known_urls)}")

    # Two-pass web search
    raw_candidates: list = []

    for pass_label, queries in [("BA/Tech/Sales", QUERIES_PASS1), ("Construction/Civil", QUERIES_PASS2)]:
        print(f"  Calling Claude web search — {pass_label} ({len(queries)} queries)...")
        try:
            results = _call_claude_search(skill_content, known_urls, queries, pass_label)
            print(f"  Pass '{pass_label}' returned {len(results)} candidates")
            raw_candidates.extend(results)
        except Exception as e:
            logging.error(f"Claude search failed ({pass_label}): {e}")
            print(f"  ERROR: Claude search failed ({pass_label}): {e}")

    # Deduplicate across passes by URL
    seen_urls: set = set()
    deduped: list  = []
    for c in raw_candidates:
        url = c.get("url", "").strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(c)
    print(f"  Total candidates after dedup: {len(deduped)}")

    # Stage 1 — domain blocklist + HTTP reachability
    reachable = []
    for candidate in deduped:
        url = candidate.get("url", "").strip()
        if not url:
            continue
        if url in known_urls:
            print(f"  SKIP (known): {url}")
            continue
        if _is_blocked_domain(url):
            logging.error(f"BLOCKED (aggregator domain): {url}")
            print(f"  SKIP (aggregator): {url}")
            continue
        try:
            if not validate_url(url):
                print(f"  SKIP (bad URL): {url}")
                continue
        except Exception as e:
            logging.error(f"Validation failed for {url}: {e}")
            continue
        reachable.append(candidate)

    # Stage 2 — batched quality validation
    new_jobs = []
    if reachable:
        print(f"  Validating {len(reachable)} reachable URL(s) in one call...")
        verdicts = batch_validate_urls(reachable, val_skill)
        for candidate in reachable:
            url = candidate.get("url", "").strip()
            verdict, reason = verdicts.get(url, ("uncertain", "not in response"))
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
