"""
app.py — Operation Next document generator
Run with: python app.py
Open at: http://localhost:5003
"""
import subprocess
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
SKILL_PATH       = ROOT / "jobsearch" / "skill" / "generation_skill.md"
REVIEW_SKILL_PATH = ROOT / "jobsearch" / "skill" / "review_skill.md"
LETTER_DOCX      = ROOT / "jobsearch" / "letters" / "Lukas_Larsson_Cover_Letter_Einride.docx"
APPLICATIONS     = ROOT / "jobsearch" / "applications"
MASTER_CV        = ROOT / "jobsearch" / "cv" / "master_cv.md"
SALES_PHILOSOPHY = ROOT / "jobsearch" / "sales_philosophy.md"

_HEADERS = ["#", "Företag", "Roll/Typ", "Plats", "CV-bas", "Status", "Datum", "URL"]

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


def _save_meta(folder: Path, company: str, role: str):
    """Full company/role text, kept separately from the folder name -- that
    name only carries the first word of the role (see _app_folder) and isn't
    enough to tell roles apart when picking a similar past example."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(
        json.dumps({"company": company, "role": role}, ensure_ascii=False),
        encoding="utf-8",
    )


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
            row.get("Plats", "—"), row.get("CV-bas", ""), row.get("Status", ""),
            row.get("Datum", today), row.get("URL", ""),
        ]
        cells = [str(c).replace("|", "/") for c in cells]
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
    _push_joblist()


def _delete_job_row(url: str):
    preamble, rows = _parse_joblist_raw()
    rows = [r for r in rows if r.get("URL", "").strip() != url]
    for i, row in enumerate(rows, 1):
        row["#"] = str(i)
    _write_joblist_raw(preamble, rows)
    _push_joblist()


def _push_joblist():
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "jobsearch/"], check=True, capture_output=True)
        result = subprocess.run(["git", "-C", str(ROOT), "diff", "--staged", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(["git", "-C", str(ROOT), "commit", "-m", "App: update jobsearch/"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(ROOT), "push"], check=True, capture_output=True)
    except Exception as e:
        logging.error(f"_push_joblist failed: {e}")


# ── Document generation helpers ────────────────────────────

def parse_joblist():
    _, rows = _parse_joblist_raw()
    return rows


def read_docx_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_jsonld_job(soup) -> str | None:
    """Extract job content from JSON-LD structured data (Teamtailor, Jobylon, Greenhouse etc.)."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = next((x for x in data if isinstance(x, dict) and x.get("@type") in ("JobPosting", "Job")), None)
            if isinstance(data, dict) and "@graph" in data:
                data = next((x for x in data["@graph"] if isinstance(x, dict) and x.get("@type") in ("JobPosting", "Job")), data)
            if not isinstance(data, dict) or data.get("@type") not in ("JobPosting", "Job"):
                continue
            parts = []
            if data.get("title"):
                parts.append(f"Title: {data['title']}")
            org = data.get("hiringOrganization")
            if org:
                parts.append(f"Company: {org.get('name', org) if isinstance(org, dict) else org}")
            loc = data.get("jobLocation")
            if loc:
                if isinstance(loc, list):
                    loc = loc[0]
                if isinstance(loc, dict):
                    addr = loc.get("address", {})
                    city = addr.get("addressLocality", "") if isinstance(addr, dict) else str(addr)
                    parts.append(f"Location: {city}")
            for field in ["description", "qualifications", "responsibilities", "skills"]:
                val = data.get(field)
                if val and isinstance(val, str):
                    clean = BeautifulSoup(val, "html.parser").get_text(separator="\n", strip=True)
                    parts.append(f"{field.capitalize()}:\n{clean[:3000]}")
            if data.get("datePosted"):
                parts.append(f"Posted: {data['datePosted']}")
            if parts:
                return "\n\n".join(parts)
        except Exception:
            continue
    return None


def fetch_job_posting(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        jsonld = _extract_jsonld_job(soup)
        if jsonld:
            return jsonld[:6000]
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:6000]
    except Exception as e:
        logging.error(f"fetch_job_posting failed: {e}")
        return f"Could not fetch job posting: {e}"


