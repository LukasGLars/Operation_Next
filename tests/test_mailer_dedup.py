# -*- coding: utf-8 -*-
"""The digest reports what reached the joblist, not what search.py approved.

results.json is written before the updater dedups against the joblist and
rejected.md, so the mail kept announcing roles that were already on the list —
KUKA and Profcon both went out as "new" on a run where the updater had skipped
them as duplicates.
"""
import json

import pytest

from pipeline import mailer


@pytest.fixture
def applied(tmp_path, monkeypatch):
    path = tmp_path / "applied.json"
    monkeypatch.setattr(mailer, "APPLIED_PATH", path)
    monkeypatch.setattr(mailer, "RESULTS_PATH", tmp_path / "results.json")
    return path


def _write(path, added, closed=()):
    path.write_text(json.dumps({"added": list(added), "closed": list(closed)},
                               ensure_ascii=False), encoding="utf-8")


def test_body_carries_only_the_role_and_the_url():
    body = mailer.build_body(
        [{"role": "Teknisk säljare till SMC Automation", "url": "https://a",
          "company": "Bravura", "role_type": "Säljare", "cv_base": "CV_Zeppelin"}], [])
    assert "Teknisk säljare till SMC Automation" in body
    assert "https://a" in body
    assert "Typ:" not in body
    assert "CV-bas:" not in body
    assert "Bravura" not in body


def test_a_duplicate_the_updater_skipped_is_not_announced(applied):
    """search.py approved KUKA; the updater skipped it as already listed."""
    _write(applied, added=[{"role": "Säljare till MANN+HUMMEL", "url": "https://new"}])
    (mailer.RESULTS_PATH).write_text(json.dumps({"new_jobs": [
        {"role": "Inside Sales Engineer till KUKA Nordic", "url": "https://kuka"},
        {"role": "Säljare till MANN+HUMMEL", "url": "https://new"}]}), encoding="utf-8")
    data = json.loads(applied.read_text(encoding="utf-8"))
    body = mailer.build_body(data["added"], data["closed"])
    assert "MANN+HUMMEL" in body
    assert "KUKA" not in body


def test_closed_rows_also_drop_to_role_and_url():
    body = mailer.build_body([], [{"role": "Kalkylator bygg", "url": "https://c",
                                   "company": "Bustos"}])
    assert "Kalkylator bygg" in body and "https://c" in body
    assert "Bustos" not in body
