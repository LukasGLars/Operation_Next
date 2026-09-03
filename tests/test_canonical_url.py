"""The same posting reaches the list under several addresses — apply form or ad
page, with or without a promotion/utm tag, http/https, www or not. Rejection and
duplicate checks compare canonical form, or a re-advertised job slips back in."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.app import canonical_url as app_canon  # noqa: E402
from pipeline.updater import canonical_url as pipeline_canon  # noqa: E402

EQUIVALENT = [
    # apply form vs ad page — what Platsbanken hands out vs what the ad lives at
    ("https://karriar.arenapersonal.com/jobs/8047922-sales-engineer/applications/new"
     "?promotion=2141244-arbetsformedlingen",
     "https://karriar.arenapersonal.com/jobs/8047922-sales-engineer"),
    # a fresh promotion tag on a re-listed ad
    ("https://jobb.oddwork.se/jobs/8031694-teknisk-saljare?promotion=2090960-af",
     "https://jobb.oddwork.se/jobs/8031694-teknisk-saljare?promotion=9999999-af"),
    # scheme, www and trailing slash
    ("http://www.example.com/jobs/12/", "https://example.com/jobs/12"),
    # utm noise
    ("https://example.com/jobs/12?utm_source=li&utm_campaign=x",
     "https://example.com/jobs/12"),
]


def test_equivalent_urls_share_a_canonical_form():
    for a, b in EQUIVALENT:
        assert app_canon(a) == app_canon(b), (a, b)


def test_distinct_postings_stay_distinct():
    assert app_canon("https://example.com/jobs/12") != app_canon("https://example.com/jobs/13")


def test_meaningful_query_is_kept():
    """recman puts the job id in a query parameter, so stripping the query
    wholesale would collapse every recman posting onto one key."""
    a = app_canon("https://sibeconstruction.recman.page/job/485833?path=ams")
    b = app_canon("https://sibeconstruction.recman.page/job/999999?path=ams")
    assert a != b
    assert "path=ams" in a


def test_aplitrak_adid_is_not_collapsed():
    """Documents the known limit: adid is opaque, so two sightings of one job
    look like two jobs. The company+role key is what catches those."""
    assert app_canon("https://www.aplitrak.com/?adid=AAA") != \
        app_canon("https://www.aplitrak.com/?adid=BBB")


def test_empty_url():
    assert app_canon("") == ""


def test_both_copies_agree():
    for a, b in EQUIVALENT:
        assert app_canon(a) == pipeline_canon(a)
        assert app_canon(b) == pipeline_canon(b)
