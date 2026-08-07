"""_attach_scores must reuse the page text the location gate already fetched
— scoring a batch of new ads should cost zero extra network calls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.search import _attach_scores  # noqa: E402


def test_attach_scores_uses_existing_page_text(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("fetch_page_text should not be called for scoring")

    monkeypatch.setattr("pipeline.search.fetch_page_text", _fail_if_called)

    jobs = [
        {"company": "TechCo", "_page_text": "Python automation and pandas for AI-driven pipelines"},
        {"company": "Bageri", "_page_text": "Vi söker en glad person till vårt bageri"},
    ]
    _attach_scores(jobs)

    assert all("score" in job for job in jobs)
    assert isinstance(jobs[0]["score"], float)


def test_attach_scores_ranks_closer_match_higher(monkeypatch, tmp_path):
    cv_path = tmp_path / "master_cv.md"
    cv_path.write_text(
        "Python automation, pandas, data-driven decision-making, AI integration",
        encoding="utf-8",
    )
    monkeypatch.setattr("pipeline.search.CV_PATH", cv_path)
    jobs = [
        {"company": "Bageri", "_page_text": "Vi söker en glad person till vårt bageri, ingen erfarenhet krävs"},
        {"company": "TechCo", "_page_text": "Python automation and pandas experience for AI-driven data pipelines"},
    ]
    _attach_scores(jobs)
    assert jobs[1]["score"] > jobs[0]["score"]


def test_attach_scores_noop_on_empty_list():
    jobs = []
    _attach_scores(jobs)
    assert jobs == []
