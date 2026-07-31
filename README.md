# Lukas Larsson — Project Portfolio

**Engineer | Business Developer | Automation Enthusiast**

A selection of projects spanning business development, process automation, AI integration, and personal tooling.

---

## Projects

### 1. Easy Search — Backend Data Model for Product Discovery
**Valeryd AB**

Designed and implemented a structured aftermarket data model to improve product relevance across e-commerce platforms. Reduced customer support load and incorrect product orders through logic-driven datasets.

- Built scalable aftermarket data model ensuring product relevance across platforms
- Created structured datasets improving search accuracy and reducing support needs
- **Results (March 2024 → March 2025):** SE matches +155%, NO matches +203%
- Significant reduction in incorrect product orders

---

### 2. BHG Installation Services Rollout
**Svensk Installationspartner / BHG Group**

Led the development and nationwide rollout of installation services across multiple product categories. Integrated market research, partner network building, contract negotiations, and IT system alignment.

- Developed multi-category installation services (HVAC, plumbing, electrical, solar)
- Built nationwide installer network and negotiated contracts
- Integrated services into e-commerce platform for seamless purchase-to-installation flow
- Enabled expansion to Finland

---

### 3. AI Customer Support Engine — Automated Email Triage & Response
**Valeryd AB**

Designed and implemented an AI-powered system to automatically handle repetitive inbound email inquiries. The system combines Claude AI, Microsoft Graph API, and Power Automate to analyze, draft, and deliver contextual replies directly from shared mailboxes within seconds of an email arriving.

- Built end-to-end automation flow in Power Automate orchestrating Claude AI and Graph API
- Claude analyzes incoming emails and generates accurate, context-aware replies in the sender's language
- Graph API delivers replies as authentic threaded responses from shared mailboxes
- Automatic categorization and archiving of all auto-handled emails for quality control
- Handles axle inquiries, gas spring requests, return orders, and out-of-assortment deflections
- Smart filtering: ignores attachments, reply threads, and unrecognized email types
- New email categories can be added via prompt updates alone

---

### 4. Python Macro Economic Signal Dashboard
**Personal Project**

Automated Python system for monitoring macroeconomic indicators and generating actionable investment signals. Pulls real-time data from FRED (Federal Reserve Economic Data) to track yield curve dynamics, credit spreads, market volatility, and labor market conditions.

- Automated daily data extraction for 10+ macro indicators (Treasury yield curves 10Y-2Y / 10Y-3M, ICE BofA credit spreads, VIX, initial jobless claims)
- Calculates momentum metrics (deltas) across all indicators to identify regime changes
- Exports timestamped data to Excel with historical tracking for trend analysis
- Generates risk-on / risk-off signals based on credit market health and curve dynamics
- Built with Python and pandas; FRED API integration for economic data retrieval

---

### 5. VVS Invoice App — Invoice Automation for Plumbing Contractors
**Personal Project** | [GitHub](https://github.com/LukasGLars/plumbing)

Mobile-first web app for small VVS sole proprietors to manage customers, jobs, materials, and invoicing — built to be fast and correct for a tired contractor at the end of a long workday.

- Full customer management with all ROT fields (personnummer, fastighet, BRF details)
- Job tracking with status flow: scheduled → in progress → done → invoiced → paid
- Purchase logging per job with receipt photo extraction via Claude Vision OCR
- Invoice creation auto-populated from job data
- Legally accurate ROT-avdrag calculation (30% of labor only, separated from materials)
- PDF generation meeting all 14 Swedish mandatory invoice fields
- Email delivery of PDF invoice directly from the app
- Inline material and service addition — new items saved to catalog immediately
- Pre-seeded with real company data and benchmark prices from bygghemma.se

**Stack:** Python, Flask, SQLite, Alpine.js, Tailwind CSS, xhtml2pdf

---

### 6. Asset Universe — Regime-Conditional Portfolio Research & Live Automation
**Personal Project** | [GitHub](https://github.com/LukasGLars/asset_universe)

Quantitative research and live-automation system for a personal investment portfolio — a macro-regime-conditional return engine, an automated risk-guard framework, and a self-directed empirical research pipeline that ships findings straight into production, not just a backtest report.

- Regime-conditional return engine: classifies market regimes from real yield and credit-spread data (FRED), ranks assets by their empirically conditional forward-return distribution rather than a static historical average
- Automated crash-protection guard for the core position: layered slow (200-day moving average) + fast (5-day crash trigger) detection, validated both in-sample and out-of-sample across three real crashes (2020, 2022, 2025) via a 20-cell parameter sensitivity sweep — no cherry-picked config
- Independent second trading edge discovered end-to-end in one session: hypothesis → 1,252-entry historical backtest → live verification against real market data → shipped to production, including catching and fixing a real risk gap (a stale-price execution case) found live mid-build
- Rigorously empirical: rejected its own initial assumption (a naive symmetric risk threshold) once live evidence showed the real risk was asymmetric — re-tested and rebuilt rather than shipping the easy answer
- Fully automated: runs twice daily via GitHub Actions, pushes real-time Telegram alerts, self-monitors with an automated health check that has already caught a real production bug before it caused harm
- 346-test automated suite covering every trading rule and alert path

**Stack:** Python, pandas, parquet/DuckDB, FRED API, yfinance, GitHub Actions, Telegram Bot API, pytest

---

### 7. Valeryd Toolkit — Internal AI Tools for Sales & Back-Office
**Valeryd AB**

Internal web app built for the Valeryd sales and back-office team. Used daily by 5 people. Reduced manual order entry from 3–10 minutes to under one minute, and distributed specialist knowledge that previously sat with one or two people across the entire team.

- **Process Order** — upload a PDF purchase order, Claude Vision extracts article lines ready to paste into NAV. Handles both digital and scanned PDFs via server-side text extraction with vision fallback
- **Generate Axle** — enter trailer dimensions and weight, returns the correct matching axle from the article catalogue. A technically complex task that previously required specialist knowledge is now executable by the full team via a 4-stage fallback matching algorithm
- **Ask Valeryd** — ~7,500 entries built from resolved customer cases across email history, support tickets, and crosslists. Institutional knowledge that previously lived with experienced team members is instantly queryable by anyone in the department. TF-IDF retrieval → Claude Haiku rerank → Claude Sonnet synthesis

*Internal tool — no public repository.*

**Stack:** Python, Flask, Claude API (Vision + Haiku + Sonnet), scikit-learn, vanilla JS

---

### 8. MedTech Compliance Platform — AI-Enabled MDR Compliance for Medical Device Companies
**Personal Project / Co-founder**

Co-founding an AI-enabled compliance platform for medical device companies under EU MDR. The platform integrates with a company's QMS to reduce manual documentation, automate competence verification, and detect compliance gaps before audits.

Positioned as a compliance assurance layer — selling on audit risk and cost of non-conformities, not efficiency alone. Go-to-market targets Heads of Quality and QA-RA Managers at MedTech firms navigating MDR transition.

Based in Gothenburg. Working with Tomas Gustafsson (PExa / Micropos Medical) and embedded in GoCo Health Innovation City for early customer validation and pilot partnerships in the Nordic MedTech ecosystem.

*In active development.*

---

*Last updated: July 2026*
