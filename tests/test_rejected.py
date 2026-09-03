"""A job manually deleted from joblist.md must not be re-added by the pipeline
on a later run, even if the same posting resurfaces in a search/JobTech pass."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import updater  # noqa: E402


def test_load_rejected_urls_parses_table(tmp_path, monkeypatch):
    rejected = tmp_path / "rejected.md"
    rejected.write_text(
        "# Rejected — Operation Next\n\n"
        "| Företag | Roll/Typ | Datum | URL |\n"
        "|---|---|---|---|\n"
        "| SEVR | Customer Success | 2026-08-11 | https://sevr.example/jobs/1 |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(updater, "REJECTED_PATH", rejected)
    assert updater.load_rejected_urls() == {"sevr.example/jobs/1"}


def test_load_rejected_urls_missing_file_returns_empty_set(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "REJECTED_PATH", tmp_path / "does-not-exist.md")
    assert updater.load_rejected_urls() == set()


def test_update_joblist_skips_rejected_url(tmp_path, monkeypatch):
    joblist = tmp_path / "joblist.md"
    joblist.write_text(
        "# Job List\n\n"
        "| # | Företag | Roll/Typ | Plats | CV-bas | Status | Datum | URL |\n"
        "|---|---|---|---|---|---|---|---|\n",
        encoding="utf-8",
    )
    rejected = tmp_path / "rejected.md"
    rejected.write_text(
        "| Företag | Roll/Typ | Datum | URL |\n"
        "|---|---|---|---|\n"
        "| SEVR | Customer Success | 2026-08-11 | https://sevr.example/jobs/1 |\n",
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text(json.dumps({
        "new_jobs": [
            {"company": "SEVR", "role": "Customer Success", "url": "https://sevr.example/jobs/1",
             "location": "Göteborg", "role_type": "customer success"},
            {"company": "Acme", "role": "Inköpare", "url": "https://acme.example/jobs/2",
             "location": "Göteborg", "role_type": "inköpare"},
        ],
        "closed_jobs": [],
    }), encoding="utf-8")

    monkeypatch.setattr(updater, "JOBLIST_PATH", joblist)
    monkeypatch.setattr(updater, "REJECTED_PATH", rejected)
    monkeypatch.setattr(updater, "RESULTS_PATH", results)

    updater.update_joblist()

    rows, _ = updater.parse_table(joblist.read_text(encoding="utf-8").splitlines())
    urls = {r["URL"] for r in rows}
    assert "https://acme.example/jobs/2" in urls
    assert "https://sevr.example/jobs/1" not in urls
