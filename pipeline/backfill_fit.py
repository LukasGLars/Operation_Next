# -*- coding: utf-8 -*-
"""Score joblist rows that predate fit scoring and write the result in.

Rows added before v0.7.0 have a blank Fit cell. New rows get scored by the
judge during a run; these never will, because `fetch_candidates` skips URLs
already in the joblist. One-off, but idempotent — it only touches rows whose
Fit is empty, so re-running it costs nothing and re-scores nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv                             # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

from pipeline import adrequirements, fitscore, jobtech, updater  # noqa: E402
from pipeline.search import fetch_page_text                # noqa: E402


def main():
    lines = updater.JOBLIST_PATH.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("|"))
    preamble, (rows, _) = lines[:start], updater.parse_table(lines[start:])

    force = "--force" in sys.argv
    have_reqs = set(adrequirements.load())
    todo = [r for r in rows
            if force or not (r.get("Fit") or "").strip()
            or not (r.get("Fit-delar") or "").strip()
            or updater.canonical_url(r.get("URL", "")) not in have_reqs]
    if not todo:
        print("Every row already has a score.")
        return 0
    print(f"Scoring {len(todo)} of {len(rows)} rows...")

    skill = (updater.ROOT / "jobsearch" / "skill" / "search_skill.md").read_text(encoding="utf-8")

    candidates = []
    for row in todo:
        url = (row.get("URL") or "").strip()
        try:
            page = fetch_page_text(url) if url else ""
        except Exception:
            page = ""
        candidates.append({
            "company": row.get("Företag", ""), "role": row.get("Roll/Typ", ""),
            "role_type": "", "location": row.get("Plats", ""),
            "_page_text": page or f"{row.get('Roll/Typ','')} {row.get('Företag','')}",
            "_row": row,
        })

    scored = 0
    found_reqs = {}
    for i in range(0, len(candidates), jobtech.JUDGE_CHUNK_SIZE):
        chunk = candidates[i:i + jobtech.JUDGE_CHUNK_SIZE]
        verdicts = jobtech._judge_chunk(chunk, skill)
        for n, c in enumerate(chunk, 1):
            if n not in verdicts:
                continue            # leave it blank; an unscored row is not a 0
            c["_row"]["Fit"] = str(fitscore.from_verdict(verdicts[n]))
            c["_row"]["Fit-delar"] = fitscore.axes_string(verdicts[n])
            bullets = adrequirements.clean(verdicts[n].get("requirements"))
            if bullets:
                found_reqs[updater.canonical_url(c["_row"].get("URL", ""))] = bullets
            scored += 1

    if not scored:
        print("ABORT: nothing came back scored — joblist untouched. "
              "Check ANTHROPIC_API_KEY and pipeline/error.log.")
        return 2

    updater.JOBLIST_PATH.write_text(
        "\n".join(preamble) + "\n" + updater.write_table(rows) + "\n", encoding="utf-8")
    print(f"Wrote {scored} score(s) to joblist.md")
    saved = adrequirements.save(found_reqs)
    print(f"Wrote requirements for {saved} row(s)")

    for r in sorted(rows, key=lambda r: -int(r.get("Fit") or 0))[:10]:
        print(f"  {r.get('Fit',''):>3}  {r.get('Företag','')[:24]:24s} {r.get('Roll/Typ','')[:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
