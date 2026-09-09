"""JobTech source — shaping Platsbanken ads into pipeline candidates.

The fixture is a real recorded API response (tests/fixtures/jobtech_search.json),
trimmed to the fields the pipeline reads. No network access.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import jobtech  # noqa: E402
from pipeline.search import location_verdict, page_location  # noqa: E402

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "jobtech_search.json").read_text(encoding="utf-8")
)
HITS = FIXTURE["hits"]


def hit_by_employer(name):
    return next(h for h in HITS if (h["employer"] or {}).get("name") == name)


def test_teamtailor_apply_url_normalises_to_posting_page():
    raw = (hit_by_employer("Nexer AB")["application_details"] or {})["url"]
    assert "/applications/new" in raw and "?promotion=" in raw

    url = jobtech.canonical_url(hit_by_employer("Nexer AB"))
    assert url.startswith("https://nexergroup.teamtailor.com/jobs/8039554-")
    assert "/applications/new" not in url
    assert "?" not in url


def test_query_string_id_is_preserved():
    """recman and ponty carry the job id in the query — stripping it breaks the link."""
    for employer in ("NXT Interim Göteborg AB", "cilbuper IT AB"):
        assert "id=" in jobtech.canonical_url(hit_by_employer(employer))


def test_candidate_links_the_ad_not_the_apply_form():
    """The two URLs are different jobs: `url` is fetched by the pipeline and
    applied through, `ad_url` is what a human opens to read the ad. Collapsing
    them is what made the joblist open bare application forms."""
    candidate = jobtech.as_candidate(hit_by_employer("cilbuper IT AB"))
    assert candidate["url"] == "https://pnty-apply.ponty-system.se/cilbuper?id=555"
    assert candidate["ad_url"] == "https://arbetsformedlingen.se/platsbanken/annonser/31231122"


def test_ad_url_is_empty_when_the_hit_has_no_webpage():
    hit = dict(hit_by_employer("Nexer AB"))
    hit["webpage_url"] = None
    assert jobtech.ad_url(hit) == ""


def test_deadline_is_truncated_to_a_date():
    assert jobtech.deadline({"application_deadline": "2026-09-12T23:59:59"}) == "2026-09-12"
    assert jobtech.deadline({"application_deadline": None}) == ""
    assert jobtech.deadline({}) == ""


def test_expired_and_withdrawn_ads_are_not_open():
    today = "2026-08-31"
    assert jobtech.is_open({"application_deadline": "2026-09-12T23:59:59"}, today)
    assert jobtech.is_open({"application_deadline": "2026-08-31T23:59:59"}, today),         "the closing day itself is still open"
    assert not jobtech.is_open({"application_deadline": "2026-08-03T23:59:59"}, today)
    assert not jobtech.is_open({"removed": True}, today)


def test_missing_deadline_counts_as_open():
    """Absence is not evidence of expiry — dropping these would lose every ad
    that never set a deadline."""
    assert jobtech.is_open({}, "2026-08-31")
    assert jobtech.is_open({"application_deadline": None}, "2026-08-31")


def test_fetch_candidates_drops_expired_hits(monkeypatch):
    live = hit_by_employer("Nexer AB")
    stale = json.loads(json.dumps(hit_by_employer("cilbuper IT AB")))
    stale["application_deadline"] = "2020-01-01T23:59:59"
    monkeypatch.setattr(jobtech, "OCCUPATION_GROUPS", {})
    monkeypatch.setattr(jobtech, "ROLE_QUERIES", ['"business analyst"'])
    monkeypatch.setattr(jobtech, "_search", lambda query, remote=False, limit=25: [live, stale])

    urls = [c["url"] for c in jobtech.fetch_candidates()]
    assert urls == [jobtech.canonical_url(live)]


def test_candidate_carries_structured_location():
    candidate = jobtech.as_candidate(hit_by_employer("Nexer AB"))
    assert candidate["location"] == "Göteborg"
    assert candidate["_source"] == "jobtech"
    assert candidate["company"] == "Nexer AB"


def test_page_text_is_readable_by_the_location_gate():
    """The gate must work on JobTech text without a special case."""
    candidate = jobtech.as_candidate(hit_by_employer("Nexer AB"))
    assert page_location(candidate["_page_text"]) == "Göteborg"
    ok, reason = location_verdict(candidate["location"], candidate["_page_text"])
    assert ok
    assert "commute" in reason


def test_no_remote_status_is_synthesised():
    """remote_work does not distinguish hybrid from fully remote, so the module
    must not claim either — otherwise a far-away hybrid would pass the gate."""
    for hit in HITS:
        assert "Remote status:" not in jobtech.as_candidate(hit)["_page_text"]


def test_ad_without_apply_url_is_dropped():
    hit = dict(hit_by_employer("Nexer AB"))
    hit["application_details"] = {"url": None, "via_af": True}
    assert jobtech.canonical_url(hit) == ""
    assert jobtech.as_candidate(hit) is None


def test_support_and_consulting_roles_are_excluded():
    def make(headline, employer="Acme AB"):
        return {"headline": headline, "employer": {"name": employer}}

    assert not jobtech.is_relevant(make("Kundservicemedarbetare"))
    assert not jobtech.is_relevant(make("Helpdesk Technician"))
    assert not jobtech.is_relevant(make("Sales Development Representative"))
    assert not jobtech.is_relevant(make("Business Analyst", employer="Accenture AB"))
    assert jobtech.is_relevant(make("Business Analyst"))
    assert jobtech.is_relevant(make("Teknisk säljare"))


def test_fetch_candidates_skips_known_urls(monkeypatch):
    monkeypatch.setattr(jobtech, "OCCUPATION_GROUPS", {})
    monkeypatch.setattr(jobtech, "ROLE_QUERIES", ["business analyst"])
    monkeypatch.setattr(jobtech, "_search", lambda query, remote=False, limit=25: HITS)
    known = [jobtech.canonical_url(hit_by_employer("Nexer AB"))]

    all_candidates = jobtech.fetch_candidates()
    filtered = jobtech.fetch_candidates(known_urls=known)

    assert len(filtered) == len(all_candidates) - 1
    assert known[0] not in [c["url"] for c in filtered]


def test_fetch_candidates_caps_and_sorts_newest_first(monkeypatch):
    monkeypatch.setattr(jobtech, "OCCUPATION_GROUPS", {})
    monkeypatch.setattr(jobtech, "ROLE_QUERIES", ["business analyst"])
    monkeypatch.setattr(jobtech, "_search", lambda query, remote=False, limit=25: HITS)

    capped = jobtech.fetch_candidates(max_candidates=2)
    assert len(capped) == 2
    assert capped[0]["_posted"] >= capped[1]["_posted"]


def test_off_topic_roles_are_excluded():
    """Free-text search returns anything mentioning the words — the role has to be
    named in the headline or the occupation taxonomy."""
    def make(headline, occupation=""):
        return {"headline": headline, "employer": {"name": "Acme AB"},
                "occupation": {"label": occupation}}

    assert not jobtech.is_relevant(make("Legitimerad Läkare"))
    assert not jobtech.is_relevant(make("HR-specialist till rekryteringsenheten"))
    assert not jobtech.is_relevant(make("myNanny barnvakt Gråbo"))
    assert not jobtech.is_relevant(make("Customer Success Intern"))
    assert jobtech.is_relevant(make("Affärsutvecklare till dormakaba"))
    assert jobtech.is_relevant(make("Okänd titel", occupation="Affärsanalytiker/Business analyst"))


def test_same_role_advertised_twice_is_deduplicated(monkeypatch):
    hit = hit_by_employer("Nexer AB")
    twin = json.loads(json.dumps(hit))
    twin["application_details"]["url"] = "https://nexergroup.teamtailor.com/jobs/9999999-other-id"
    monkeypatch.setattr(jobtech, "OCCUPATION_GROUPS", {})
    monkeypatch.setattr(jobtech, "ROLE_QUERIES", ['"business analyst"'])
    monkeypatch.setattr(jobtech, "_search", lambda query, remote=False, limit=25: [hit, twin])

    assert len(jobtech.fetch_candidates()) == 1


def test_location_gate_runs_before_the_cap(monkeypatch):
    """Otherwise the nationwide remote pass fills the cap with roles the gate
    would reject downstream anyway."""
    monkeypatch.setattr(jobtech, "OCCUPATION_GROUPS", {})
    monkeypatch.setattr(jobtech, "ROLE_QUERIES", ['"business analyst"'])
    monkeypatch.setattr(jobtech, "_search", lambda query, remote=False, limit=25: HITS)

    rejecting = jobtech.fetch_candidates(location_ok=lambda loc, text: (False, "too far"))
    assert rejecting == []

    accepting = jobtech.fetch_candidates(location_ok=lambda loc, text: (True, "fine"))
    assert accepting


def test_judge_fit_passes_through_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    candidates = [jobtech.as_candidate(hit_by_employer("Nexer AB"))]
    assert jobtech.judge_fit(candidates, "role filters here") == candidates


def _hit(headline, employer="Acme AB"):
    return {"headline": headline, "employer": {"name": employer}}


def test_group_hits_skip_the_headline_role_requirement():
    """The occupation group is the relevance signal. "Regionsäljare" carries no
    _ROLE_INCLUDE word and is exactly the kind of ad the group sweep is for."""
    hit = _hit("Regionsäljare")
    assert not jobtech.is_relevant(hit)
    assert jobtech.is_relevant(hit, from_group=True)


def test_group_hits_still_obey_every_exclude():
    assert not jobtech.is_relevant(_hit("Kundservicemedarbetare"), from_group=True)
    assert not jobtech.is_relevant(_hit("Business Analyst", employer="Accenture AB"),
                                   from_group=True)


def test_churn_sales_is_filtered_out_of_the_group():
    """Företagssäljare holds door-knocking and commission churn alongside the
    real technical sales roles, and those ads ask a question instead of naming
    a job — so only a headline filter catches them."""
    for headline in ["Är du redo att ta plats som säljare i Bollebygd?",
                     "Vill du utvecklas, tävla och tjäna bra?",
                     "Ta nästa steg i din utveckling inom försäljning",
                     "Säljare sökes — inga förkunskaper krävs"]:
        assert not jobtech.is_relevant(_hit(headline), from_group=True), headline
    for headline in ["Account Manager / Sales Specialist – Project Sales",
                     "Teknisk säljare till Heidelberg Materials",
                     "Regionsäljare"]:
        assert jobtech.is_relevant(_hit(headline), from_group=True), headline


def test_teamtailor_apply_form_is_trimmed_on_a_customer_domain():
    """jobb.karisma.se is Teamtailor on the customer's own domain, so the host
    list misses it and the apply form — which has no ad text — is what gets
    fetched. That read as a withdrawn posting and closed a live row."""
    hit = {"application_details": {"url":
        "https://jobb.karisma.se/jobs/7597765-teknisk-saljare-proav"
        "/applications/new?promotion=1954684-arbetsformedlingen"}}
    assert jobtech.canonical_url(hit) ==         "https://jobb.karisma.se/jobs/7597765-teknisk-saljare-proav"


def test_group_sweep_runs_alongside_the_role_queries(monkeypatch):
    monkeypatch.setattr(jobtech, "ROLE_QUERIES", ['"business analyst"'])
    monkeypatch.setattr(jobtech, "OCCUPATION_GROUPS", {"Företagssäljare": "oXSW_fbY_XrY"})
    monkeypatch.setattr(jobtech, "_search",
                        lambda q, remote=False, limit=25: [hit_by_employer("Nexer AB")])
    monkeypatch.setattr(jobtech, "_search_group",
                        lambda g, remote=False, limit=100: [hit_by_employer("cilbuper IT AB")])
    companies = {c["company"] for c in jobtech.fetch_candidates()}
    assert companies == {"Nexer AB", "cilbuper IT AB"}
