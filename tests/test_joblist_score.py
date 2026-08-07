"""The Score column — CV-fit ranking has to survive into joblist.md, or the
UI has nothing to sort ads by."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.updater import parse_table, write_table  # noqa: E402


def test_new_job_score_lands_in_score_column():
    table = write_table([{
        "#": "1", "Företag": "SEVR", "Roll/Typ": "Customer Success",
        "Plats": "Göteborg", "CV-bas": "CV_Einride", "Status": "Identifierad",
        "Datum": "2026-08-04", "URL": "https://example.com/jobs/1234-csm",
        "Score": "0.1950",
    }])
    header, _, row = table.splitlines()
    assert header.split("|")[9].strip() == "Score"
    assert row.split("|")[9].strip() == "0.1950"


def test_row_without_score_gets_placeholder():
    table = write_table([{"#": "1", "Företag": "Acme", "URL": "https://x.se/jobs/1"}])
    assert table.splitlines()[2].split("|")[9].strip() == "—"


def test_roundtrip_keeps_score():
    rows_in = [{
        "#": "1", "Företag": "Veidekke", "Roll/Typ": "Platschef",
        "Plats": "Göteborg", "CV-bas": "CV_BYGG", "Status": "Identifierad",
        "Datum": "2026-08-04", "URL": "https://veidekke.example/jobs/7958681",
        "Score": "0.0421",
    }]
    rows_out, has_datum = parse_table(write_table(rows_in).splitlines())
    assert has_datum
    assert rows_out[0]["Score"] == "0.0421"
