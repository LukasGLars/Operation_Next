"""Candidates from Arbetsförmedlingen's open JobSearch API (jobtechdev.se).

The Claude web search only reaches ads it can find on ATS platforms. This module
reaches what employers publish to Platsbanken, which is most of the Swedish
market and was previously invisible to the pipeline: arbetsformedlingen.se is
blocked as an aggregator — correctly, for scraping — but the API returns
structured data, so nothing is scraped and no location has to be guessed.

Two things about the data are worth knowing:

- Platsbanken's own ad pages are rendered client side. Fetching one returns a
  cookie notice and nothing else, so the employer's apply URL is used instead,
  normalised to the canonical posting page where the ATS path carries the job id.
- The `remote_work` flag does not distinguish hybrid from fully remote. Since a
  hybrid role outside commuting range is not usable, no remote status is
  synthesised here — the ad text is passed through and `location_verdict()` in
  search.py stays the single place that decides.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date

import anthropic
import requests

SEARCH_API = "https://jobsearch.api.jobtechdev.se/search"
MODEL = "claude-sonnet-4-6"
PER_QUERY_LIMIT = 25
MAX_CANDIDATES = 30

# Municipality concept ids for the commutable ring in search.py. Filtering server
# side keeps responses small, and localities are covered by their municipality —
# Mölnlycke by Härryda, Sävedalen by Partille, Älvängen by Ale.
COMMUTABLE_MUNICIPALITY_IDS = {
    "alingsås":   "UQ75_1eU_jaC",
    "göteborg":   "PVZL_BQT_XtL",
    "mölndal":    "mc45_ki9_Bv3",
    "partille":   "CCiR_sXa_BVW",
    "lerum":      "yHV7_2Y6_zQx",
    "härryda":    "dzWW_R3G_6Eh",
    "ale":        "17Ug_Btv_mBr",
    "bollebygd":  "ypAQ_vTD_KLU",
    "borås":      "TpRZ_bFL_jhL",
    "lilla edet": "YQcE_SNB_Tv3",
    "vårgårda":   "NfFx_5jj_ogg",
}

# One query per role family in search_skill.md's include list. Quoted, because
# free text matches every term separately: an unquoted "product specialist"
# returns 271 hits including "HR-specialist" and "Legitimerad Läkare", a quoted
# one returns 2.
ROLE_QUERIES = [
    '"business analyst"',
    '"affärsanalytiker"',
    '"affärsutvecklare"',
    '"teknisk säljare"',
    '"sales engineer"',
    '"customer success"',
    '"solutions engineer"',
    '"implementation consultant"',
    '"data analyst"',
    '"product specialist"',
    '"entreprenadingenjör"',
    '"kalkylingenjör"',
    '"inköpare"',
]

# The role has to be named in the headline or the taxonomy occupation, not merely
# mentioned somewhere in the ad text. Without this, a passing reference to
# "business analysis" pulls in dentists and babysitters.
_ROLE_INCLUDE = re.compile(
    r"(business analyst|affärsanalytiker|affärsutveckl|business develop|"
    r"teknisk säljare|technical sales|sales engineer|säljingenjör|"
    r"solutions? engineer|solutions? architect|solution consultant|"
    r"implementation|implementer|customer success|"
    r"data analyst|dataanalytiker|analytiker|"
    r"product specialist|produktspecialist|product owner|"
    r"entreprenadingenjör|kalkylingenjör|projekteringsingenjör|"
    r"inköpare|upphandlare|procurement|sourcing|"
    r"verksamhetsutveckl|processutveckl|automation)",
    re.I,
)

# Cheap deterministic pass over the exclude rules. The judge call below handles
# the ones that need reading — "requires consulting background" and the like.
_HEADLINE_EXCLUDE = re.compile(
    r"(kundservice|kundtjänst|customer service|helpdesk|help desk|service desk|"
    r"telefonförsäljare|telemarketing|innesäljare|butikssäljare|butikschef|"
    r"receptionist|lärare|forskare|doktorand|professor|sjuksköterska|undersköterska|"
    r"\bsdr\b|\bbdr\b|sales development representative|"
    r"business development representative|"
    r"\bintern\b|internship|praktikant|praktikplats|examensarbete|"
    r"sommarjobb|feriejobb)",
    re.I,
)
_EMPLOYER_EXCLUDE = re.compile(r"(kpmg|accenture|mckinsey|boston consulting|\bbcg\b)", re.I)

# Hosts whose path carries the job id, so query parameters can be dropped to get
# the canonical posting page. Elsewhere the id often lives in the query string.
_PATH_ID_HOSTS = re.compile(
    r"(teamtailor\.com|jobylon\.com|greenhouse\.io|lever\.co|workable\.com|"
    r"smartrecruiters\.com|karriar\.[a-z0-9-]+\.se)",
    re.I,
)


def _search(query, remote=False, limit=PER_QUERY_LIMIT):
    params = {"q": query, "limit": limit, "sort": "pubdate-desc"}
    if remote:
        params["remote"] = "true"
    else:
        params["municipality"] = list(COMMUTABLE_MUNICIPALITY_IDS.values())
    r = requests.get(SEARCH_API, params=params, timeout=25,
                     headers={"accept": "application/json"})
    r.raise_for_status()
    return r.json().get("hits", [])


def canonical_url(hit):
    """The employer's apply URL, normalised to the posting page when possible.
    Empty when the ad is applied to through Arbetsförmedlingen — there is no
    employer page to fetch, so the role cannot support document generation."""
    url = ((hit.get("application_details") or {}).get("url") or "").strip()
    if not url:
        return ""
    if _PATH_ID_HOSTS.search(url):
        url = url.split("?")[0]
        url = re.sub(r"/applications?/new/?$", "", url)
    return url


def is_relevant(hit):
    headline   = hit.get("headline") or ""
    employer   = (hit.get("employer") or {}).get("name") or ""
    occupation = (hit.get("occupation") or {}).get("label") or ""
    if _HEADLINE_EXCLUDE.search(headline) or _EMPLOYER_EXCLUDE.search(employer):
        return False
    return bool(_ROLE_INCLUDE.search(headline) or _ROLE_INCLUDE.search(occupation))


def page_text(hit):
    """The same shape fetch_page_text() produces, so the location gate and the
    validation call in search.py need no special case for these candidates."""
    address = hit.get("workplace_address") or {}
    parts = [
        f"Title: {hit.get('headline', '')}",
        f"Company: {(hit.get('employer') or {}).get('name', '')}",
    ]
    if address.get("municipality"):
        parts.append(f"Location: {address['municipality']}")
    description = ((hit.get("description") or {}).get("text") or "")[:2500]
    if description:
        parts.append(f"Description:\n{description}")
    if hit.get("publication_date"):
        parts.append(f"Posted: {hit['publication_date'][:10]}")
    return "\n\n".join(parts)


def as_candidate(hit):
    """Shape a hit like the search model's output, or None if unusable."""
    url = canonical_url(hit)
    if not url:
        return None
    address = hit.get("workplace_address") or {}
    return {
        "company":    (hit.get("employer") or {}).get("name", ""),
        "role":       hit.get("headline", ""),
        "role_type":  (hit.get("occupation") or {}).get("label", ""),
        "url":        url,
        "location":   address.get("municipality", ""),
        "status":     "Identifierad",
        "date_added": date.today().isoformat(),
        "_page_text": page_text(hit),
        "_posted":    hit.get("publication_date", ""),
        "_source":    "jobtech",
    }