def _build_doc_content(cv_base: str, job_url: str, job_posting_text: str) -> list:
    skill_content      = SKILL_PATH.read_text(encoding="utf-8") if SKILL_PATH.exists() else ""
    master_cv_text     = MASTER_CV.read_text(encoding="utf-8") if MASTER_CV.exists() else ""
    sales_phil_text    = SALES_PHILOSOPHY.read_text(encoding="utf-8") if SALES_PHILOSOPHY.exists() else ""
    cover_letter_text  = read_docx_text(LETTER_DOCX) if LETTER_DOCX.exists() else ""

    # Static reference docs -- identical on every /generate call. Cached
    # separately from the job-specific tail so repeat calls only pay full
    # price for the posting text, not the whole CV + skill + tone reference.
    static_text = (
        "Generation instructions — follow all rules here exactly:\n" + skill_content +
        "\n\nMaster CV — complete work history and all projects. Select and tailor from this:\n" + master_cv_text +
        "\n\nSales philosophy — use paragraph from this for technical sales cover letters (para 3):\n" + sales_phil_text +
        "\n\nCover letter tone reference (match this tone and length):\n" + cover_letter_text
    )
    dynamic_text = (
        "\n\nJob posting URL: " + job_url +
        "\nJob posting content:\n" + job_posting_text +
        '\n\nGenerate a full tailored CV and cover letter for this role, in the SAME LANGUAGE\n'
        'as the job posting above (English posting -> English CV; Swedish posting -> Swedish CV;\n'
        'per SKILL.md language rules -- never default to Swedish regardless of posting language).\n'
        'Return ONLY a valid JSON object with no other text:\n'
        '{"cv": "full CV in markdown, in the job posting'"'"'s language", "cover_letter": "full cover letter in plain text, same language"}'
    )
    return [
        {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_text},
    ]


