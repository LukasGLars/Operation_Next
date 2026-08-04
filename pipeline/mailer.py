import json
import os
import smtplib
import logging
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "results.json"
ERROR_LOG    = Path(__file__).parent / "error.log"

logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)


STAT_LABELS = [
    ("web_candidates",     "Kandidater från websökning"),
    ("jobtech_candidates", "Kandidater från Platsbanken"),
    ("reachable",          "Nåbara URL:er"),
    ("in_range",           "Inom pendlingsavstånd"),
    ("validated",          "Godkända av validering"),
]


def should_send(new_jobs, errors):
    """Mail on new roles and on failures only. Closed ads are still recorded in
    the joblist, they just do not warrant a mail. A dead pipeline still reports,
    because a missing or stale results.json counts as an error, and a hard crash
    fails the Actions job."""
    return bool(new_jobs or errors)


def build_subject(new_jobs, errors):
    today = date.today().isoformat()
    if errors:
        return f"Operation Next — FEL I PIPELINE ({len(errors)}) {today}"
    return f"Operation Next — {len(new_jobs)} nya roller {today}"


def stale_warning(timestamp):
    """A results.json from an earlier day means search.py never got to write one."""
    if not timestamp:
        return "results.json saknar timestamp — kördes search.py?"
    if timestamp[:10] != date.today().isoformat():
        return f"results.json är från {timestamp[:10]}, inte idag — search.py kan ha kraschat"
    return ""


def build_body(new_jobs, closed_jobs, stats=None, errors=None):
    lines = []

    lines.append(f"Operation Next — Daglig uppdatering {date.today().isoformat()}")
    lines.append("=" * 50)

    if errors:
        lines.append(f"\n{len(errors)} FEL UNDER KÖRNINGEN\n")
        for error in errors:
            lines.append(f"  ! {error}")
        lines.append("")
        lines.append("Noll nya roller kan bero på detta och inte på att marknaden är tom.")

    if not new_jobs and not closed_jobs and not errors:
        lines.append("\nInga nya eller stängda roller. Pipelinen kördes utan fel.")

    if new_jobs:
        lines.append(f"\n{len(new_jobs)} NYA ROLLER\n")
        for job in new_jobs:
            lines.append(f"{job.get('company', '—')} — {job.get('role', '—')}")
            lines.append(f"Typ: {job.get('role_type', '—')}")
            lines.append(f"CV-bas: {job.get('cv_base', 'CV')}")
            lines.append(f"URL: {job.get('url', '—')}")
            lines.append("")

    if closed_jobs:
        lines.append(f"\n{len(closed_jobs)} STÄNGDA ANNONSER\n")
        for job in closed_jobs:
            lines.append(f"{job.get('company', '—')} — {job.get('role', '—')}")
            lines.append(f"URL: {job.get('url', '—')}")
            lines.append("")

    if stats:
        lines.append("\nSTATUS PER STEG\n")
        for key, label in STAT_LABELS:
            if key in stats:
                lines.append(f"  {label}: {stats[key]}")
        lines.append("")

    lines.append("=" * 50)
    lines.append("Operation Next Pipeline")

    return "\n".join(lines)


def send_digest():
    print(f"[{datetime.now().isoformat()}] mailer.py starting")

    # Load results. A missing or unreadable file is itself worth mailing about —
    # it means search.py did not finish.
    results = {}
    errors  = []
    if not RESULTS_PATH.exists():
        errors.append("results.json saknas — search.py skrev aldrig något resultat")
    else:
        try:
            with open(RESULTS_PATH, encoding="utf-8") as f:
                results = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Failed to read results.json: {e}")
            print(f"  ERROR: {e}")
            errors.append(f"results.json kunde inte läsas: {str(e)[:120]}")

    new_jobs    = results.get("new_jobs", [])
    closed_jobs = results.get("closed_jobs", [])
    stats       = results.get("stats", {})
    errors     += results.get("errors", [])

    if results:
        stale = stale_warning(results.get("timestamp", ""))
        if stale:
            errors.append(stale)

    if not should_send(new_jobs, errors):
        print("  No new roles and no errors — no mail sent")
        return

    # Credentials
    mail_from = os.environ.get("MAIL_FROM", "")
    mail_to   = os.environ.get("MAIL_TO", "")
    password  = os.environ.get("MAIL_PASSWORD", "")

    if not all([mail_from, mail_to, password]):
        logging.error("Missing mail credentials — set MAIL_FROM, MAIL_TO, MAIL_PASSWORD")
        print("  ERROR: mail credentials not set")
        return

    # Build message — only reached when there is news or a failure to report.
    subject = build_subject(new_jobs, errors)
    body    = build_body(new_jobs, closed_jobs, stats, errors)

    msg = MIMEMultipart()
    msg["From"]    = mail_from
    msg["To"]      = mail_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Send
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(mail_from, password)
            server.send_message(msg)
        print(f"  Mail sent to {mail_to} — {len(new_jobs)} new, {len(closed_jobs)} closed")
    except Exception as e:
        logging.error(f"SMTP failed: {e}")
        print(f"  ERROR: mail failed — see error.log")

    print(f"[{datetime.now().isoformat()}] mailer.py done")


if __name__ == "__main__":
    send_digest()
