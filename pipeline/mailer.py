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


def build_body(new_jobs, closed_jobs):
    lines = []

    lines.append(f"Operation Next — Daglig uppdatering {date.today().isoformat()}")
    lines.append("=" * 50)

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

    lines.append("=" * 50)
    lines.append("Operation Next Pipeline")

    return "\n".join(lines)


def send_digest():
    print(f"[{datetime.now().isoformat()}] mailer.py starting")

    # Load results
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
        print("  Nothing to report — no mail sent")
        return

    # Credentials
    mail_from = os.environ.get("MAIL_FROM", "")
    mail_to   = os.environ.get("MAIL_TO", "")
    password  = os.environ.get("MAIL_PASSWORD", "")

    if not all([mail_from, mail_to, password]):
        logging.error("Missing mail credentials — set MAIL_FROM, MAIL_TO, MAIL_PASSWORD")
        print("  ERROR: mail credentials not set")
        return

    # Build message
    subject = f"Operation Next — {len(new_jobs)} nya roller {date.today().isoformat()}"
    body    = build_body(new_jobs, closed_jobs)

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