def _match_similar_role(client, role: str, company: str, candidates: list[str]) -> int | None:
    """One Claude call: which past role (by list position) is closest to the
    new one in function, seniority and register. Split out from
    _matched_edited_examples so tests can stub the judgement without an API
    call, same pattern as _validate_chunk / _judge_chunk in pipeline/."""
    listing = "\n".join(f"{i}. {title}" for i, title in enumerate(candidates, 1))
    prompt = (
        f"New role: {role} at {company}\n\n"
        f"Past roles with human-edited application examples:\n{listing}\n\n"
        "Which past role is closest to the new role in function, seniority and register? "
        "Roles in different fields (e.g. technical field sales vs. digital business "
        "development) are NOT close even if both are commercial. "
        "Reply with only the number, or NONE if nothing is a reasonable match."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response.content[0].text.strip()
    match = re.search(r"\d+", answer)
    if "NONE" in answer.upper() or not match:
        return None
    idx = int(match.group()) - 1
    return idx if 0 <= idx < len(candidates) else None


def _matched_edited_examples(client, company: str, role: str) -> str:
    """Human-approved edit closest to the new role, paired with its AI draft
    where available -- the diff between draft and edit is the clearest
    signal of what gets rejected, stronger than just showing a finished
    example.

    Replaces picking the single newest edit regardless of role. A technical
    field-sales edit (Thomas Betong) has nothing to teach a digital business
    developer draft (Voi) -- wrong register and wrong content entirely.
    Matching is one Claude call over past role titles rather than a fixed
    taxonomy, since roles applied for don't cluster into a few clean buckets.
    Returns "" rather than forcing a weak match when nothing is close."""
    if not role:
        return ""
    current_folder = _app_folder(company, role) if company else None
    candidates = []
    for folder in sorted(p for p in APPLICATIONS.glob("*") if p.is_dir()):
        if folder == current_folder:
            continue
        if not ((folder / "cv_edited.md").exists() or (folder / "cover_letter_edited.md").exists()):
            continue
        meta_path = folder / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            title = f"{meta.get('role', '')} at {meta.get('company', '')}".strip()
        else:
            title = folder.name.replace("_", " ")
        candidates.append((folder, title))
    if not candidates:
        return ""

    try:
        idx = _match_similar_role(client, role, company, [title for _, title in candidates])
    except Exception as e:
        logging.error(f"Example matching failed: {e}")
        return ""
    if idx is None:
        return ""
    folder, title = candidates[idx]

    blocks = []
    for label, stem in (("Cover letter", "cover_letter"), ("CV", "cv")):
        edited_path = folder / f"{stem}_edited.md"
        if not edited_path.exists():
            continue
        edited_text = edited_path.read_text(encoding="utf-8")
        original_path = folder / f"{stem}_original.md"
        if original_path.exists():
            original_text = original_path.read_text(encoding="utf-8")
            blocks.append(
                f"{label} example -- AI draft (REJECTED patterns, avoid repeating these):\n"
                f"{original_text}\n\n"
                f"{label} example -- human-approved final version, from a similar role "
                f"({title}) -- match this instead:\n{edited_text}"
            )
        else:
            blocks.append(
                f"{label} example -- human-approved final version, from a similar role "
                f"({title}) -- match this:\n{edited_text}"
            )
    return "\n\n---\n\n".join(blocks)


def _build_review_content(draft_cv: str, draft_cover_letter: str, job_posting_text: str, recent_examples: str) -> list:
    """Second pass, per jobsearch/skill/review_skill.md: refines the draft
    to actually speak to what THIS company is anxious about and to read as
    written by a native speaker who understood the ad, rather than a
    translation. Never wired into the generation flow before -- the skill
    file existed but nothing called it."""
    review_skill_content = REVIEW_SKILL_PATH.read_text(encoding="utf-8") if REVIEW_SKILL_PATH.exists() else ""

    # Static across every /review call -- cached separately from the
    # per-request draft/posting text, which changes every time.
    static_text = (
        "Review instructions — follow all rules here exactly:\n" + review_skill_content +
        ("\n\nRecent human-approved edits -- the AI draft/final pairs below show exactly what gets "
         "rejected in practice: canned opening lines, repeated rhetorical devices, translated-sounding "
         "phrasing, inflated job titles, tool lists in place of stances, and bullets that name internal "
         "tech instead of what colleagues get. Do not repeat any pattern shown as rejected, and match "
         "the voice and structure of the approved versions:\n" + recent_examples if recent_examples else "")
    )
    dynamic_text = (
        "\n\nJob posting content:\n" + job_posting_text +
        "\n\nDraft CV:\n" + draft_cv +
        "\n\nDraft cover letter:\n" + draft_cover_letter +
        '\n\nRefine the draft CV and cover letter per the review instructions above. '
        'Keep the same language they are already written in -- do not translate.\n'
        'Return ONLY a valid JSON object with no other text:\n'
        '{"cv": "full refined CV in markdown", "cover_letter": "full refined cover letter in plain text"}'
    )
    return [
        {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_text},
    ]


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

@app.before_request
def auto_pull():
    if request.method == "GET":
        subprocess.run(["git", "-C", str(ROOT), "pull"], capture_output=True)


@app.route("/")
def index():
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
        job_posting_text = fetch_job_posting(job_url)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="You are Lukas Larsson's job application assistant. Generate a tailored CV and cover letter using the provided reference documents and instructions. Output only valid JSON.",
            messages=[{"role": "user", "content": _build_doc_content(cv_base, job_url, job_posting_text)}],
        )
        result = _parse_claude_json(response.content[0].text)

        # Review pass (jobsearch/skill/review_skill.md) -- refines the draft
        # to speak to what THIS company is actually anxious about and to read
        # as native, not translated. Falls back to the unreviewed draft on
        # any failure rather than breaking generation entirely.
        if result.get("cv") and result.get("cover_letter"):
            try:
                recent_examples = _matched_edited_examples(client, company, role)
                review_response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system="You are Lukas Larsson's job application assistant, now reviewing your own draft. Output only valid JSON.",
                    messages=[{"role": "user", "content": _build_review_content(
                        result["cv"], result["cover_letter"], job_posting_text, recent_examples)}],
                )
                reviewed = _parse_claude_json(review_response.content[0].text)
                if reviewed.get("cv") and reviewed.get("cover_letter"):
                    result = reviewed
            except Exception as e:
                logging.error(f"Review pass failed, using unreviewed draft: {e}")

        try:
            _update_job_row(job_url, {"Status": "Genererat", "Datum": date.today().isoformat()})
        except Exception as e:
            logging.error(f"Status update after generation failed: {e}")
        if company and role and result.get("cv"):
            try:
                folder = _app_folder(company, role)
                _save_docs(folder, result["cv"], result.get("cover_letter", ""), "original")
                _save_meta(folder, company, role)
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
        _save_meta(folder, company, role)
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
