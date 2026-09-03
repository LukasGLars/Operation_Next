"""Marking several rows and clearing them in one click: one joblist rewrite,
one push, and every removed row recorded in rejected.md. Setting a row to
Avslag records it too, but leaves the row in the list."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app as appmod  # noqa: E402

JOBLIST = (
    "# Job List\n\n"
    "| # | Företag | Roll/Typ | Plats | CV-bas | Status | Datum | Deadline | Annons | URL |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
    "| 1 | Acme | Inköpare | Göteborg | CV | Identifierad | 2026-09-01 |  | a | https://a.example/1 |\n"
    "| 2 | Bolt | Säljare | Göteborg | CV | Identifierad | 2026-09-01 |  | b | https://b.example/2 |\n"
    "| 3 | Cirk | Analytiker | Göteborg | CV | Ansökt | 2026-09-01 |  | c | https://c.example/3 |\n"
)


def _wire(tmp_path, monkeypatch):
    joblist = tmp_path / "joblist.md"
    joblist.write_text(JOBLIST, encoding="utf-8")
    rejected = tmp_path / "rejected.md"
    pushes = []
    monkeypatch.setattr(appmod, "JOBLIST_PATH", joblist)
    monkeypatch.setattr(appmod, "REJECTED_PATH", rejected)
    monkeypatch.setattr(appmod, "_push_joblist", lambda: pushes.append(1))
    return joblist, rejected, pushes


def _rows(joblist):
    return {r["URL"] for r in appmod.parse_joblist()}


def test_deletes_several_rows_in_one_write_and_one_push(tmp_path, monkeypatch):
    joblist, rejected, pushes = _wire(tmp_path, monkeypatch)
    n = appmod._delete_job_rows(["https://a.example/1", "https://c.example/3"])
    assert n == 2
    assert _rows(joblist) == {"https://b.example/2"}
    assert len(pushes) == 1, "a bulk delete is one commit, not one per row"


def test_remaining_rows_are_renumbered(tmp_path, monkeypatch):
    joblist, _, _ = _wire(tmp_path, monkeypatch)
    appmod._delete_job_rows(["https://a.example/1"])
    assert [r["#"] for r in appmod.parse_joblist()] == ["1", "2"]


def test_every_deleted_row_lands_in_rejected(tmp_path, monkeypatch):
    _, rejected, _ = _wire(tmp_path, monkeypatch)
    appmod._delete_job_rows(["https://a.example/1", "https://c.example/3"])
    text = rejected.read_text(encoding="utf-8")
    assert "https://a.example/1" in text
    assert "https://c.example/3" in text
    assert "https://b.example/2" not in text


def test_unknown_url_is_ignored(tmp_path, monkeypatch):
    joblist, _, _ = _wire(tmp_path, monkeypatch)
    assert appmod._delete_job_rows(["https://nope.example/9"]) == 0
    assert len(_rows(joblist)) == 3


def test_empty_selection_does_nothing(tmp_path, monkeypatch):
    joblist, _, pushes = _wire(tmp_path, monkeypatch)
    assert appmod._delete_job_rows([]) == 0
    assert appmod._delete_job_rows(["", "  "]) == 0
    assert len(_rows(joblist)) == 3
    assert pushes == []


def test_avslag_keeps_the_row_but_records_it(tmp_path, monkeypatch):
    joblist, rejected, _ = _wire(tmp_path, monkeypatch)
    client = appmod.app.test_client()
    res = client.post("/status", json={"url": "https://c.example/3", "status": "Avslag"})
    assert res.get_json() == {"ok": True}

    rows = {r["URL"]: r for r in appmod.parse_joblist()}
    assert rows["https://c.example/3"]["Status"] == "Avslag", "row stays in the list"
    assert "https://c.example/3" in rejected.read_text(encoding="utf-8")


def test_other_statuses_are_not_recorded_as_rejected(tmp_path, monkeypatch):
    _, rejected, _ = _wire(tmp_path, monkeypatch)
    client = appmod.app.test_client()
    client.post("/status", json={"url": "https://a.example/1", "status": "Ansökt"})
    assert not rejected.exists()


def test_delete_route_accepts_a_single_url(tmp_path, monkeypatch):
    joblist, _, _ = _wire(tmp_path, monkeypatch)
    client = appmod.app.test_client()
    res = client.post("/delete", json={"url": "https://a.example/1"})
    assert res.get_json()["deleted"] == 1
    assert _rows(joblist) == {"https://b.example/2", "https://c.example/3"}


def test_delete_route_accepts_a_list(tmp_path, monkeypatch):
    joblist, _, _ = _wire(tmp_path, monkeypatch)
    client = appmod.app.test_client()
    res = client.post("/delete", json={"urls": ["https://a.example/1", "https://b.example/2"]})
    assert res.get_json()["deleted"] == 2
    assert _rows(joblist) == {"https://c.example/3"}


def test_delete_route_rejects_an_empty_body(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    client = appmod.app.test_client()
    assert appmod.app.test_client().post("/delete", json={"urls": []}).status_code == 400
