import json
import os
import re
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT          = Path(__file__).parent.parent
JOBLIST_PATH  = ROOT / "jobsearch" / "joblist.md"
REJECTED_PATH = ROOT / "jobsearch" / "rejected.md"
SKILL_PATH    = ROOT / "jobsearch" / "skill" / "SKILL.md"
RESULTS_PATH  = Path(__file__).parent / "results.json"
ERROR_LOG     = Path(__file__).parent / "error.log"

logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

TODAY = date.today().isoformat()

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

_GENERIC_TERMINALS = {
    "jobs", "karriar", "karriär", "career", "careers",
    "lediga-tjanster", "lediga-tjänster", "lediga-jobb",
    "open-positions", "openings", "vacancies", "vacancy",
    "join-us", "work-with-us", "jobba-hos-oss",
}


# ── Markdown table parser / writer ─────────────────────────

HEADERS_WITHOUT_DATUM = ["#", "Företag", "Roll/Typ", "Plats", "CV-bas", "Status", "URL"]
HEADERS_WITH_DATUM    = ["#", "Företag", "Roll/Typ", "Plats", "CV-bas", "Status", "Datum",
                         "Deadline", "Annons", "URL"]


def _is_generic_careers_url(url: str) -> bool:
    try:
        path = urlparse(url).path.rstrip("/")
        last_segment = path.split("/")[-1].lower()
        return last_segment in _GENERIC_TERMINALS
    except Exception:
        return False


def parse_table(lines):
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
        if cells[0].strip() == "#":
            header_line = cells
            has_datum = "Datum" in cells
            continue
        if all(re.match(r'^-+$', c.strip()) for c in cells if c.strip()):
            continue
        if not header_line:
            continue
        row = {}
        for i, h in enumerate(header_line):
            row[h] = cells[i] if i < len(cells) else ""
        rows.append(row)

    return rows, has_datum


def load_rejected_urls() -> set:
    """URLs manually deleted from joblist.md — see jobsearch/rejected.md."""
    if not REJECTED_PATH.exists():
        return set()
    urls = set()
    for line in REJECTED_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---") or stripped.startswith("| Företag"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) >= 4 and cells[3]:
            urls.add(cells[3])
    return urls


def _role_key(company, role):
    """Company + role, normalised. Case and run-together whitespace differ
    between runs; nothing else is stripped, because the roles that legitimately
    share a company differ only in a real word — Bustos advertises "Inköpare
    bygg" and "Inköpare anläggning" as separate openings."""
    return (" ".join((company or "").split()).casefold(),
            " ".join((role or "").split()).casefold())


def known_role_keys(rows):
    """Role keys already in the list, ignoring closed rows.

    jobtech dedups (company, role) within a single run, and updater dedups on
    URL. Neither catches a role re-advertised under a fresh tracking id a week
    later: the URL is new, and the two sightings were never in the same batch.

    Closed rows are excluded on purpose. If the earlier posting has ended, the
    same role appearing again is a real opening rather than a second row for a
    live one.
    """
    return {
        _role_key(row.get("Företag", ""), row.get("Roll/Typ", ""))
        for row in rows
        if row.get("Status", "").strip().lower() != "stängd"
    }


def cv_base_for_role(role_type):
    rt = role_type.lower()
    for keyword, cv in ROLE_CV_MAP.items():
        if keyword in rt:
            return cv
    return "CV"


def close_expired(rows, today=None):
    """Mark rows whose application deadline has passed as Stängd, in place.

    Closing rather than deleting hands them to the 30-day Stängd prune below, so
    an expired role stays visible for a while instead of vanishing the morning
    after its deadline. A blank Deadline is left alone — rows added before the
    column existed have no deadline to judge, and an unknown one is not an
    expired one.
    """
    today = today or TODAY
    closed = 0
    for row in rows:
        due = row.get("Deadline", "").strip()
        if due and due < today and row.get("Status", "").strip().lower() != "stängd":
            row["Status"] = "Stängd"
            row["Datum"]  = today
            closed += 1
    return closed


