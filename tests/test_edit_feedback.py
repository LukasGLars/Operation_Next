"""Human edits fed back into the review pass.

The edits are the only record of what actually gets rejected, so both documents
have to reach the prompt — the CV corrections (inflated titles, tool lists,
bullets naming internals) were invisible while this read cover letters only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.app as flask_app  # noqa: E402


def write_pair(folder, stem, draft, final):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}_original.md").write_text(draft, encoding="utf-8")
    (folder / f"{stem}_edited.md").write_text(final, encoding="utf-8")


def test_both_documents_reach_the_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    write_pair(tmp_path / "acme_analyst", "cover_letter",
               "DRAFT LETTER särskilt", "FINAL LETTER")
    write_pair(tmp_path / "acme_analyst", "cv",
               "### Hercules – Platschef", "### Hercules – Arbetsledare")

    examples = flask_app._recent_edited_examples()

    assert "Cover letter example 1" in examples
    assert "CV example 1" in examples
    assert "Platschef" in examples      # the rejected draft
    assert "Arbetsledare" in examples   # the approved version


def test_draft_is_labelled_rejected_and_final_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    write_pair(tmp_path / "acme_analyst", "cv", "DRAFT", "FINAL")

    examples = flask_app._recent_edited_examples()
    assert examples.index("REJECTED") < examples.index("human-approved")


def test_edit_without_a_draft_still_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    folder = tmp_path / "acme_analyst"
    folder.mkdir()
    (folder / "cv_edited.md").write_text("FINAL ONLY", encoding="utf-8")

    examples = flask_app._recent_edited_examples()
    assert "FINAL ONLY" in examples
    assert "REJECTED" not in examples


def test_no_edits_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, "APPLICATIONS", tmp_path)
    assert flask_app._recent_edited_examples() == ""
