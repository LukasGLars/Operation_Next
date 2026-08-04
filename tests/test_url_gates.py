"""URL gates in search.py that JobTech candidates rely on."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.search import _is_generic_landing, _url_looks_specific  # noqa: E402


def test_careers_hub_is_rejected():
    assert _is_generic_landing("https://www.heysid.com/careers")
    assert _is_generic_landing("https://foretag.se/lediga-jobb/")


def test_posting_url_is_not_a_hub():
    assert not _is_generic_landing("https://nexergroup.teamtailor.com/jobs/8039554-business-analyst")
    assert not _is_generic_landing("https://apply.recman.page/job_post.php?id=482070")
    # A hub path with a role id in the query string still points at one posting
    assert not _is_generic_landing("https://thomasbetong.se/karriar/lediga-tjanster/?rmpId=615274")


def test_query_string_ids_fail_the_strict_shape_check():
    """Why JobTech candidates skip _url_looks_specific: real apply URLs carry the
    id in the query, which that heuristic cannot see."""
    assert not _url_looks_specific("https://pnty-apply.ponty-system.se/cilbuper?id=555")
    assert _url_looks_specific("https://nexergroup.teamtailor.com/jobs/8039554-business-analyst")
