"""Location filter — the gate that keeps out-of-range roles out of the pipeline.

Run: python -m pytest tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.search import location_verdict, page_location  # noqa: E402


def page(city="", body="", remote=""):
    """Mimic what fetch_page_text() returns for a JSON-LD posting."""
    parts = ["Title: Business Analyst", "Company: Acme AB"]
    if city:
        parts.append(f"Location: {city}")
    if body:
        parts.append(f"Description:\n{body}")
    if remote:
        parts.append(f"Remote status: {remote}")
    return "\n\n".join(parts)


def test_rejects_onsite_role_far_away():
    ok, reason = location_verdict("Umeå", page("Umeå"))
    assert not ok
    assert "Umeå" in reason


def test_rejects_hybrid_role_far_away():
    """Hybrid in Umeå still means being in Umeå most of the week."""
    ok, reason = location_verdict("Umeå", page("Umeå", remote="Hybridarbete"))
    assert not ok
    assert "hybrid" in reason


def test_accepts_fully_remote_role_far_away():
    ok, _ = location_verdict("Umeå", page("Umeå", remote="Fully remote"))
    assert ok


def test_accepts_remote_first_wording_without_usable_city():
    """Alight: 'Multiple locations', tagged Hybrid, remote-first from anywhere."""
    ok, _ = location_verdict(
        "", page("Multiple locations", "You can work remote-first from anywhere in Europe!", "Hybrid")
    )
    assert ok


def test_accepts_hybrid_when_office_is_commutable():
    ok, _ = location_verdict("", page("Göteborg", remote="Hybridarbete"))
    assert ok


def test_accepts_role_within_commute():
    ok, _ = location_verdict("Göteborg", page("Göteborg"))
    assert ok


def test_page_location_overrides_model_guess():
    """The search model claims Göteborg, the ad says Umeå — the ad wins."""
    ok, reason = location_verdict("Göteborg", page("Umeå"))
    assert not ok
    assert "Umeå" in reason


def test_rejects_unknown_location():
    ok, reason = location_verdict("", page())
    assert not ok
    assert "no location" in reason


def test_hybrid_cloud_in_body_does_not_pass_onsite_role():
    ok, _ = location_verdict("Stockholm", page("Stockholm", "Du arbetar med hybrid cloud och remote sensing."))
    assert not ok


def test_remote_tag_in_location_field_passes():
    ok, _ = location_verdict("Stockholm (Remote)", page("Stockholm (Remote)"))
    assert ok


def test_hybrid_tag_in_page_chrome_passes_when_jsonld_has_no_location():
    """Teamtailor fallback path: no Location: line, hybrid tagged in the chrome."""
    ok, _ = location_verdict("", "Novacura IFS Solution Architect Göteborg Hybridarbete Ansök nu")
    assert ok


def test_blank_location_line_is_not_read_as_next_field():
    assert page_location("Location: \n\nDescription:\nWe are hiring") == ""


def test_page_location_reads_jsonld_line():
    assert page_location(page("Mölndal")) == "Mölndal"
    assert page_location("no structured data here") == ""
