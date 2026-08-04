"""Chunking the two batched Claude calls.

Both previously sent every candidate in one request. A run with 32 candidates
truncated the verdict array and dropped all 32; judge_fit hit the same limit and
passed everything through unjudged.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import jobtech, search  # noqa: E402


def candidate(i):
    return {
        "company": f"Acme {i}", "role": "Business Analyst", "role_type": "Analyst",
        "location": "Göteborg", "url": f"https://acme.se/jobs/{1000 + i}-analyst",
        "_page_text": f"Title: Business Analyst\n\nLocation: Göteborg\n\nAd {i}",
    }


def test_validation_splits_into_chunks(monkeypatch):
    calls = []

    def fake_chunk(entries, validation_skill):
        calls.append(len(entries))
        return {e["url"]: ("valid", "ok") for e in entries}

    monkeypatch.setattr(search, "_validate_chunk", fake_chunk)
    monkeypatch.setattr(search, "VALIDATION_CHUNK_SIZE", 8)

    candidates = [candidate(i) for i in range(20)]
    verdicts = search.batch_validate_urls(candidates, "skill text")

    assert calls == [8, 8, 4]                 # no single 20-candidate request
    assert len(verdicts) == 20                # every candidate got a verdict
    assert all(v == ("valid", "ok") for v in verdicts.values())


def test_one_failing_chunk_does_not_sink_the_others(monkeypatch):
    def fake_chunk(entries, validation_skill):
        if entries[0]["url"].endswith("1000-analyst"):
            return {e["url"]: ("uncertain", "validation error: truncated") for e in entries}
        return {e["url"]: ("valid", "ok") for e in entries}

    monkeypatch.setattr(search, "_validate_chunk", fake_chunk)
    monkeypatch.setattr(search, "VALIDATION_CHUNK_SIZE", 4)

    verdicts = search.batch_validate_urls([candidate(i) for i in range(8)], "skill")
    valid = [u for u, (verdict, _) in verdicts.items() if verdict == "valid"]
    assert len(valid) == 4                    # the healthy chunk still passed


def test_judge_fit_splits_into_chunks(monkeypatch):
    calls = []

    def fake_chunk(chunk, skill_content, errors=None):
        calls.append(len(chunk))
        return {i: {"index": i, "fit": True} for i in range(1, len(chunk) + 1)}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(jobtech, "_judge_chunk", fake_chunk)
    monkeypatch.setattr(jobtech, "JUDGE_CHUNK_SIZE", 10)

    kept = jobtech.judge_fit([candidate(i) for i in range(25)], "role filters")

    assert calls == [10, 10, 5]
    assert len(kept) == 25


def test_judge_fit_records_a_failed_chunk_as_an_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(jobtech, "JUDGE_CHUNK_SIZE", 10)

    errors = []

    def failing_chunk(chunk, skill_content, errors=None):
        if errors is not None:
            errors.append("JobTech role-fit judgement truncated for 10 candidate(s)")
        return {}

    monkeypatch.setattr(jobtech, "_judge_chunk", failing_chunk)
    kept = jobtech.judge_fit([candidate(i) for i in range(10)], "role filters", errors=errors)

    assert len(kept) == 10                    # passed through, not dropped
    assert errors and "truncated" in errors[0]  # and the run reports it
