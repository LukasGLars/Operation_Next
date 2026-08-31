"""Zero-diff edit pairs.

Saving writes both documents, so editing only the CV minted a cover letter
"edit" byte-identical to the draft. _matched_edited_examples then presented the
same text as both the rejected draft and the approved final — an instruction to
avoid and copy the same thing. Four saved applications carried such a pair,
including the closest neighbour to a Business Analyst role.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.app import _edited_stems, _save_docs  # noqa: E402


def test_editing_only_the_cv_leaves_no_cover_letter_pair(tmp_path):
    _save_docs(tmp_path, "draft cv", "draft cl", "original")
    _save_docs(tmp_path, "edited cv", "draft cl", "edited")

    assert (tmp_path / "cv_edited.md").exists()
    assert not (tmp_path / "cover_letter_edited.md").exists()
    assert _edited_stems(tmp_path) == ["cv"]


def test_both_edited_are_both_kept(tmp_path):
    _save_docs(tmp_path, "draft cv", "draft cl", "original")
    _save_docs(tmp_path, "edited cv", "edited cl", "edited")
    assert sorted(_edited_stems(tmp_path)) == ["cover_letter", "cv"]


def test_reverting_an_edit_removes_the_stale_pair(tmp_path):
    """Otherwise a reverted edit keeps teaching the contradiction forever."""
    _save_docs(tmp_path, "draft cv", "draft cl", "original")
    _save_docs(tmp_path, "edited cv", "draft cl", "edited")
    assert (tmp_path / "cv_edited.md").exists()

    _save_docs(tmp_path, "draft cv", "draft cl", "edited")
    assert not (tmp_path / "cv_edited.md").exists()
    assert _edited_stems(tmp_path) == []


def test_an_existing_zero_diff_pair_is_ignored(tmp_path):
    """The four already on disk are inert without having to delete them."""
    (tmp_path / "cv_original.md").write_text("same", encoding="utf-8")
    (tmp_path / "cv_edited.md").write_text("same", encoding="utf-8")
    assert _edited_stems(tmp_path) == []


def test_an_edit_without_a_draft_still_counts(tmp_path):
    """peab_anl_ggning_ab_entreprenadingenj_r has edited files and no originals;
    there is no diff to show, but the finished version is still a usable model."""
    (tmp_path / "cv_edited.md").write_text("hand written", encoding="utf-8")
    assert _edited_stems(tmp_path) == ["cv"]


def test_original_is_never_overwritten(tmp_path):
    """The draft is the 'before' half of the diff — rewriting it destroys it."""
    _save_docs(tmp_path, "draft cv", "draft cl", "original")
    _save_docs(tmp_path, "second draft", "second cl", "original")
    assert (tmp_path / "cv_original.md").read_text(encoding="utf-8") == "draft cv"
