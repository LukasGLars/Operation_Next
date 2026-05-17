import anthropic
import requests
import json
import os
import re
import logging
import time
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
    # Aggregators and job boards — never direct postings
    "ledigajobb.se", "jobbland.se", "indeed.com", "monster.se",
    "jobbet.se", "platsbanken.arbetsformedlingen.se", "reed.co.uk",
    "totaljobs.com", "cv-biblioteket.se",
    "linkedin.com", "glassdoor.com", "glassdoor.se",
    "stepstone.se", "stepstone.de",
    "jobbsafari.se", "careerjet.se", "careerjet.com",
    "jooble.org", "adzuna.se", "adzuna.com",
    "arbetsformedlingen.se",
}

# Generic path endings that indicate a listing/hub page, not a specific posting
_GENERIC_PATH_ENDS = {
    "career", "careers", "jobs", "jobb", "jobb-vi-soker", "jobb-vi-söker",
    "lediga-tjanster", "lediga-tjänster", "lediga-jobb", "open-positions",
    "openings", "vacancies", "vacancy", "join-us", "work-with-us",
    "jobba-hos-oss", "vi-soker", "vi-söker", "work-here", "jobba-har",
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

# ATS-targeted pass — site: searches return only direct employer postings with numeric IDs
QUERIES_PASS3 = [
    'site:teamtailor.com "business analyst" Göteborg',
    'site:teamtailor.com "customer success" Sverige',
    'site:teamtailor.com "sales engineer" Sverige',
    'site:teamtailor.com "affärsutvecklare" Sverige',
    'site:teamtailor.com "implementation" Sverige',
    'site:teamtailor.com "teknisk säljare" Sverige',
    'site:teamtailor.com "entreprenadingenjör" Sverige',
    'site:teamtailor.com "kalkylingenjör" Sverige',
    'site:jobylon.com "business analyst" Sverige',
    'site:jobylon.com "customer success" Sverige',
    'site:greenhouse.io "business analyst" Sweden',
    'site:lever.co "business analyst" Sweden',
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


def extract_search_profile(skill_content):
    """Return only the sections of SKILL.md needed for job searching.
    Drops CV rules, cover letter rules, key results library etc. — reduces
    tokens per search call from ~5000 to ~1000.
    """
    if not skill_content:
        return skill_content
    KEEP = {"role filters", "location rules", "cv base selection"}
    lines = skill_content.splitlines()
    sections: dict = {}
    current_key = None
    current_lines: list = []
    for line in lines:
        h2 = re.match(r'^##\s+(.+)', line)
        if h2:
            if current_key is not None:
                sections[current_key] = current_lines
            current_key = h2.group(1).strip().lower()
            current_lines = [line]
        elif current_key is not None:
            current_lines.append(line)
    if current_key is not None:
        sections[current_key] = current_lines
    result = []
    for key, sec_lines in sections.items():
        if any(k in key for k in KEEP):
            result.extend(sec_lines)
            result.append("")
    return "\n".join(result) if result else skill_content


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


def _url_looks_specific(url):
    """Return True if URL appears to point to one specific job posting.
    Valid posting URLs almost always have a numeric job ID or a long unique slug.
    """
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
        segments = [s for s in path.split("/") if s]
        if not segments:
            return False
        last = segments[-1].lower()
        if last in _GENERIC_PATH_ENDS:
            return False
        # Numeric job ID anywhere in path (e.g. /jobs/4669704-csm, /jobs/6909181)
        if any(re.search(r'\d{4,}', seg) for seg in segments):
            return True
        # Long unique slug (e.g. /jobs/customer-success-manager-till-checkwatt)
        if len(last) > 25:
            return True
        return False
    except Exception:
        return False


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
    for attempt in range(1, 4):
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
            is_429 = "429" in str(exc)
            if is_429 and attempt < 3:
                wait = 15 * attempt
                print(f"  429 rate limit — retrying batch validation in {wait}s (attempt {attempt}/3)")
                time.sleep(wait)
            else:
                logging.error(f"Batch URL validation failed (attempt {attempt}): {exc}")
                return {entry["url"]: ("uncertain", f"validation error: {str(exc)[:60]}") for entry in entries}


# ── Claude web search ──────────────────────────────────────

def _call_claude_search(skill_content, known_urls, queries, pass_label):
    """One search pass. Uses explicit query list and no arbitrary result cap."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    skip_block    = "\n".join(known_urls) if known_urls else "(none)"
    profile_block = extract_search_profile(skill_content).strip() or (
        "No skill profile loaded — search broadly for: "
        "Business Analyst, Technical Sales, Product Manager roles in Sweden."
    )
    queries_block = "\n".join(f"- {q}" for q in queries)
    today         = date.today().isoformat()

    system = f"""You are a job search assistant for a candidate based in Sweden (commute from Alingsås).
Find all relevant new job postings matching the candidate profile.
Return every qualifying role found — no upper limit on results.

URL QUALITY RULES — CRITICAL:
A valid posting URL almost always contains a numeric job ID (4+ digits) or a long
unique slug in the path. If the URL does not have one, it is almost certainly a
listing page or aggregator — do not return it.

Prefer ATS-hosted employer career pages:
  Teamtailor, Jobylon, Greenhouse, Workable, Lever, BambooHR, SmartRecruiters, Taleo

NEVER return these domains (hard block):
  ledigajobb.se, jobbland.se, indeed.com, monster.se, jobbet.se,
  linkedin.com, glassdoor.com, stepstone.se, jobbsafari.se, careerjet.se,
  arbetsformedlingen.se, jooble.org, adzuna.se

NEVER return pages that are:
  /career  /careers  /jobs  (root-level — no ID)  /lediga-jobb  /open-positions
  Search result pages.  Category or hub pages.  Any page listing multiple roles.

VALID URL examples — these all have numeric IDs or long unique slugs:
  collaborate.checkwatt.se/jobs/4669704-customer-success-manager      ← numeric ID
  emp.jobylon.com/jobs/354499-einride-senior-business-analyst          ← numeric ID
  careersweden.knowit.se/jobs/6909181                                  ← numeric ID
  boards.greenhouse.io/acmecorp/jobs/7894321                           ← numeric ID
  jobs.lever.co/company/abc12345-role-title-stockholm                  ← unique slug

INVALID URL examples — reject these:
  ledigajobb.se/jobb/business-analyst-goteborg    ← aggregator
  company.com/career                               ← generic page, no ID
  company.com/en/careers/open-positions            ← listing hub, no ID
  linkedin.com/jobs/view/123456789                 ← aggregator
  biner.se/en/career                               ← generic page, no ID

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
                "max_uses": 8,
            }],
            messages=[{"role": "user", "content": user_msg}],
        )

    response = None
    for attempt in range(1, 4):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_call)
            try:
                response = future.result(timeout=SEARCH_TIMEOUT_SECS)
                break
            except FuturesTimeout:
                logging.error(f"Claude search timed out after {SEARCH_TIMEOUT_SECS}s ({pass_label})")
                print(f"  TIMEOUT: Claude search ({pass_label}) exceeded {SEARCH_TIMEOUT_SECS}s")
                return []
            except Exception as exc:
                if "429" in str(exc) and attempt < 3:
                    wait = 90
                    print(f"  429 rate limit on search ({pass_label}) — waiting {wait}s (attempt {attempt}/3)")
                    time.sleep(wait)
                else:
                    raise

    if response is None:
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

    passes = [
        ("BA/Tech/Sales",      QUERIES_PASS1),
        ("Construction/Civil", QUERIES_PASS2),
        ("ATS-targeted",       QUERIES_PASS3),
    ]
    for i, (pass_label, queries) in enumerate(passes):
        if i > 0:
            print(f"  Waiting 90s before next pass (rate limit buffer)...")
            time.sleep(90)
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
        if not _url_looks_specific(url):
            logging.error(f"SKIP (no job ID or unique slug): {url}")
            print(f"  SKIP (generic URL — no job ID): {url}")
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
