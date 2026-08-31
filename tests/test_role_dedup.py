"""Cross-run duplicate detection.

jobtech dedups (company, role) inside one run and updater dedups on URL. A role
re-advertised under a fresh tracking id a week later defeats both: the URL is
new, and the two sightings were never in the same batch. That is how the Experis
"Affärskoordinator / Business Analyst / Lyreco / Borås" posting landed in
joblist.md twice, seven days apart, under two aplitrak ids.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.updater import _role_key, known_role_keys  # noqa: E402

EXPERIS = "Experis AB"
LYRECO = "Affärskoordinator / Business Analyst / Lyreco / Borås"


def _row(company=EXPERIS, role=LYRECO, status="Identifierad"):
    return {"Företag": company, "Roll/Typ": role, "Status": status}


def test_the_experis_repost_is_recognised():
    assert _role_key(EXPERIS, LYRECO) in known_role_keys([_row()])


def test_case_and_whitespace_do_not_defeat_the_key():
    assert _role_key("experis ab", "Affärskoordinator  /  Business Analyst / Lyreco / Borås") \
        == _role_key(EXPERIS, LYRECO)


def test_roles_differing_by_a_real_word_stay_separate():
    """Bustos advertises these as four distinct openings — over-normalising the
    key would collapse them and silently drop three."""
    keys = known_role_keys([
        _row("Bustos Konsulttjänster AB", "Inköpare bygg"),
        _row("Bustos Konsulttjänster AB", "Inköpare anläggning"),
        _row("Bustos Konsulttjänster AB", "Entreprenadingenör bygg"),
        _row("Bustos Konsulttjänster AB", "Entreprenadingenjör anläggning"),
    ])
    assert len(keys) == 4


def test_same_role_at_a_different_company_is_not_a_duplicate():
    keys = known_role_keys([_row("PEAB SVERIGE AB", "Entreprenadingenjör")])
    assert _role_key("Peab Anläggning AB", "Entreprenadingenjör") not in keys


def test_closed_rows_do_not_block_a_repost():
    """If the earlier posting ended, the role appearing again is a real opening."""
    assert known_role_keys([_row(status="Stängd")]) == set()
    assert known_role_keys([_row(status="stängd")]) == set()


def test_an_applied_row_still_blocks_a_duplicate():
    for status in ("Ansökt", "Intervju", "Genererat"):
        assert _role_key(EXPERIS, LYRECO) in known_role_keys([_row(status=status)])
