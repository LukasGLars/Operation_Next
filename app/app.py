"""
app.py — Operation Next document generator
Run with: python app.py
Open at: http://localhost:5001
"""
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

CV_BASE_FILES = {
    "CV_Einride":   "Lukas_Larsson_CV_Einride.pdf",
    "CV_Zeppelin":  "Lukas_Larsson_CV_Zeppelin.pdf",
    "CV_Plymovent": "Lukas_Larsson_CV_Plymovent.pdf",
    "CV_BYGG":      "Lukas_Larsson_CV_BYGG.pdf",
    "CV":           "Lukas_Larsson_CV.pdf",
}

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR)


# ── Helpers ────────────────────────────────────────────────

def parse_joblist():
    if not JOBLIST_PATH.exists():
        return []
    jobs = []
    header = None
    with open(JOBLIST_PATH, encoding="utf-8") as f:
        for line in f:
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
                jobs.append({header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))})
    return jobs


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


# ── Routes ─────────────────────────────────────────────────

@app.route("/")
def index():
    jobs = parse_joblist()
    return render_template("index.html", jobs=jobs)


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

    if not job_url:
        return jsonify({"error": "No job URL provided"}), 400

    skill_content     = SKILL_PATH.read_text(encoding="utf-8") if SKILL_PATH.exists() else ""
    job_posting_text  = fetch_job_posting(job_url)
    cover_letter_text = read_docx_text(LETTER_DOCX) if LETTER_DOCX.exists() else ""

    cv_filename = CV_BASE_FILES.get(cv_base, CV_BASE_FILES["CV_Einride"])
    cv_path     = CV_DIR / cv_filename
    if not cv_path.exists():
        cv_path = CV_DIR / CV_BASE_FILES["CV_Einride"]

    content = [
        {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf",
                       "data": read_pdf_b64(cv_path)},
            "title": f"CV Reference ({cv_base})",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    if PORTFOLIO_PDF.exists():
        content.append({
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf",
                       "data": read_pdf_b64(PORTFOLIO_PDF)},
            "title": "Portfolio",
            "cache_control": {"type": "ephemeral"},
        })

    content.append({
        "type": "text",
        "text": f"""SKILL.md — follow all rules here exactly:
{skill_content}

Cover letter tone reference (match this tone and length):
{cover_letter_text}

Job posting URL: {job_url}
Job posting content:
{job_posting_text}

Generate a full tailored CV and cover letter for this role.
Return ONLY a valid JSON object with no other text:
{{"cv": "full CV in markdown, in Swedish", "cover_letter": "full cover letter in plain text"}}""",
    })

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="You are Lukas Larsson's job application assistant. Generate a tailored CV and cover letter using the provided reference documents and instructions. Output only valid JSON.",
            messages=[{"role": "user", "content": content}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return jsonify(json.loads(match.group()))
        return jsonify({"error": "Could not parse response", "raw": text}), 500
    except Exception as e:
        logging.error(f"Generation failed: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("Operation Next starting on http://localhost:5001")
    app.run(debug=True, port=5001)