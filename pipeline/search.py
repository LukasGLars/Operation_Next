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

try:                                  # run as a script from pipeline/
    import jobtech
    import relevance
    from llm_json import TruncatedResponse, parse_json_array
except ImportError:                   # imported as pipeline.search (tests, CI)
    from pipeline import jobtech, relevance
    from pipeline.llm_json import TruncatedResponse, parse_json_array

ROOT               = Path(__file__).parent.parent
JOBLIST_PATH       = ROOT / "jobsearch" / "joblist.md"
SKILL_PATH         = ROOT / "jobsearch" / "skill" / "search_skill.md"
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
    "platsportalen.se",
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

# Places within roughly a 40 minute commute of Alingsås. Anything outside this
# set only passes when the ad explicitly states hybrid or remote work.
COMMUTABLE_PLACES = {
    "alingsås", "vårgårda", "sollebrunn", "gråbo", "floda", "stenkullen",
    "lerum", "partille", "sävedalen", "jonsered", "göteborg", "gothenburg",
    "mölndal", "mölnlycke", "härryda", "landvetter", "bollebygd", "borås",
    "lilla edet", "nödinge", "älvängen", "surte", "bohus", "ale",
}

# Fully remote passes from anywhere. Hybrid does not — two or three days a week
# in a Stockholm office is not commutable from Alingsås — so the two are matched
# separately. In body text both need a full phrase, otherwise "hybrid cloud" or
# "remote sensing" would let an out-of-range role through.
_FULLY_REMOTE_IN_LOCATION = re.compile(r"\b(remote|distans\w*|anywhere)\b", re.I)
_FULLY_REMOTE_IN_BODY = re.compile(
    r"(remote[- ]first|fully remote|helt remote|100\s*% remote|work from anywhere|"
    r"helt på distans|arbeta helt på distans)",
    re.I,
)
_HYBRID_IN_BODY = re.compile(
    r"(hybridarbete|hybridupplägg|hybridlösning|hybrid work|hybrid remote|"
    r"distansarbete|arbeta på distans|jobba på distans|arbeta hemifrån|"
    r"jobba hemifrån|möjlighet till distans|work from home)",
    re.I,
)

# Search queries split into three thematic passes. Sweden-wide on-site queries
# are wasted effort now that the location gate drops everything outside the ring
# unless it is fully remote — so the geography is either the region or remote.
QUERIES_PASS1 = [
    "business analyst Göteborg",
    "business analyst Gothenburg",
    "affärsutvecklare Göteborg",
    "teknisk säljare Göteborg",
    "sales engineer Göteborg",
    "customer success manager Göteborg",
    "solutions engineer Göteborg",
    "implementation consultant Göteborg",
    "product specialist Västra Götaland",
    "business analyst helt distansarbete Sverige",
    "customer success fully remote Sweden",
    "affärsutvecklare distans Sverige",
    # Alingsås and Borås are their own labor markets, not Göteborg suburbs —
    # everything else in COMMUTABLE_PLACES is a Göteborg satellite already
    # findable under "Göteborg" ad text and JobTech's municipality filter.
    "business analyst Alingsås",
    "affärsutvecklare Alingsås",
    "teknisk säljare Alingsås",
    "business analyst Borås",
    "affärsutvecklare Borås",
    "teknisk säljare Borås",
    "sales engineer Borås",
    "customer success manager Borås",
]

QUERIES_PASS2 = [
    "entreprenadingenjör Göteborg",
    "kalkylingenjör Göteborg",
    "projekteringsingenjör Göteborg",
    "inköpare bygg Göteborg",
    "entreprenadingenjör Alingsås Borås",
    "civil engineer Gothenburg",
    "construction project engineer Gothenburg",
    "procurement engineer Västra Götaland",
]

# ATS-targeted pass — site: searches return only direct employer postings with numeric IDs
QUERIES_PASS3 = [
    'site:teamtailor.com "business analyst" Göteborg',
    'site:teamtailor.com "customer success" Göteborg',
    'site:teamtailor.com "sales engineer" Göteborg',
    'site:teamtailor.com "affärsutvecklare" Göteborg',
    'site:teamtailor.com "implementation" Göteborg',
    'site:teamtailor.com "teknisk säljare" Göteborg',
    'site:teamtailor.com "entreprenadingenjör" Göteborg',
    'site:teamtailor.com "kalkylingenjör" Göteborg',
    'site:jobylon.com "business analyst" Göteborg',
    'site:jobylon.com "customer success" Göteborg',
    'site:greenhouse.io "business analyst" Gothenburg',
    'site:lever.co "business analyst" remote Sweden',
    'site:teamtailor.com "affärsutvecklare" Borås',
    'site:teamtailor.com "teknisk säljare" Borås',
]

