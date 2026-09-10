# -*- coding: utf-8 -*-
"""Keep the suite off the real jobsearch/ data.

`update_joblist()` prunes the requirements sidecar to whatever rows it was given.
Tests that exercise it redirect JOBLIST_PATH and RESULTS_PATH to tmp_path but had
no reason to know about a store added later — so the first run of the suite after
that change pruned the real jobsearch/requirements.json down to its two fixture
rows, i.e. emptied it.

Redirecting the store for every test makes that impossible to repeat, including
for whatever sidecar comes next.
"""
import pytest

from pipeline import adrequirements


@pytest.fixture(autouse=True)
def _never_touch_the_real_requirements_store(tmp_path, monkeypatch):
    monkeypatch.setattr(adrequirements, "STORE", tmp_path / "requirements.json")
