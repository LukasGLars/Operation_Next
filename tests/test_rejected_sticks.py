"""A job that was deleted, or that came back no, must stay gone. Three ways it
used to return: a fresh tracking tag on the URL, an opaque tracking URL that
canonicalisation cannot match, and the 30-day prune dropping a Stängd row
without recording it."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import search, updater  # noqa: E402

HEADER = (
    "| # | Företag | Roll/Typ | Plats | CV-bas | Status | Datum | Deadline | Annons | URL |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)
REJECTED_HEADER = "| Företag | Roll/Typ | Datum | URL |\n|---|---|---|---|\n"

# update_joblist() returns early when a pass found nothing, so the prune cases
# need one unrelated result to get past that.
FILLER = {"company": "Filler", "role": "Analytiker",
          "url": "https://filler.example/jobs/9",
          "location": "Göteborg", "role_type": "data analyst"}


def _wire(tmp_path, monkeypatch, joblist_rows="", rejected_rows="", new_jobs=()):
    # recheck_dead_ads fetches every live row; without a stub these tests would
    # hit the network and mark the fake domains dead.
    monkeypatch.setattr(search, "fetch_page_text", lambda url: "en riktig annons " * 40)
    joblist = tmp_path / "joblist.md"
    joblist.write_text("# Job List\n\n" + HEADER + joblist_rows, encoding="utf-8")
    rejected = tmp_path / "rejected.md"
    rejected.write_text(REJECTED_HEADER + rejected_rows, encoding="utf-8")
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"new_jobs": list(new_jobs), "closed_jobs": []}),
                       encoding="utf-8")
    monkeypatch.setattr(updater, "JOBLIST_PATH", joblist)
    monkeypatch.setattr(updater, "REJECTED_PATH", rejected)
    monkeypatch.setattr(updater, "RESULTS_PATH", results)
    return joblist, rejected


def _urls(joblist):
    rows, _ = updater.parse_table(joblist.read_text(encoding="utf-8").splitlines())
    return {r["URL"] for r in rows}


def test_rejected_job_with_a_new_promotion_tag_is_not_readded(tmp_path, monkeypatch):
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        rejected_rows="| Oddwork | Teknisk säljare | 2026-08-01 | "
                      "https://jobb.oddwork.se/jobs/803-teknisk/applications/new?promotion=OLD |\n",
        new_jobs=[{"company": "Oddwork", "role": "Teknisk säljare",
                   "url": "https://jobb.oddwork.se/jobs/803-teknisk?promotion=NEW",
                   "location": "Göteborg", "role_type": "teknisk säljare"}],
    )
    updater.update_joblist()
    assert _urls(joblist) == set()


def test_rejected_job_under_an_opaque_url_is_caught_by_role(tmp_path, monkeypatch):
    """The real case: an Experis role came back under a second aplitrak adid,
    which no amount of URL normalising can match."""
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        rejected_rows="| Experis AB | Inköpare/ Upphandlare | 2026-08-01 | "
                      "https://www.aplitrak.com/?adid=OLD |\n",
        new_jobs=[{"company": "Experis AB", "role": "Inköpare/ Upphandlare",
                   "url": "https://www.aplitrak.com/?adid=NEW",
                   "location": "Alingsås", "role_type": "inköpare"}],
    )
    updater.update_joblist()
    assert _urls(joblist) == set()


def test_unrelated_job_still_gets_added(tmp_path, monkeypatch):
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        rejected_rows="| Experis AB | Inköpare | 2026-08-01 | https://www.aplitrak.com/?adid=OLD |\n",
        new_jobs=[{"company": "Acme", "role": "Teknisk säljare",
                   "url": "https://acme.example/jobs/2",
                   "location": "Göteborg", "role_type": "teknisk säljare"}],
    )
    updater.update_joblist()
    assert "https://acme.example/jobs/2" in _urls(joblist)


def test_pruned_stale_row_is_recorded_as_rejected(tmp_path, monkeypatch):
    stale = (date.today() - timedelta(days=45)).isoformat()
    joblist, rejected = _wire(
        tmp_path, monkeypatch,
        joblist_rows=f"| 1 | Poolia | Inköpare | Göteborg | CV | Stängd | {stale} |  | "
                     f"https://poolia.example/jobs/1 | https://poolia.example/jobs/1 |\n",
        new_jobs=[FILLER],
    )
    updater.update_joblist()
    assert _urls(joblist) == {FILLER["url"]}, "stale row should still be pruned"
    assert updater.canonical_url("https://poolia.example/jobs/1") in updater.load_rejected_urls()


def test_pruned_avslag_row_is_recorded_too(tmp_path, monkeypatch):
    stale = (date.today() - timedelta(days=45)).isoformat()
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        joblist_rows=f"| 1 | Vitec | Teknisk säljare | Göteborg | CV | Avslag | {stale} |  | "
                     f"https://vitec.example/jobs/1 | https://vitec.example/jobs/1 |\n",
        new_jobs=[FILLER],
    )
    updater.update_joblist()
    assert _urls(joblist) == {FILLER["url"]}
    assert updater.canonical_url("https://vitec.example/jobs/1") in updater.load_rejected_urls()


def test_pruned_ej_kvalificerad_row_is_recorded_too(tmp_path, monkeypatch):
    stale = (date.today() - timedelta(days=45)).isoformat()
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        joblist_rows=f"| 1 | Surgical Science | Product Specialist | Göteborg | CV | "
                     f"Ej kvalificerad | {stale} |  | "
                     f"https://ss.example/jobs/1 | https://ss.example/jobs/1 |\n",
        new_jobs=[FILLER],
    )
    updater.update_joblist()
    assert _urls(joblist) == {FILLER["url"]}
    assert updater.canonical_url("https://ss.example/jobs/1") in updater.load_rejected_urls()


def test_ej_kvalificerad_row_is_not_reopened_by_the_dead_ad_recheck(tmp_path, monkeypatch):
    """The ad stays live for months; that says nothing about whether the
    candidate qualifies, so the recheck must leave the row alone."""
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        joblist_rows=f"| 1 | Surgical Science | Product Specialist | Göteborg | CV | "
                     f"Ej kvalificerad | {date.today().isoformat()} |  | "
                     f"https://ss.example/jobs/1 | https://ss.example/jobs/1 |\n",
        new_jobs=[FILLER],
    )
    updater.update_joblist()
    rows, _ = updater.parse_table(joblist.read_text(encoding="utf-8").splitlines())
    row = next(r for r in rows if r["URL"] == "https://ss.example/jobs/1")
    assert row["Status"] == "Ej kvalificerad"


def test_recent_closed_row_is_left_alone(tmp_path, monkeypatch):
    joblist, _ = _wire(
        tmp_path, monkeypatch,
        joblist_rows=f"| 1 | Poolia | Inköpare | Göteborg | CV | Stängd | {date.today().isoformat()} |  | "
                     f"https://poolia.example/jobs/1 | https://poolia.example/jobs/1 |\n",
    )
    updater.update_joblist()
    assert "https://poolia.example/jobs/1" in _urls(joblist)
    assert updater.load_rejected_urls() == set()


def test_append_rejected_does_not_duplicate(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch,
          rejected_rows="| Acme | Inköpare | 2026-08-01 | https://acme.example/jobs/1 |\n")
    row = {"Företag": "Acme", "Roll/Typ": "Inköpare", "URL": "https://acme.example/jobs/1?promotion=X"}
    assert updater.append_rejected([row]) == 0
