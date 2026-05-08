"""
app.py — Operation Next document generator
Run with: python app.py
Open at: http://localhost:5003
"""
import subprocess
import base64
import json
import logging
import os
import re
from datetime import date
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup
from docx import Document
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(Path(__file__).parent.parent / ".env")

ROOT          = Path(__file__).parent.parent
JOBLIST_PATH  = ROOT / "jobsearch" / "joblist.md"
SKILL_PATH    = ROOT / "jobsearch" / "skill" / "SKILL.md"
CV_DIR        = ROOT / "jobsearch" / "cv"
PORTFOLIO_PDF = ROOT / "jobsearch" / "portfolio" / "git_Lukas_Portfolio.pdf"
LETTER_DOCX   = ROOT / "jobsearch" / "letters" / "Lukas_Larsson_Cover_Letter_Einride.docx"
APPLICATIONS  = ROOT / "jobsearch" / "applications"

CV_BASE_FILES = {
    "CV_Einride":   "Lukas_Larsson_CV_Einride.pdf",
    "CV_Zeppelin":  "Lukas_Larsson_CV_Zeppelin.pdf",
    "CV_Plymovent": "Lukas_Larsson_CV_Plymovent.pdf",
    "CV_BYGG":      "Lukas_Larsson_CV_BYGG.pdf",
    "CV":           "Lukas_Larsson_CV.pdf",
}

_HEADERS = ["#", "Företag", "Roll/Typ", "CV-bas", "Status", "Datum", "URL"]

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR)


# ── Application file helpers ───────────────────────────────

def _app_folder(company: str, role: str) -> Path:
    def slug(s):
        s = s.lower().strip()
        s = re.sub(r"[^a-z0-9]", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s
    role_first = role.split("/")[0].split(" ")[0].strip() if role else ""
    return APPLICATIONS / (slug(company) + "_" + slug(role_first))


def _save_docs(folder: Path, cv: str, cover_letter: str, suffix: str):
    folder.mkdir(parents=True, exist_ok=True)
    cv_path = folder / f"cv_{suffix}.md"
    cl_path = folder / f"cover_letter_{suffix}.md"
    if not cv_path.exists() or suffix != "original":
        cv_path.write_text(cv, encoding="utf-8")
    if not cl_path.exists() or suffix != "original":
        cl_path.write_text(cover_letter, encoding="utf-8")


# ── Joblist read/write ─────────────────────────────────────

def _parse_joblist_raw():
    if not JOBLIST_PATH.exists():
        return [], []
    with open(JOBLIST_PATH, encoding="utf-8") as f:
        lines = f.read().splitlines()
    table_start = next((i for i, l in enumerate(lines) if l.strip().startswith("|")), None)
    if table_start is None:
        return lines, []
    preamble = lines[:table_start]
    header = None
    rows = []
    for line in lines[table_start:]:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        if cells[0] == "#":
            header = cells
            continue
        if all(re.match(r"^-+$", c) for c in cells if c):
            continue
        if header:
            rows.append({header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))})
    return preamble, rows


def _write_joblist_raw(preamble, rows):
    today = date.today().isoformat()
    sep = "|" + "|".join("---" for _ in _HEADERS) + "|"
    table_lines = ["| " + " | ".join(_HEADERS) + " |", sep]
    for row in rows:
        cells = [
            row.get("#", ""), row.get("Företag", ""), row.get("Roll/Typ", ""),
            row.get("CV-bas", ""), row.get("Status", ""),
            row.get("Datum", today), row.get("URL", ""),
        ]
        table_lines.append("| " + " | ".join(cells) + " |")
    output = "\n".join(preamble) + "\n\n" + "\n".join(table_lines) + "\n"
    with open(JOBLIST_PATH, "w", encoding="utf-8") as f:
        f.write(output)


def _update_job_row(url: str, updates: dict):
    preamble, rows = _parse_joblist_raw()
    for row in rows:
        if row.get("URL", "").strip() == url:
            row.update(updates)
            break
    _write_joblist_raw(preamble, rows)


def _delete_job_row(url: str):
    preamble, rows = _parse_joblist_raw()
    rows = [r for r in rows if r.get("URL", "").strip() != url]
    for i, row in enumerate(rows, 1):
        row["#"] = str(i)
    _write_joblist_raw(preamble, rows)


# ── Document generation helpers ────────────────────────────

def parse_joblist():
    _, rows = _parse_joblist_raw()
    return rows


def read_pdf_b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def read_docx_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def fetch_job_posting(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:6000]
    except Exception as e:
        logging.error(f"fetch_job_posting failed: {e}")
        return f"Could not fetch job posting: {e}"


