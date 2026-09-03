"""Platsbanken hands out Teamtailor apply-form deep links
(.../applications/new?promotion=...). That page has the cookie banner and the
form fields but no ad text, so a draft generated from it is written off the job
title alone. Fetching must fall back to the parent /jobs/<slug> page."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.app import _ad_page_url  # noqa: E402


def test_strips_teamtailor_apply_form():
    assert _ad_page_url(
        "https://karriar.arenapersonal.com/jobs/8047922-sales-engineer-till-wam-scandinavia"
        "/applications/new?promotion=2141244-arbetsformedlingen"
    ) == "https://karriar.arenapersonal.com/jobs/8047922-sales-engineer-till-wam-scandinavia"


def test_leaves_plain_job_page_alone():
    url = "https://karriar.poolia.se/jobs/8261281-senior-strategisk-inkopare"
    assert _ad_page_url(url) == url


def test_leaves_other_ats_alone():
    """recman's ?apply_only is a query flag on the ad itself, not a separate page."""
    url = "https://sibeconstruction.recman.page/job/485833?path=ams&apply_only"
    assert _ad_page_url(url) == url


def test_leaves_platsbanken_alone():
    url = "https://arbetsformedlingen.se/platsbanken/annonser/31342433"
    assert _ad_page_url(url) == url


def test_does_not_match_slug_containing_applications():
    """Only the /applications/new segment is an apply form; a slug that merely
    contains the word is still the ad page."""
    url = "https://example.teamtailor.com/jobs/123-applications-engineer"
    assert _ad_page_url(url) == url
