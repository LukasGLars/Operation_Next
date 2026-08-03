"""
build_portfolio_pdf.py — renders README.md (the project portfolio) to a
clean PDF for attaching to job applications as a supporting document.

README.md is the canonical, up-to-date source (also what the generation
pipeline reads directly, see app/app.py PORTFOLIO_MD) -- this just
produces a presentable PDF export of the same content, nothing more.

Usage:
    python pipeline/build_portfolio_pdf.py
"""
from __future__ import annotations

from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT       = Path(__file__).parent.parent
README     = ROOT / "README.md"
OUT_PDF    = ROOT / "jobsearch" / "portfolio" / "git_Lukas_Portfolio.pdf"

CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 18pt; margin-bottom: 2pt; }
h2 { font-size: 11pt; color: #444; margin-top: 0; font-weight: normal; }
h3 { font-size: 12pt; margin-top: 14pt; margin-bottom: 4pt; border-bottom: 1px solid #ccc; padding-bottom: 2pt; }
p { margin: 4pt 0; }
ul { margin: 4pt 0; padding-left: 16pt; }
li { margin: 2pt 0; }
strong { color: #111; }
a { color: #2563eb; text-decoration: none; }
hr { border: none; border-top: 1px solid #ddd; margin: 10pt 0; }
em { color: #555; }
"""


def build() -> None:
    md_text = README.read_text(encoding="utf-8")
    body_html = markdown.markdown(md_text, extensions=["extra"])
    full_html = f"<html><head><style>{CSS}</style></head><body>{body_html}</body></html>"

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PDF, "wb") as f:
        result = pisa.CreatePDF(full_html, dest=f)

    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} error(s)")
    print(f"Saved: {OUT_PDF}  ({OUT_PDF.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