def _build_doc_content(cv_base: str, job_url: str) -> list:
    skill_content     = SKILL_PATH.read_text(encoding="utf-8") if SKILL_PATH.exists() else ""
    job_posting_text  = fetch_job_posting(job_url)
    cover_letter_text = read_docx_text(LETTER_DOCX) if LETTER_DOCX.exists() else ""

    cv_filename = CV_BASE_FILES.get(cv_base, CV_BASE_FILES["CV_Einride"])
    cv_path     = CV_DIR / cv_filename
    if not cv_path.exists():
        cv_path = CV_DIR / CV_BASE_FILES["CV_Einride"]

    content = [{
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": read_pdf_b64(cv_path)},
        "title": f"CV Reference ({cv_base})",
        "cache_control": {"type": "ephemeral"},
    }]
    if PORTFOLIO_PDF.exists():
        content.append({
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": read_pdf_b64(PORTFOLIO_PDF)},
            "title": "Portfolio",
            "cache_control": {"type": "ephemeral"},
        })
    prompt = (
        "SKILL.md — follow all rules here exactly:\n" + skill_content +
        "\n\nCover letter tone reference (match this tone and length):\n" + cover_letter_text +
        "\n\nJob posting URL: " + job_url +
        "\nJob posting content:\n" + job_posting_text +
        '\n\nGenerate a full tailored CV and cover letter for this role.\n'
        'Return ONLY a valid JSON object with no other text:\n'
        '{"cv": "full CV in markdown, in Swedish", "cover_letter": "full cover letter in plain text"}'
    )
    content.append({"type": "text", "text": prompt})
    return content


def _parse_claude_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON found in response")


# ── Routes ─────────────────────────────────────────────────

@app.route("/")
def index():
    subprocess.run(["git", "-C", str(ROOT), "pull"], capture_output=True)
    return render_template("index.html", jobs=parse_joblist())


@app.route("/generate", methods=["GET"])
def generate_page():
    return render_template("generate.html",
        company  = request.args.get("company", ""),
        role     = request.args.get("role", ""),
        cv_base  = request.args.get("cv_base", "CV_Einride"),
        url      = request.args.get("url", ""),
        location = request.args.get("location", ""),
    )


@app.route("/generate", methods=["POST"])
def generate():
    data    = request.get_json()
    job_url = (data.get("url") or "").strip()
    cv_base = (data.get("cv_base") or "CV_Einride").strip()
    company = (data.get("company") or "").strip()
    role    = (data.get("role") or "").strip()
    if not job_url:
        return jsonify({"error": "No job URL provided"}), 400

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="You are Lukas Larsson's job application assistant. Generate a tailored CV and cover letter using the provided reference documents and instructions. Output only valid JSON.",
            messages=[{"role": "user", "content": _build_doc_content(cv_base, job_url)}],
        )
        result = _parse_claude_json(response.content[0].text)
        try:
            _update_job_row(job_url, {"Status": "Genererat", "Datum": date.today().isoformat()})
        except Exception as e:
            logging.error(f"Status update after generation failed: {e}")
        if company and role and result.get("cv"):
            try:
                folder = _app_folder(company, role)
                _save_docs(folder, result["cv"], result.get("cover_letter", ""), "original")
            except Exception as e:
                logging.error(f"Save original failed: {e}")
        return jsonify(result)
    except Exception as e:
        logging.error(f"Generation failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/save", methods=["POST"])
def save_edited():
    data         = request.get_json()
    company      = (data.get("company") or "").strip()
    role         = (data.get("role") or "").strip()
    cv           = (data.get("cv") or "").strip()
    cover_letter = (data.get("cover_letter") or "").strip()
    if not company or not role:
        return jsonify({"error": "company and role required"}), 400
    try:
        folder = _app_folder(company, role)
        _save_docs(folder, cv, cover_letter, "edited")
        return jsonify({"ok": True, "folder": str(folder.relative_to(ROOT))})
    except Exception as e:
        logging.error(f"Save edited failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/status", methods=["POST"])
def update_status():
    data   = request.get_json()
    url    = (data.get("url") or "").strip()
    status = (data.get("status") or "").strip()
    if not url or not status:
        return jsonify({"error": "url and status required"}), 400
    try:
        _update_job_row(url, {"Status": status, "Datum": date.today().isoformat()})
        return jsonify({"ok": True})
    except Exception as e:
        logging.error(f"Status update failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/delete", methods=["POST"])
def delete_job():
    data = request.get_json()
    url  = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    try:
        _delete_job_row(url)
        return jsonify({"ok": True})
    except Exception as e:
        logging.error(f"Delete failed: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("Operation Next starting on http://localhost:5003")
    app.run(debug=True, port=5003)
