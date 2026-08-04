"""Parsing model responses — the bug that dropped 32 valid candidates.

A truncated verdict array failed the same way as malformed output, so a
max_tokens problem was reported as "uncertain" for every candidate.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.llm_json import TruncatedResponse, parse_json_array  # noqa: E402


def test_plain_array():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]


def test_fenced_array():
    assert parse_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_truncation_is_its_own_error():
    """The actual failing response: array cut off mid-object."""
    truncated = '[\n  {"url": "https://x.se/1", "verdict": "valid", "reason": "ok"},\n  {"url": "https://x.se/2", "verd'
    with pytest.raises(TruncatedResponse) as excinfo:
        parse_json_array(truncated)
    assert "truncated" in str(excinfo.value)


def test_prose_before_the_array_is_skipped():
    text = 'Here are the verdicts:\n\n[{"url": "https://x.se/1", "verdict": "valid"}]'
    assert parse_json_array(text) == [{"url": "https://x.se/1", "verdict": "valid"}]


def test_citation_marker_does_not_parse_as_the_result():
    """Why greedy matters: a non-greedy regex matched "[1]" and returned an empty
    result set, which is how a search pass reported 0 candidates."""
    text = 'Found one role [1] matching:\n[{"company": "Nexer", "role": "Business Analyst"}]'
    assert parse_json_array(text) == [{"company": "Nexer", "role": "Business Analyst"}]


def test_empty_array_is_a_valid_answer():
    assert parse_json_array("[]") == []


def test_no_array_at_all():
    with pytest.raises(ValueError) as excinfo:
        parse_json_array("I could not validate these URLs.")
    assert "no JSON array" in str(excinfo.value)