SEARCH_TIMEOUT_SECS = 300

# One call for every candidate does not fit: a run with 32 candidates truncated
# its verdict array and every candidate was dropped as uncertain.
VALIDATION_CHUNK_SIZE = 8
VALIDATION_MAX_TOKENS = 4096


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


def page_location(page_text):
    """The Location: line fetch_page_text writes from JSON-LD — more reliable
    than the location the search model reports."""
    match = re.search(r"^Location:[ \t]*(.+)$", page_text or "", re.M)
    return match.group(1).strip() if match else ""


def remote_status_of(page_text):
    """"" | "hybrid" | "remote" — from the Remote status line fetch_page_text adds."""
    match = re.search(r"^Remote status:[ \t]*(.+)$", page_text or "", re.M)
    if not match:
        return ""
    value = match.group(1).strip().lower()
    if "hybrid" in value or "tillfälligt" in value or "temporarily" in value:
        return "hybrid"
    if "remote" in value or "distans" in value:
        return "remote"
    return ""


def location_verdict(stated_location, page_text=""):
    """Return (ok, reason). A role passes if its office is within commuting
    distance of Alingsås, or if it is fully remote. Hybrid only passes when the
    office itself is commutable — a Stockholm hybrid still means two or three
    days a week in Stockholm."""
    loc = (page_location(page_text) or stated_location or "").strip()
    status = remote_status_of(page_text)

    if any(re.search(rf"\b{re.escape(p)}\b", loc, re.I) for p in COMMUTABLE_PLACES):
        return True, f"within commute range ({loc})"
    if (status == "remote"
            or _FULLY_REMOTE_IN_LOCATION.search(loc)
            or (page_text and _FULLY_REMOTE_IN_BODY.search(page_text))):
        return True, f"fully remote ({loc or 'no location stated'})"
    if not loc:
        if status == "hybrid" or (page_text and _HYBRID_IN_BODY.search(page_text)):
            return True, "hybrid, no location stated"
        return False, "no location stated and no hybrid/remote wording"
    if status == "hybrid" or _HYBRID_IN_BODY.search(page_text or ""):
        return False, f"hybrid, but office outside 40 min commute ({loc})"
    return False, f"outside 40 min commute from Alingsås ({loc})"


