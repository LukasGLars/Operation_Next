"""Digest reporting — a broken run must not read like a quiet week."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.mailer import build_body, build_subject, stale_warning  # noqa: E402

JOB = {"company": "SEVR", "role": "Customer Success", "url": "https://x.se/jobs/1"}
STATS = {"web_candidates": 4, "jobtech_candidates": 30, "reachable": 28,
         "in_range": 26, "validated": 3}


def test_errors_dominate_the_subject():
    subject = build_subject([JOB], [], ["web search pass 'ATS-targeted' failed: 429"])
    assert "FEL I PIPELINE" in subject


def test_quiet_run_says_so_instead_of_going_silent():
    subject = build_subject([], [], [])
    assert "inga nya roller" in subject
    body = build_body([], [], STATS, [])
    assert "utan fel" in body


def test_new_roles_keep_the_count_in_the_subject():
    assert "1 nya roller" in build_subject([JOB], [], [])


def test_body_explains_that_zero_may_be_a_failure():
    body = build_body([], [], STATS, ["JobTech source failed: timeout"])
    assert "JobTech source failed: timeout" in body
    assert "inte på att marknaden är tom" in body


def test_body_reports_every_stage_count():
    body = build_body([], [], STATS, [])
    for value in ("4", "30", "28", "26", "3"):
        assert value in body
    assert "Kandidater från Platsbanken" in body


def test_stale_results_are_flagged():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert "kan ha kraschat" in stale_warning(f"{yesterday}T05:03:11")
    assert stale_warning(f"{date.today().isoformat()}T05:03:11") == ""
    assert "saknar timestamp" in stale_warning("")
