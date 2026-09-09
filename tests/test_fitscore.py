# -*- coding: utf-8 -*-
"""Fit scoring — the score orders the list, it never removes anything from it."""
from pipeline import fitscore, jobtech, updater


def test_weights_sum_to_the_max():
    assert sum(fitscore.AXES.values()) == fitscore.MAX_SCORE == 100


def test_clamp_bounds_and_rejects_nonsense():
    assert fitscore.clamp(150) == 100
    assert fitscore.clamp(-5) == 0
    assert fitscore.clamp("87") == 87
    assert fitscore.clamp(87.6) == 88
    assert fitscore.clamp("very good") == 0
    assert fitscore.clamp(None) == 0


def test_score_is_read_from_either_shape():
    assert fitscore.from_verdict({"score": 90}) == 90
    assert fitscore.from_verdict(
        {"axes": {"category": 35, "technical": 25, "requirement": 18, "evidence": 12}}
    ) == 90


def test_a_missing_score_is_zero_not_a_crash():
    """An unjudged candidate has to sort last without taking the run down."""
    assert fitscore.from_verdict({}) == 0
    assert fitscore.from_verdict(None) == 0
    assert fitscore.from_verdict({"fit": True}) == 0


def _candidate(company, url):
    return {"company": company, "role": "Teknisk säljare", "url": url,
            "role_type": "", "location": "Göteborg", "_page_text": "x"}


def test_judge_fit_sorts_by_score_and_keeps_the_unjudged(monkeypatch):
    chunk = [_candidate("Low", "a"), _candidate("High", "b"), _candidate("Unjudged", "c")]
    monkeypatch.setattr(jobtech, "_judge_chunk", lambda c, s, e=None: {
        1: {"fit": True, "score": 30},
        2: {"fit": True, "score": 95},
        # 3 is absent — the model skipped it, or the chunk truncated
    })
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    kept = jobtech.judge_fit(chunk, "skill")
    assert [c["company"] for c in kept] == ["High", "Low", "Unjudged"]
    assert kept[-1]["fit"] == 0, "unjudged sorts last but is still on the list"


def test_an_unfit_verdict_is_still_removed_by_judge_fit(monkeypatch):
    """Scoring does not take over the include/exclude decision."""
    chunk = [_candidate("Out", "a"), _candidate("In", "b")]
    monkeypatch.setattr(jobtech, "_judge_chunk", lambda c, s, e=None: {
        1: {"fit": False, "score": 99, "reason": "pure sales"},
        2: {"fit": True, "score": 40},
    })
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    assert [c["company"] for c in jobtech.judge_fit(chunk, "skill")] == ["In"]


def test_the_table_round_trips_a_score_and_leaves_old_rows_blank():
    """Rows written before scoring existed have no Fit and must stay parseable."""
    scored = {"#": "1", "Företag": "ABB", "Roll/Typ": "AM", "Fit": "90",
              "Status": "Identifierad", "URL": "https://a"}
    legacy = {"#": "2", "Företag": "Old", "Roll/Typ": "X",
              "Status": "Ansökt", "URL": "https://b"}
    rows, _ = updater.parse_table(updater.write_table([scored, legacy]).splitlines())
    assert rows[0]["Fit"] == "90" and rows[0]["URL"] == "https://a"
    assert rows[1]["Fit"] == "" and rows[1]["URL"] == "https://b"


def test_axes_are_stored_and_read_back_in_order():
    verdict = {"axes": {"category": 35, "technical": 25, "requirement": 18, "evidence": 12}}
    assert fitscore.axes_string(verdict) == "35/25/18/12"
    assert fitscore.explain("35/25/18/12") ==         "category 35, technical 25, requirement 18, evidence 12"


def test_a_missing_or_malformed_breakdown_explains_nothing():
    """Better an empty tooltip than a confidently mislabelled one."""
    assert fitscore.axes_string({"score": 90}) == ""
    assert fitscore.axes_string({}) == ""
    assert fitscore.explain("") == ""
    assert fitscore.explain("35/25") == ""
    assert fitscore.explain("a/b/c/d") == "category a, technical b, requirement c, evidence d"


def test_the_breakdown_survives_a_table_round_trip():
    row = {"#": "1", "Företag": "ABB", "Roll/Typ": "AM", "Fit": "90",
           "Fit-delar": "35/25/18/12", "Status": "Identifierad", "URL": "https://a"}
    rows, _ = updater.parse_table(updater.write_table([row]).splitlines())
    assert rows[0]["Fit-delar"] == "35/25/18/12"
    assert rows[0]["URL"] == "https://a"
