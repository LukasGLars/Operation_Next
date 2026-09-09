# -*- coding: utf-8 -*-
"""Score the rows already in joblist.md and check the rubric against outcomes.

The point of this script is to be able to fail. Four rows reached Intervju; if
the rubric does not rank them near the top of a list it has never seen labelled,
it is encoding the wrong thing and should be changed before it goes anywhere
near a live run. Run it after any change to fitscore.RUBRIC or its weights.

Not a pytest: it costs real API calls and needs the network, so it stays a
script you run deliberately.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv                             # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")         # the app does this; CI uses secrets

from pipeline import jobtech, updater                      # noqa: E402
from pipeline.search import fetch_page_text                # noqa: E402

CONVERTED = {"intervju"}
APPLIED   = {"ansökt"}


def main():
    lines = updater.JOBLIST_PATH.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("|"))
    rows, _ = updater.parse_table(lines[start:])

    skill = (updater.ROOT / "jobsearch" / "skill" / "search_skill.md").read_text(encoding="utf-8")

    candidates = []
    for row in rows:
        url = row.get("URL", "").strip()
        try:
            page = fetch_page_text(url) if url else ""
        except Exception:
            page = ""
        candidates.append({
            "company":    row.get("Företag", ""),
            "role":       row.get("Roll/Typ", ""),
            "role_type":  "",
            "location":   row.get("Plats", ""),
            "url":        url,
            "_page_text": page or f"{row.get('Roll/Typ','')} {row.get('Företag','')}",
            "_status":    row.get("Status", "").strip().lower(),
        })

    scored = []
    for i in range(0, len(candidates), jobtech.JUDGE_CHUNK_SIZE):
        chunk = candidates[i:i + jobtech.JUDGE_CHUNK_SIZE]
        verdicts = jobtech._judge_chunk(chunk, skill)
        for n, c in enumerate(chunk, 1):
            from pipeline import fitscore
            c["fit"] = fitscore.from_verdict(verdicts.get(n))
            scored.append(c)

    graded = [c for c in scored if c["fit"] > 0]
    if len(graded) < len(scored) * 0.9:
        print("")
        print(f"ABORT: only {len(graded)} of {len(scored)} rows came back with "
              f"a score. With unscored rows at 0 the sort is just joblist order,"
              f" so the check below would report PASS without measuring "
              f"anything. Check ANTHROPIC_API_KEY and pipeline/error.log.")
        return 2

    scored.sort(key=lambda c: c["fit"], reverse=True)
    quartile = max(1, len(scored) // 4)

    print(f"\nScored {len(scored)} rows. Top quartile is the first {quartile}.\n")
    passes = 0
    converted = [c for c in scored if c["_status"] in CONVERTED]
    for c in scored:
        if c["_status"] in CONVERTED or c["_status"] in APPLIED:
            rank = scored.index(c) + 1
            ok = rank <= quartile
            passes += ok and c["_status"] in CONVERTED
            label = c["_status"].capitalize()
            print(f"  rank {rank:3d}  {c['fit']:3d}  {c['company'][:22]:22s} "
                  f"{c['role'][:34]:34s} [{label}] {'PASS' if ok else 'MISS'}")

    print(f"\n  {passes}/{len(converted)} Intervju rows in the top quartile.")
    print(f"\n  Top 8 overall:")
    for c in scored[:8]:
        print(f"    {c['fit']:3d}  {c['company'][:24]:24s} {c['role'][:44]}")
    print(f"  Bottom 5:")
    for c in scored[-5:]:
        print(f"    {c['fit']:3d}  {c['company'][:24]:24s} {c['role'][:44]}")

    ok = passes == len(converted)
    print(f"\nRESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
