"""Expiry and the ad/apply URL split in joblist.md.

Two columns were added alongside URL rather than repointing it: URL is the
identity key for dedup, rejected.md and status updates, so its meaning has to
stay put. Annons is what the list links; URL is what you apply through.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.updater import close_expired, parse_table, write_table  # noqa: E402


def _row(**overrides):
    row = {
        "#": "1", "Företag": "cilbuper IT AB", "Roll/Typ": "Business Analyst",
        "Plats": "Göteborg", "CV-bas": "CV_Einride", "Status": "Identifierad",
        "Datum": "2026-08-26", "Deadline": "2026-08-03",
        "Annons": "https://arbetsformedlingen.se/platsbanken/annonser/31231122",
        "URL": "https://pnty-apply.ponty-system.se/cilbuper?id=555",
    }
    row.update(overrides)
    return row


def test_both_urls_survive_a_roundtrip():
    rows, has_datum = parse_table(write_table([_row()]).splitlines())
    assert has_datum
    assert rows[0]["Annons"].endswith("/annonser/31231122")
    assert rows[0]["URL"].endswith("?id=555")
    assert rows[0]["Deadline"] == "2026-08-03"


def test_rows_written_before_the_columns_existed_stay_parseable():
    """Old rows have neither column; they must render as empty, not shift the
    URL out of alignment into the wrong cell."""
    legacy = {"#": "1", "Företag": "Acme", "URL": "https://x.se/jobs/1"}
    rows, _ = parse_table(write_table([legacy]).splitlines())
    assert rows[0]["Deadline"] == ""
    assert rows[0]["Annons"] == ""
    assert rows[0]["URL"] == "https://x.se/jobs/1"


def test_url_column_is_still_the_last_column():
    """rejected.md and the app both read URL positionally in places."""
    header = write_table([_row()]).splitlines()[0]
    assert header.split("|")[-2].strip() == "URL"


def test_row_past_its_deadline_is_closed():
    rows = [_row(Deadline="2026-08-03")]
    assert close_expired(rows, today="2026-08-31") == 1
    assert rows[0]["Status"] == "Stängd"
    assert rows[0]["Datum"] == "2026-08-31", "resets the clock for the 30-day prune"


def test_closing_day_is_not_yet_expired():
    rows = [_row(Deadline="2026-08-31")]
    assert close_expired(rows, today="2026-08-31") == 0
    assert rows[0]["Status"] == "Identifierad"


def test_blank_deadline_is_left_alone():
    """Rows predating the column have nothing to judge — an unknown deadline is
    not an expired one."""
    rows = [_row(Deadline="")]
    assert close_expired(rows, today="2026-08-31") == 0
    assert rows[0]["Status"] == "Identifierad"


def test_already_closed_rows_are_not_retouched():
    """Otherwise Datum would be bumped on every run and the 30-day prune could
    never reach the row."""
    rows = [_row(Deadline="2026-08-03", Status="Stängd", Datum="2026-08-04")]
    assert close_expired(rows, today="2026-08-31") == 0
    assert rows[0]["Datum"] == "2026-08-04"
