import json
import os
import re
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

ROOT         = Path(__file__).parent.parent
JOBLIST_PATH = ROOT / "jobsearch" / "joblist.md"
SKILL_PATH   = ROOT / "jobsearch" / "skill" / "SKILL.md"
RESULTS_PATH = Path(__file__).parent / "results.json"
ERROR_LOG    = Path(__file__).parent / "error.log"

logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

TODAY = date.today().isoformat()

# Default role → CV base mapping (extend via SKILL.md when populated)
ROLE_CV_MAP = {
    "business analyst":      "CV_Einride",
    "data analyst":          "CV_Einride",
    "product analyst":       "CV_Einride",
    "csm":                   "CV_Einride",
    "customer success":      "CV_Einride",
    "greentech":             "CV_Einride",
    "product manager":       "CV",
    "project manager":       "CV",
    "business development":  "CV",
    "sales engineer":        "CV_Zeppelin",
    "technical sales":       "CV_Zeppelin",
    "teknisk säljare":       "CV_Zeppelin",
    "fintech":               "CV_Einride",
    "healthtech":            "CV_Einride",
    "saas":                  "CV_Einride",
}


# ── Markdown table parser / writer ─────────────────────────

HEADERS_WITHOUT_DATUM = ["#", "Företag", "Roll/Typ", "CV-bas", "Status", "URL"]
HEADERS_WITH_DATUM    = ["#", "Företag", "Roll/Typ", "CV-bas", "Status", "Datum", "URL"]


def parse_table(lines):
    """Return list of row dicts from markdown table lines."""
    rows = []
    header_line = None
    has_datum = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        # Detect header row
        if cells[0].strip() == "#":
            header_line = cells
            has_datum = "Datum" in cells
            continue
        # Skip separator
        if all(re.match(r'^-+$', c.strip()) for c in cells if c.strip()):
            continue
        # Data row
        if not header_line:
            continue
        row = {}
        for i, h in enumerate(header_line):
            row[h] = cells[i] if i < len(cells) else ""
        rows.append(row)

    return rows, has_datum


def cv_base_for_role(role_type):
    rt = role_type.lower()
    for keyword, cv in ROLE_CV_MAP.items():
        if keyword in rt:
            return cv
    return "CV"


def write_table(rows):
    """Render rows back to markdown table string."""
    headers = HEADERS_WITH_DATUM
    sep = "|" + "|".join("---" for _ in headers) + "|"
    header_row = "| " + " | ".join(headers) + " |"

    lines = [header_row, sep]
    for row in rows:
        cells = [
            row.get("#", ""),
            row.get("Företag", ""),
            row.get("Roll/Typ", ""),
            row.get("CV-bas", ""),
            row.get("Status", ""),
            row.get("Datum", TODAY),
            row.get("URL", ""),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────

def update_joblist():
    print(f"[{datetime.now().isoformat()}] updater.py starting")

    # Load results.json
    if not RESULTS_PATH.exists():
        print("  No results.json found — exiting cleanly")
        return
    try:
        with open(RESULTS_PATH, encoding="utf-8") as f:
            results = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f"Failed to read results.json: {e}")
        print(f"  ERROR: {e}")
        return

    new_jobs    = results.get("new_jobs", [])
    closed_jobs = results.get("closed_jobs", [])

    if not new_jobs and not closed_jobs:
        print("  Nothing to update")
        return

    # Load joblist.md
    try:
        with open(JOBLIST_PATH, encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logging.error(f"Failed to read joblist.md: {e}")
        raise

    lines = content.splitlines()

    # Split into preamble and table
    table_start = next((i for i, l in enumerate(lines) if l.strip().startswith("|")), None)
    if table_start is None:
        logging.error("No table found in joblist.md")
        return

    preamble = lines[:table_start]
    table_lines = lines[table_start:]

    rows, has_datum = parse_table(table_lines)

    # Add Datum column to existing rows if missing
    if not has_datum:
        print("  Adding Datum column to existing rows")
        for row in rows:
            row["Datum"] = TODAY

    # Build URL lookup
    url_index = {row["URL"].strip(): i for i, row in enumerate(rows)}

    # Handle closed jobs
    for job in closed_jobs:
        url = job.get("url", "").strip()
        if url in url_index:
            rows[url_index[url]]["Status"] = "Stängd"
            rows[url_index[url]]["Datum"]  = TODAY
            print(f"  CLOSED: {job.get('company')} → status set to Stängd")

    # Handle new jobs — no duplicates
    known_urls = {row["URL"].strip() for row in rows}
    for job in new_jobs:
        url = job.get("url", "").strip()
        if url in known_urls:
            print(f"  SKIP (duplicate): {url}")
            continue
        new_row = {
            "#":        str(len(rows) + 1),
            "Företag":  job.get("company", ""),
            "Roll/Typ": job.get("role", ""),
            "CV-bas":   job.get("cv_base") or cv_base_for_role(job.get("role_type", "")),
            "Status":   "Identifierad",
            "Datum":    TODAY,
            "URL":      url,
        }
        rows.append(new_row)
        known_urls.add(url)
        print(f"  ADDED: {new_row['Företag']} — {new_row['Roll/Typ']}")

    # Clean up Stängd rows older than 30 days
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    before = len(rows)
    rows = [
        r for r in rows
        if not (r.get("Status", "").lower() == "stängd"
                and r.get("Datum", TODAY) < cutoff)
    ]
    removed = before - len(rows)
    if removed:
        print(f"  Pruned {removed} stale Stängd row(s)")

    # Re-number
    for i, row in enumerate(rows, 1):
        row["#"] = str(i)

    # Write back
    try:
        table_md = write_table(rows)
        output = "\n".join(preamble) + "\n\n" + table_md + "\n"
        with open(JOBLIST_PATH, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"  joblist.md updated — {len(rows)} rows")
    except OSError as e:
        logging.error(f"Failed to write joblist.md: {e}")
        raise

    print(f"[{datetime.now().isoformat()}] updater.py done")


if __name__ == "__main__":
    update_joblist()
