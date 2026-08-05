"""Human edits fed back into the review pass, matched by role instead of recency.

The edits are the only record of what actually gets rejected, so both documents
have to reach the prompt -- the CV corrections (inflated titles, tool lists,
bullets naming internals) were invisible while this read cover letters only.

Matching by role also matters: a technical field-sales edit has nothing to
teach a digital business developer draft. The match itself is a Claude call,
stubbed out here via _match_similar_role so tests don't hit the API.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.app as flask_app  # noqa: E402


def write_pair(folder, stem, draft, final):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}_original.md").write_text(draft, encoding="utf-8")
    (folder / f"{stem}_edited.md").write_text(final, encoding="utf-8")


def write_meta(folder, company, role):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(
        json.dumps({"company": company, "role": role}), encoding="utf-8")


def test_both_documents_reach_the_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    monkeypatch.setattr(flask_app, "_match_similar_role", lambda *a, **k: 0)
    folder = tmp_path / "acme_analyst"
    write_pair(folder, "cover_letter", "DRAFT LETTER särskilt", "FINAL LETTER")
    write_pair(folder, "cv", "### Hercules – Platschef", "### Hercules – Arbetsledare")
    write_meta(folder, "Acme", "Business Analyst")

    examples = flask_app._matched_edited_examples(None, "Voi", "Business Analyst")

    assert "Cover letter example" in examples
    assert "CV example" in examples
    assert "Platschef" in examples      # the rejected draft
    assert "Arbetsledare" in examples   # the approved version


def test_draft_is_labelled_rejected_and_final_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    monkeypatch.setattr(flask_app, "_match_similar_role", lambda *a, **k: 0)
    folder = tmp_path / "acme_analyst"
    write_pair(folder, "cv", "DRAFT", "FINAL")
    write_meta(folder, "Acme", "Business Analyst")

    examples = flask_app._matched_edited_examples(None, "Voi", "Business Analyst")
    assert examples.index("REJECTED") < examples.index("human-approved")


def test_edit_without_a_draft_still_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    monkeypatch.setattr(flask_app, "_match_similar_role", lambda *a, **k: 0)
    folder = tmp_path / "acme_analyst"
    folder.mkdir()
    (folder / "cv_edited.md").write_text("FINAL ONLY", encoding="utf-8")
    write_meta(folder, "Acme", "Business Analyst")

    examples = flask_app._matched_edited_examples(None, "Voi", "Business Analyst")
    assert "FINAL ONLY" in examples
    assert "REJECTED" not in examples


def test_no_edits_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    assert flask_app._matched_edited_examples(None, "Voi", "Business Analyst") == ""


def test_no_close_match_yields_nothing(tmp_path, monkeypatch):
    """The core fix: an unrelated role's edit must not bleed into the draft."""
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    monkeypatch.setattr(flask_app, "_match_similar_role", lambda *a, **k: None)
    folder = tmp_path / "thomas_betong_teknisk"
    write_pair(folder, "cv", "DRAFT", "FINAL")
    write_meta(folder, "Thomas Betong", "Teknisk säljare")

    examples = flask_app._matched_edited_examples(None, "Voi", "Digital affärsutvecklare")
    assert examples == ""


def test_current_role_is_excluded_from_its_own_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    calls = []

    def fake_match(client, role, company, candidates):
        calls.append(candidates)
        return None

    monkeypatch.setattr(flask_app, "_match_similar_role", fake_match)
    folder = flask_app._app_folder("Acme", "Business Analyst")
    write_pair(folder, "cv", "DRAFT", "FINAL")
    write_meta(folder, "Acme", "Business Analyst")

    flask_app._matched_edited_examples(None, "Acme", "Business Analyst")
    assert calls == []  # the only candidate was itself, so no match call was made


def test_missing_meta_falls_back_to_folder_name(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    seen_titles = []

    def fake_match(client, role, company, candidates):
        seen_titles.extend(candidates)
        return 0

    monkeypatch.setattr(flask_app, "_match_similar_role", fake_match)
    write_pair(tmp_path / "acme_business_analyst", "cv", "DRAFT", "FINAL")

    flask_app._matched_edited_examples(None, "Voi", "Business Analyst")
    assert seen_titles == ["acme business analyst"]