def fetch_candidates(known_urls=(), max_candidates=MAX_CANDIDATES, location_ok=None):
    """Newest first, capped. Runs each role query over the commutable
    municipalities and again with the remote filter.

    `location_ok(location, page_text) -> (bool, reason)` is search.py's location
    gate, injected to avoid an import cycle. It runs before the cap: the remote
    pass searches nationwide, so without it a run's cap fills with Stockholm ads
    that the gate would reject downstream anyway.
    """
    seen = set(known_urls)
    seen_roles = set()          # same role re-advertised under a second ad id
    found = []
    rejected = 0
    for query in ROLE_QUERIES:
        for remote in (False, True):
            try:
                hits = _search(query, remote=remote)
            except Exception as e:
                logging.error(f"jobtech search failed ({query}, remote={remote}): {e}")
                continue
            for hit in hits:
                if not is_relevant(hit):
                    continue
                candidate = as_candidate(hit)
                if not candidate or candidate["url"] in seen:
                    continue
                role_key = (candidate["company"].lower(), candidate["role"].lower())
                if role_key in seen_roles:
                    continue
                seen.add(candidate["url"])
                seen_roles.add(role_key)
                if location_ok:
                    ok, reason = location_ok(candidate["location"], candidate["_page_text"])
                    if not ok:
                        logging.error(f"jobtech location reject ({reason}): {candidate['url']}")
                        rejected += 1
                        continue
                found.append(candidate)

    if rejected:
        print(f"  JobTech: {rejected} candidate(s) rejected on location")
    found.sort(key=lambda c: c.get("_posted", ""), reverse=True)
    if len(found) > max_candidates:
        print(f"  JobTech: capping {len(found)} candidates at {max_candidates} (newest first)")
        logging.error(f"jobtech cap: dropped {len(found) - max_candidates} candidate(s)")
        found = found[:max_candidates]
    return found


def judge_fit(candidates, skill_content):
    """One batched Claude call applying the role filters. Returns the keepers.
    Without a key or a skill file the candidates pass through — the URL
    validation stage still runs on them."""
    if not candidates:
        return []
    if not skill_content or not os.environ.get("ANTHROPIC_API_KEY"):
        logging.error("jobtech judge_fit skipped — no skill content or no API key")
        return candidates

    items = "\n\n".join(
        f"--- {i + 1} ---\nCompany: {c['company']}\nRole: {c['role']}\n"
        f"Occupation: {c['role_type']}\nLocation: {c['location']}\n"
        f"{c['_page_text'][:900]}"
        for i, c in enumerate(candidates)
    )
    prompt = (
        f"Judge each of the following {len(candidates)} roles against the role "
        "filters. A role fits only if it matches an include keyword and breaks no "
        "exclude rule. Prefer precision over recall.\n\n"
        f"{items}\n\n"
        "Return a JSON array with one object per role in the same order:\n"
        '[{"index": 1, "fit": true, "cv_base": "CV_Einride", "reason": "..."}]'
    )

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=skill_content,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError(f"no JSON array in response: {text[:200]}")
        verdicts = {v.get("index"): v for v in json.loads(match.group())}
    except Exception as e:
        logging.error(f"jobtech judge_fit failed: {e}")
        return candidates

    kept = []
    for i, candidate in enumerate(candidates, 1):
        verdict = verdicts.get(i)
        if verdict and not verdict.get("fit", True):
            print(f"  SKIP (role fit — {str(verdict.get('reason', ''))[:60]}): "
                  f"{candidate['company']} — {candidate['role'][:40]}")
            continue
        if verdict and verdict.get("cv_base"):
            candidate["cv_base"] = verdict["cv_base"]
        kept.append(candidate)
    return kept
