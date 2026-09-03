"""Index page sorts by how far along a job is -- Intervju first, Stängd last."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.app import _status_rank  # noqa: E402


def test_order_runs_live_then_outcomes_then_stangd():
    ranks = [_status_rank(s) for s in
              ["Intervju", "Ansökt", "Genererat", "Identifierad", "Avslag",
               "Ej kvalificerad", "Nagot annat", "Stängd"]]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == 8


def test_outcomes_sort_below_every_live_row_but_above_stangd():
    for outcome in ("Avslag", "Ej kvalificerad"):
        for live in ("Intervju", "Ansökt", "Genererat", "Identifierad"):
            assert _status_rank(live) < _status_rank(outcome)
        assert _status_rank(outcome) < _status_rank("Stängd")


def test_avslag_outranks_ej_kvalificerad():
    """Avslag means you applied and heard back; Ej kvalificerad means you never
    applied, so it is the less far-along of the two."""
    assert _status_rank("Avslag") < _status_rank("Ej kvalificerad")


def test_ansokt_without_diacritic_ranks_same_as_with():
    assert _status_rank("Ansökt") == _status_rank("Ansokt")


def test_sort_is_stable_within_same_status():
    jobs = [{"Status": "Identifierad", "Företag": "A"}, {"Status": "Identifierad", "Företag": "B"}]
    jobs.sort(key=lambda j: _status_rank(j["Status"]))
    assert [j["Företag"] for j in jobs] == ["A", "B"]