def write_table(rows):
    headers = HEADERS_WITH_DATUM
    sep = "|" + "|".join("---" for _ in headers) + "|"
    header_row = "| " + " | ".join(headers) + " |"

    lines = [header_row, sep]
    for row in rows:
        cells = [
            row.get("#", ""),
            row.get("Företag", ""),
            row.get("Roll/Typ", ""),
            row.get("Plats", "—"),
            row.get("CV-bas", ""),
            row.get("Status", ""),
            row.get("Datum", TODAY),
            row.get("Deadline", ""),
            row.get("Annons", ""),
            row.get("URL", ""),
        ]
        # A literal "|" in any field (e.g. a role title copied from a site that
        # uses "|" as a separator) would otherwise split into extra table
        # columns and shift every field after it out of alignment.
        cells = [str(c).replace("|", "/") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────

def update_joblist():
    print(f"[{datetime.now().isoformat()}] updater.py starting")

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

    try:
        with open(JOBLIST_PATH, encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logging.error(f"Failed to read joblist.md: {e}")
        raise

    lines = content.splitlines()

    table_start = next((i for i, l in enumerate(lines) if l.strip().startswith("|")), None)
    if table_start is None:
        logging.error("No table found in joblist.md")
        return

    preamble = lines[:table_start]
    table_lines = lines[table_start:]

    rows, has_datum = parse_table(table_lines)

    if not has_datum:
        print("  Adding Datum column to existing rows")
        for row in rows:
            row["Datum"] = TODAY

    url_index = {row["URL"].strip(): i for i, row in enumerate(rows)}

    for job in closed_jobs:
        url = job.get("url", "").strip()
        if url in url_index:
            rows[url_index[url]]["Status"] = "Stängd"
            rows[url_index[url]]["Datum"]  = TODAY
            print(f"  CLOSED: {job.get('company')} → status set to Stängd")

    known_urls = {row["URL"].strip() for row in rows}
    known_roles = known_role_keys(rows)
    rejected_urls = load_rejected_urls()
    for job in new_jobs:
        url = job.get("url", "").strip()
        if url in known_urls:
            print(f"  SKIP (duplicate): {url}")
            continue
        if url in rejected_urls:
            print(f"  SKIP (rejected): {url}")
            continue
        role_key = _role_key(job.get("company", ""), job.get("role", ""))
        if role_key in known_roles:
            # Logged rather than dropped quietly: this is the one skip that can
            # be wrong, and a false positive would otherwise be invisible.
            logging.error(f"SKIP (duplicate role): {job.get('company')} — {job.get('role')}")
            print(f"  SKIP (duplicate role, already in list): "
                  f"{job.get('company')} — {job.get('role')}")
            continue
        new_row = {
            "#":        str(len(rows) + 1),
            "Företag":  job.get("company", ""),
            "Roll/Typ": job.get("role", ""),
            "Plats":    job.get("location", "") or "—",
            "CV-bas":   job.get("cv_base") or cv_base_for_role(job.get("role_type", "")),
            "Status":   "Identifierad",
            "Datum":    TODAY,
            "Deadline": job.get("deadline", ""),
            "Annons":   job.get("ad_url") or url,
            "URL":      url,
        }
        rows.append(new_row)
        known_urls.add(url)
        known_roles.add(role_key)
        print(f"  ADDED: {new_row['Företag']} — {new_row['Roll/Typ']}")
        if _is_generic_careers_url(url):
            logging.error(f"WARNING: generic careers URL for {new_row['Företag']}: {url}")
            print(f"  WARNING: URL looks like a careers page, not a specific posting — {url}")

    closed_on_deadline = close_expired(rows)
    if closed_on_deadline:
        print(f"  {closed_on_deadline} row(s) past deadline → Stängd")

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

    for i, row in enumerate(rows, 1):
        row["#"] = str(i)

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