def _is_generic_landing(url):
    """A careers hub with nothing identifying a role. Applied to candidates that
    skip the stricter URL shape check — such a page cannot support generation."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.query:
            return False
        last = parsed.path.rstrip("/").split("/")[-1].lower()
        return last in _GENERIC_PATH_ENDS
    except Exception:
        return False


def validate_url(url):
    """Returns (status_ok, final_url).
    status_ok: True=200, False=non-200, None=error/skip.
    final_url: URL after all redirects (may differ from input).
    """
    if not url or url in ("—", ""):
        return None, url
    if not url.startswith("http"):
        return None, url
    try:
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code == 200, r.url
    except Exception as e:
        logging.error(f"validate_url({url}): {e}")
        return None, url


def _redirect_to_hub(original_url, final_url):
    """True if redirect lost the job ID — likely bounced to a generic listing page."""
    if not final_url or final_url == original_url:
        return False
    from urllib.parse import urlparse
    orig_path  = urlparse(original_url).path
    final_path = urlparse(final_url).path
    orig_has_id  = bool(re.search(r'\d{4,}', orig_path))
    final_has_id = bool(re.search(r'\d{4,}', final_path))
    return orig_has_id and not final_has_id


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


def _remote_status(soup):
    """Teamtailor and friends state the work model in a definition list:
    <dt>Remote status</dt><dd>Hybrid</dd> / <dt>Distansarbete</dt><dd>Hybridarbete</dd>.
    More reliable than prose — the word "hybrid" also shows up in "hybrid cloud"."""
    for dt in soup.find_all("dt"):
        if dt.get_text(strip=True).lower() in ("remote status", "distansarbete"):
            dd = dt.find_next("dd")
            if dd:
                return dd.get_text(" ", strip=True)
    return ""


def _strip_page_chrome(soup):
    """Removes non-content chrome, including cookie-consent dialogs (e.g.
    Teamtailor's <dialog data-controller="common--cookies--alert">) which
    otherwise fill the 4000-char cap before any real job content is reached."""
    for tag in soup(["script", "style", "nav", "footer", "header", "dialog"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": re.compile("cookie", re.I)}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": re.compile("cookie", re.I)}):
        tag.decompose()


_META_REFRESH_RE = re.compile(
    r'<meta[^>]+http-equiv=["\']refresh["\'][^>]*content=["\'][^;]*;\s*url=[\'"]?([^\'">]+)',
    re.I,
)


def _meta_refresh_target(html, base_url):
    """Some ATS trackers (aplitrak.com, used by Experis/Manpower/Jefferson Wells
    ads) redirect via <meta http-equiv="refresh">, not a real HTTP redirect —
    requests' allow_redirects never follows it, so the page reads as empty."""
    match = _META_REFRESH_RE.search(html or "")
    if not match:
        return None
    from urllib.parse import urljoin
    return urljoin(base_url, match.group(1).strip())


def _get_following_meta_refresh(url):
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    redirect = _meta_refresh_target(r.text, r.url)
    if redirect and redirect != r.url:
        r = requests.get(redirect, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    return r


def fetch_page_text(url):
    try:
        from bs4 import BeautifulSoup
        r = _get_following_meta_refresh(url)
        soup = BeautifulSoup(r.text, "html.parser")
        status = _remote_status(soup)
        suffix = f"\n\nRemote status: {status}" if status else ""
        jsonld = _extract_jsonld_job(soup)
        if jsonld:
            return jsonld[:4000] + suffix
        _strip_page_chrome(soup)
        return soup.get_text(separator="\n", strip=True)[:4000] + suffix
    except Exception as e:
        logging.error(f"fetch_page_text({url}): {e}")
        return ""


def visible_page_text(url):
    """Full visible page text. Used only as a location fallback — some ATS pages
    carry no location in their JSON-LD and tag hybrid/remote in page chrome that
    fetch_page_text discards."""
    try:
        from bs4 import BeautifulSoup
        r = _get_following_meta_refresh(url)
        soup = BeautifulSoup(r.text, "html.parser")
        _strip_page_chrome(soup)
        return soup.get_text(" ", strip=True)[:6000]
    except Exception as e:
        logging.error(f"visible_page_text({url}): {e}")
        return ""


def _validate_chunk(entries, validation_skill):
    """One validation call. Returns dict url -> (verdict, reason)."""
    items = "\n\n".join(
        f"--- URL {i+1} ---\nURL: {e['url']}\nPage content:\n{e['content'][:2000]}"
        for i, e in enumerate(entries)
    )

    prompt = (
        f"Validate each of the following {len(entries)} URLs against the skill rules.\n\n"
        f"{items}\n\n"
        "Return a JSON array with one object per URL in the same order. Keep each "
        "reason under 12 words:\n"
        '[{"url": "...", "verdict": "valid|invalid|uncertain", "reason": "..."}]'
    )

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    for attempt in range(1, 4):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=VALIDATION_MAX_TOKENS,
                system=[{"type": "text", "text": validation_skill, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            results = parse_json_array(response.content[0].text)
            return {r["url"]: (r.get("verdict", "uncertain"), r.get("reason", "")) for r in results}
        except Exception as exc:
            is_429 = "429" in str(exc)
            if is_429 and attempt < 3:
                wait = 15 * attempt
                print(f"  429 rate limit — retrying batch validation in {wait}s (attempt {attempt}/3)")
                time.sleep(wait)
            else:
                label = "truncated" if isinstance(exc, TruncatedResponse) else "failed"
                logging.error(f"Batch URL validation {label} (attempt {attempt}): {exc}")
                return {e["url"]: ("uncertain", f"validation error: {str(exc)[:60]}") for e in entries}


def batch_validate_urls(candidates, validation_skill):
    """Validate candidate URLs in chunks. Returns dict url -> (verdict, reason).

    Chunked because one call for everything does not fit: a run with 32
    candidates truncated its verdict array and every single candidate was
    dropped as uncertain."""
    if not validation_skill or not candidates:
        return {c.get("url", ""): ("uncertain", "no skill or no candidates") for c in candidates}

    entries = []
    for c in candidates:
        url = c.get("url", "").strip()
        if not url:
            continue
        page_text = c.get("_page_text") or fetch_page_text(url)
        entries.append({"url": url, "content": page_text or "(could not fetch)"})

    if not entries:
        return {}

    verdicts = {}
    chunks = [entries[i:i + VALIDATION_CHUNK_SIZE]
              for i in range(0, len(entries), VALIDATION_CHUNK_SIZE)]
    for i, chunk in enumerate(chunks, 1):
        print(f"  Validating chunk {i}/{len(chunks)} ({len(chunk)} URL(s))...")
        verdicts.update(_validate_chunk(chunk, validation_skill))
    return verdicts


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

LOCATION RULES — CRITICAL:
Only return a role if it is either
  (a) within a 40 minute commute of Alingsås — Alingsås, Göteborg, Partille,
      Lerum, Mölndal, Mölnlycke, Härryda, Landvetter, Vårgårda, Bollebygd,
      Borås, Ale, Lilla Edet and equivalent, or
  (b) fully remote.
A hybrid role counts only if its office is inside that range — a Stockholm
hybrid still means two or three days a week in Stockholm. Reject on-site and
hybrid roles anywhere else — Stockholm, Malmö, Umeå, Södertälje, Borlänge,
Örnsköldsvik and the like — however well the role otherwise matches.
Always fill "location" with the city the ad states, or "Remote" when the ad is
fully remote.

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
            # Identical across pass1/2/3 within one run (same known_urls) --
            # cached so only the first pass pays full price for it.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                # Must cover the query list, plus room for a retry. At the old
                # fixed 8 the last third of every pass never ran, silently.
                "max_uses": len(queries) + 2,
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

    try:
        return parse_json_array(text)
    except TruncatedResponse as e:
        logging.error(f"Search response truncated ({pass_label}): {e}")
        print(f"  ERROR: search response truncated ({pass_label}) — raise max_tokens")
    except Exception as e:
        logging.error(f"JSON parse failed ({pass_label}): {e} — raw: {text[:300]}")
    return []


# ── Main ───────────────────────────────────────────────────

def search_new_jobs():
    print(f"[{datetime.now().isoformat()}] search.py starting")

    # Collected for the digest. A pass that fails is caught and logged, so
    # without this a broken run and a quiet week look identical downstream.
    run_errors: list = []

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
                ok, final_url = validate_url(url)
                if ok is False:
                    print(f"  CLOSED: {job['company']} — {url}")
                    closed_jobs.append({
                        "company": job["company"],
                        "role":    job["role"],
                        "url":     url,
                        "reason":  "non-200 response",
                    })
                elif ok is True:
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
            run_errors.append(f"web search pass '{pass_label}' failed: {str(e)[:120]}")

    web_candidate_count = len(raw_candidates)

    # Platsbanken via the JobTech API — structured location, no scraping
    jobtech_candidate_count = 0
    try:
        jt_candidates = jobtech.fetch_candidates(known_urls, location_ok=location_verdict)
        print(f"  JobTech returned {len(jt_candidates)} candidate(s) in range")
        jt_candidates = jobtech.judge_fit(jt_candidates, skill_content, errors=run_errors)
        print(f"  JobTech after role-fit judgement: {len(jt_candidates)}")
        jobtech_candidate_count = len(jt_candidates)
        raw_candidates.extend(jt_candidates)
    except Exception as e:
        logging.error(f"JobTech source failed: {e}")
        print(f"  ERROR: JobTech source failed: {e}")
        run_errors.append(f"JobTech source failed: {str(e)[:120]}")

    if not raw_candidates:
        run_errors.append("no candidates from any source — both the web search "
                          "and JobTech returned nothing")

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
        # JobTech candidates come from structured ad data, so they are known to be
        # single postings. The URL shape heuristics only exist to catch listing
        # pages the search model invented, and would reject valid apply URLs whose
        # job id sits in a query parameter.
        from_jobtech = candidate.get("_source") == "jobtech"
        if not from_jobtech and not _url_looks_specific(url):
            logging.error(f"SKIP (no job ID or unique slug): {url}")
            print(f"  SKIP (generic URL — no job ID): {url}")
            continue
        if from_jobtech and _is_generic_landing(url):
            logging.error(f"SKIP (careers hub, not a posting): {url}")
            print(f"  SKIP (careers hub): {url}")
            continue
        try:
            ok, final_url = validate_url(url)
            if not ok:
                print(f"  SKIP (bad URL): {url}")
                continue
            if not from_jobtech and _redirect_to_hub(url, final_url):
                logging.error(f"SKIP (redirect to hub): {url} → {final_url}")
                print(f"  SKIP (redirect to hub): {url}")
                continue
            candidate["url"] = final_url
        except Exception as e:
            logging.error(f"Validation failed for {url}: {e}")
            continue
        reachable.append(candidate)

    # Stage 1.5 — location gate. Page text is fetched once here and reused by
    # the validation call below.
    in_range = []
    for candidate in reachable:
        page_text = candidate.get("_page_text") or fetch_page_text(candidate["url"])
        candidate["_page_text"] = page_text
        ok, reason = location_verdict(candidate.get("location", ""), page_text)
        if not ok and not page_location(page_text):
            ok, reason = location_verdict(
                candidate.get("location", ""), visible_page_text(candidate["url"])
            )
        if not ok:
            logging.error(f"SKIP (location — {reason}): {candidate['url']}")
            print(f"  SKIP (location — {reason}): {candidate.get('company')}")
            continue
        candidate["location"] = page_location(page_text) or candidate.get("location", "")
        in_range.append(candidate)
    if reachable:
        print(f"  In range: {len(in_range)}/{len(reachable)} (location filter)")

    # Stage 1.6 — relevance gate. Both sources land here: JobTech candidates are
    # merged into raw_candidates above, so this covers them too. Runs before the
    # batched Claude call so an unwinnable role costs nothing to reject.
    relevant = []
    for candidate in in_range:
        page_text = candidate.get("_page_text") or ""
        dead, dead_reason = relevance.is_dead_ad(page_text)
        if dead:
            logging.error(f"SKIP (dead — {dead_reason}): {candidate['url']}")
            print(f"  SKIP (dead — {dead_reason}): {candidate.get('company')}")
            continue
        ok, reason = relevance.relevance_verdict(
            candidate.get("role", ""), candidate.get("company", ""), page_text
        )
        if not ok:
            logging.error(f"SKIP (relevance — {reason}): {candidate['url']}")
            print(f"  SKIP (relevance — {reason}): {candidate.get('company')}")
            continue
        relevant.append(candidate)
    if in_range:
        print(f"  Relevant: {len(relevant)}/{len(in_range)} (relevance filter)")
    in_range = relevant

    # Stage 2 — batched quality validation
    new_jobs = []
    if in_range:
        print(f"  Validating {len(in_range)} reachable URL(s) in one call...")
        verdicts = batch_validate_urls(in_range, val_skill)
        validation_errors = 0
        for candidate in in_range:
            url = candidate.get("url", "").strip()
            verdict, reason = verdicts.get(url, ("uncertain", "not in response"))
            if verdict == "valid":
                print(f"  NEW: {candidate.get('company')} — {candidate.get('role')}")
                new_jobs.append(candidate)
            else:
                if reason.startswith("validation error"):
                    validation_errors += 1
                logging.error(f"URL rejected [{verdict}] ({reason}): {url}")
                print(f"  SKIP ({verdict} — {reason[:60]}): {url}")
        if validation_errors:
            run_errors.append(f"validation call failed for {validation_errors} of "
                              f"{len(in_range)} candidate(s)")

    # Save results
    for job in new_jobs:
        for key in [k for k in job if k.startswith("_")]:
            job.pop(key)

    results = {
        "timestamp":   datetime.now().isoformat(),
        "new_jobs":    new_jobs,
        "closed_jobs": closed_jobs,
        "stats": {
            "web_candidates":     web_candidate_count,
            "jobtech_candidates": jobtech_candidate_count,
            "reachable":          len(reachable),
            "in_range":           len(in_range),
            "validated":          len(new_jobs),
        },
        "errors": run_errors,
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
