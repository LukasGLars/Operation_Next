"""The Plats column — a role's location has to survive into joblist.md, or an
out-of-range ad is invisible in the list and in the digest mail."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.updater import parse_table, write_table  # noqa: E402


def test_new_job_location_lands_in_plats_column():
    table = write_table([{
        "#": "1", "Företag": "SEVR", "Roll/Typ": "Customer Success",
        "Plats": "Göteborg", "CV-bas": "CV_Einride", "Status": "Identifierad",
        "Datum": "2026-08-04", "URL": "https://example.com/jobs/1234-csm",
    }])
    header, _, row = table.splitlines()
    assert header.split("|")[4].strip() == "Plats"
    assert row.split("|")[4].strip() == "Göteborg"


def test_row_from_older_table_gets_placeholder():
    table = write_table([{"#": "1", "Företag": "Acme", "URL": "https://x.se/jobs/1"}])
    assert table.splitlines()[2].split("|")[4].strip() == "—"


def test_roundtrip_keeps_plats():
    rows_in = [{
        "#": "1", "Företag": "Veidekke", "Roll/Typ": "Platschef",
        "Plats": "Göteborg", "CV-bas": "CV_BYGG", "Status": "Identifierad",
        "Datum": "2026-08-04", "URL": "https://veidekke.example/jobs/7958681",
    }]
    rows_out, has_datum = parse_table(write_table(rows_in).splitlines())
    assert has_datum
    assert rows_out[0]["Plats"] == "Göteborg"
