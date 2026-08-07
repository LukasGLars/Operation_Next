"""Index page sorts by how far along a job is -- Intervju first, Stängd last."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.app import _status_rank  # noqa: E402


def test_order_is_intervju_ansokt_genererat_identifierad_other_stangd():
    ranks = [_status_rank(s) for s in
              ["Intervju", "Ansökt", "Genererat", "Identifierad", "Nagot annat", "Stängd"]]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == 6


def test_ansokt_without_diacritic_ranks_same_as_with():
    assert _status_rank("Ansökt") == _status_rank("Ansokt")


def test_sort_is_stable_within_same_status():
    jobs = [{"Status": "Identifierad", "Företag": "A"}, {"Status": "Identifierad", "Företag": "B"}]
    jobs.sort(key=lambda j: _status_rank(j["Status"]))
    assert [j["Företag"] for j in jobs] == ["A", "B"]
