# -*- coding: utf-8 -*-
"""recheck_dead_ads — liveness for rows already in the joblist."""
from pipeline.updater import recheck_dead_ads

DEAD = "Jobbannonsen är inte längre aktiv. Antingen är jobbet tillsatt. " * 10
LIVE = "Vi söker en teknisk säljare till vårt team i Göteborg. " * 20


def row(n, status, url):
    return {"#": n, "Företag": "X", "Roll/Typ": "Y", "Status": status,
            "Datum": "2026-01-01", "URL": url}


def fetch_map(mapping):
    return lambda url: mapping[url]


def test_dead_identifierad_row_is_closed():
    rows = [row("1", "Identifierad", "a")]
    assert recheck_dead_ads(rows, fetch_map({"a": DEAD}), today="2026-09-02") == 1
    assert rows[0]["Status"] == "Stängd"
    assert rows[0]["Datum"] == "2026-09-02"


def test_live_row_untouched():
    rows = [row("1", "Identifierad", "a")]
    assert recheck_dead_ads(rows, fetch_map({"a": LIVE})) == 0
    assert rows[0]["Status"] == "Identifierad"


def test_applied_and_interview_rows_are_never_closed():
    # A pulled ad is the expected state once you are in a process — closing on
    # it would delete exactly the rows that matter most.
    rows = [row("1", "Ansökt", "a"), row("2", "Intervju", "b")]
    assert recheck_dead_ads(rows, fetch_map({"a": DEAD, "b": DEAD})) == 0
    assert [r["Status"] for r in rows] == ["Ansökt", "Intervju"]


def test_already_closed_row_is_not_rebumped():
    # Otherwise Datum resets every run and the 30-day prune never reaches it.
    rows = [row("1", "Stängd", "a")]
    assert recheck_dead_ads(rows, fetch_map({"a": DEAD}), today="2026-09-02") == 0
    assert rows[0]["Datum"] == "2026-01-01"


def test_fetch_failure_is_not_evidence_of_death():
    def boom(url):
        raise RuntimeError("network down")
    rows = [row("1", "Identifierad", "a")]
    assert recheck_dead_ads(rows, boom) == 0
    assert rows[0]["Status"] == "Identifierad"
