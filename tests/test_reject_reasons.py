# -*- coding: utf-8 -*-
"""Rejection reasons — how a preference reaches the judge.

The URL and company+role checks hold out the *same* posting. A reason has to
generalise: the proAV role that prompted this scored 88, because the rubric
measures whether a role is winnable and nothing in it models what the candidate
finds dull. No static rule in search_skill.md was going to cover it.
"""
import app.app as appmod
from pipeline import jobtech, updater


def _wire(tmp_path, monkeypatch):
    rejected = tmp_path / "rejected.md"
    monkeypatch.setattr(appmod, "REJECTED_PATH", rejected)
    monkeypatch.setattr(updater, "REJECTED_PATH", rejected)
    return rejected


def test_a_reason_is_written_and_read_back(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    appmod._append_rejected("Karisma", "Teknisk säljare, proAV",
                            "https://a", "inte intresserad av ljud och bild")
    assert updater.load_rejection_reasons() == [
        ("Teknisk säljare, proAV", "inte intresserad av ljud och bild")]


def test_rows_without_a_reason_are_ignored_not_broken(tmp_path, monkeypatch):
    """Every row written before this existed has four columns."""
    rejected = _wire(tmp_path, monkeypatch)
    rejected.write_text(
        "| Företag | Roll/Typ | Datum | URL |\n|---|---|---|---|\n"
        "| Old AB | Inköpare | 2026-08-01 | https://old |\n", encoding="utf-8")
    assert updater.load_rejection_reasons() == []
    assert updater.load_rejected_urls() == {"old"}


def test_the_url_still_lands_at_index_three_with_a_reason_present(tmp_path, monkeypatch):
    """_rejected_rows keys the URL positionally, which is why Anledning is
    appended last rather than inserted."""
    _wire(tmp_path, monkeypatch)
    appmod._append_rejected("Karisma", "proAV", "https://x", "domän jag ogillar")
    assert updater.load_rejected_urls() == {"x"}
    assert updater.load_rejected_role_keys()


def test_a_pipe_in_the_reason_cannot_break_the_table(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    appmod._append_rejected("A", "B", "https://c", "ljud | bild | nätverk")
    assert updater.load_rejection_reasons() == [("B", "ljud / bild / nätverk")]


def test_only_the_newest_reasons_reach_the_prompt(tmp_path, monkeypatch):
    """They are appended to every judge call, so the list is capped."""
    _wire(tmp_path, monkeypatch)
    for i in range(40):
        appmod._append_rejected("C", f"Roll {i}", f"https://u{i}", f"skäl {i}")
    reasons = updater.load_rejection_reasons(limit=25)
    assert len(reasons) == 25
    assert reasons[-1] == ("Roll 39", "skäl 39"), "newest must survive the cap"


def test_the_block_tells_the_judge_to_generalise(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    appmod._append_rejected("Karisma", "proAV", "https://a", "ogillar ljud och bild")
    block = jobtech._rejection_block()
    assert "ogillar ljud och bild" in block
    assert "same kind" in block and "unfit" in block


def test_no_rejections_means_no_block(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    assert jobtech._rejection_block() == ""


def test_an_unreadable_rejected_file_costs_the_rules_not_the_run(monkeypatch):
    def boom(*a, **k):
        raise OSError("gone")
    monkeypatch.setattr(updater, "load_rejection_reasons", boom)
    assert jobtech._rejection_block() == ""
