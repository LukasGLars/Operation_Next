# -*- coding: utf-8 -*-
"""The requirements sidecar — a tooltip, and never more important than the list."""
import json

import pytest

from pipeline import adrequirements


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(adrequirements, "STORE", tmp_path / "requirements.json")


def test_clean_trims_bullets_and_markers():
    out = adrequirements.clean(["- Erfarenhet av  teknisk\n  försäljning", "• B-körkort"])
    assert out == ["Erfarenhet av teknisk försäljning", "B-körkort"]


def test_clean_caps_count_and_length():
    assert len(adrequirements.clean([f"krav {i}" for i in range(20)])) == adrequirements.MAX_BULLETS
    assert len(adrequirements.clean(["x" * 500])[0]) == adrequirements.MAX_BULLET_CHARS


def test_clean_drops_anything_that_is_not_a_list_of_strings():
    assert adrequirements.clean(None) == []
    assert adrequirements.clean("Erfarenhet") == []
    assert adrequirements.clean([1, None, {"a": 1}]) == []


def test_save_and_load_round_trip():
    adrequirements.save({"https://a": ["Krav ett", "Krav två"]})
    assert adrequirements.load() == {"https://a": ["Krav ett", "Krav två"]}


def test_an_empty_extraction_cannot_wipe_what_was_captured_before():
    """A run where the model returned nothing must leave yesterday's bullets
    alone — the alternative is the tooltip silently emptying."""
    adrequirements.save({"https://a": ["Krav ett"]})
    adrequirements.save({"https://a": []})
    assert adrequirements.load()["https://a"] == ["Krav ett"]


def test_prune_drops_entries_whose_row_is_gone():
    adrequirements.save({"https://a": ["x"], "https://b": ["y"]})
    assert adrequirements.prune(["https://a"]) == 1
    assert set(adrequirements.load()) == {"https://a"}


def test_a_corrupt_store_reads_as_empty_rather_than_raising():
    """Losing the sidecar costs a tooltip; it must not take the joblist down."""
    adrequirements.STORE.write_text("{not json", encoding="utf-8")
    assert adrequirements.load() == {}


def test_a_list_at_the_top_level_is_not_treated_as_a_store():
    adrequirements.STORE.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    assert adrequirements.load() == {}
