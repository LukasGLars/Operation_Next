"""One-off: score every existing joblist.md row that predates the Score
column. Live-fetches each ad's page text (not retained from the original
pipeline run), same TF-IDF as rank_jobs.py — no LLM calls. Run with:
    python -m pipeline.backfill_scores
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rank_jobs import CV_PATH, score_documents
from search import fetch_page_text
from updater import JOBLIST_PATH, parse_table, write_table


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    content = JOBLIST_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()
    table_start = next(i for i, l in enumerate(lines) if l.strip().startswith("|"))
    preamble = lines[:table_start]

    rows, _ = parse_table(lines[table_start:])
    todo = [row for row in rows if not row.get("Score") or row["Score"] == "—"]
    print(f"{len(todo)}/{len(rows)} row(s) need a score")

    cv_text = CV_PATH.read_text(encoding="utf-8")
    doc_texts = []
    scored_rows = []
    for row in todo:
        url = (row.get("URL") or "").strip()
        if not url:
            continue
        text = fetch_page_text(url)
        if not text:
            print(f"  SKIP (no page text): {row.get('Företag')}")
            continue
        doc_texts.append(text)
        scored_rows.append(row)
        print(f"  fetched: {row.get('Företag')}")

    scores = score_documents(cv_text, doc_texts)
    for row, score in zip(scored_rows, scores):
        row["Score"] = f"{score:.4f}"

    output = "\n".join(preamble) + "\n\n" + write_table(rows) + "\n"
    JOBLIST_PATH.write_text(output, encoding="utf-8")
    print(f"joblist.md updated — {len(scored_rows)} row(s) scored")


if __name__ == "__main__":
    main()
