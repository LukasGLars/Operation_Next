"""One-off: fill Annons and Deadline on joblist rows that predate those columns.

Not part of the recurring run — `updater.py` populates both for every new row.
This exists only to catch up the rows already in the list when the columns were
added.

It never deletes. A row that finds no match is left exactly as it is and printed
for review, because absence from the API is not evidence of expiry: rows sourced
from the web search were never in Platsbanken to begin with, and a live ad can
miss on query drift or the per-query limit. Deleting on a miss would take out
good rows to remove a few stale ones.

    python pipeline/backfill_ads.py            # preview
    python pipeline/backfill_ads.py --write    # apply
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# The scheduled pipeline runs under UTF-8; this script is run by hand, and a
# Windows console defaults to cp1252 — which cannot encode the arrow or the å/ä/ö
# in company names, and would abort the run on a print rather than on a failure.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline import jobtech
from pipeline.updater import (
    JOBLIST_PATH, close_expired, parse_table, write_table,
)


def index_live_ads():
    """apply URL -> hit, over the same queries the pipeline runs.

    Uses _search rather than fetch_candidates so withdrawn and past-deadline ads
    are included — those are exactly the ones worth finding here.
    """
    by_url = {}
    for query in jobtech.ROLE_QUERIES:
        for remote in (False, True):
            try:
                hits = jobtech._search(query, remote=remote)
            except Exception as e:
                print(f"  WARNING: search failed ({query}, remote={remote}): {e}")
                continue
            for hit in hits:
                url = jobtech.canonical_url(hit)
                if url:
                    by_url.setdefault(url, hit)
    return by_url


def backfill(rows, by_url):
    """Fill blank Annons/Deadline cells in place. Returns (filled, unmatched)."""
    filled, unmatched = 0, []
    for row in rows:
        if row.get("Annons", "").strip() and row.get("Deadline", "").strip():
            continue
        hit = by_url.get(row.get("URL", "").strip())
        if not hit:
            unmatched.append(row)
            continue
        row["Annons"] = row.get("Annons", "").strip() or jobtech.ad_url(hit)
        row["Deadline"] = row.get("Deadline", "").strip() or jobtech.deadline(hit)
        filled += 1
    return filled, unmatched


def main(write=False):
    lines = JOBLIST_PATH.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().startswith("|")), None)
    if start is None:
        print("No table found in joblist.md")
        return
    preamble, (rows, _) = lines[:start], parse_table(lines[start:])
    print(f"{len(rows)} row(s) in joblist.md")

    print("Querying JobTech...")
    by_url = index_live_ads()
    print(f"  {len(by_url)} live ad(s) indexed")

    filled, unmatched = backfill(rows, by_url)
    would_close = close_expired(rows)

    print(f"\n  filled:    {filled}")
    print(f"  expired:   {would_close} row(s) past deadline → Stängd")
    print(f"  unmatched: {len(unmatched)} row(s), left untouched:")
    for row in unmatched:
        print(f"    #{row.get('#','?'):>3}  {row.get('Företag','')[:28]:28}  "
              f"{row.get('Roll/Typ','')[:34]:34}  {row.get('URL','')[:60]}")

    if not write:
        print("\nPreview only — re-run with --write to apply.")
        return
    output = "\n".join(preamble) + "\n\n" + write_table(rows) + "\n"
    JOBLIST_PATH.write_text(output, encoding="utf-8")
    print(f"\njoblist.md written — {len(rows)} rows")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
