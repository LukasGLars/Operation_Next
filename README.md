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

### 6. Reactor Core — Portfolio Construction & Thesis Pulse Monitor
**Personal Project** | [GitHub](https://github.com/LukasGLars/reactor-core-thesis-pulse)

Two-part project: a rigorous quantitative research process to construct an 8-position portfolio from scratch, followed by an automated daily monitoring system that tracks whether the thesis behind each position remains intact.

**Part 1 — Portfolio Construction**

Portfolio built from a 44-ticker candidate universe across commodities, semiconductors, infrastructure, defensives, and EM. No thesis first — let Sharpe, Calmar, and total return determine what belongs and at what weight.

- Screened 44 liquid USD-denominated tickers across 7 categories down to 8 final positions
- Mean-variance optimization (SLSQP) with 80 random restarts across 3Y, 5Y, and 10Y windows
- 6-regime historical analysis: Pre-COVID Bull, COVID Crash, COVID Recovery, Rate Hike/Inflation, AI Bull, Rate Cut
- Leave-one-out position audit: each holding tested for Sharpe contribution, gold correlation, regime wins, and role coverage
- Gold cap sensitivity tested at 7 levels (10%–uncapped) across all three windows
- Gold-only and combined precious metals stress tests (−10% to −50% shocks)
- Quarterly rolling 3Y optimization to test weight stability over time
- Out-of-sample validation on 2009–2016 data (optimizer never saw): OOS Sharpe 0.955–1.057
- DCA simulation in SEK: 1,000,000 kr initial + 6,000 kr/month from 2018, with live FX conversion
- v2 → v3 versioning with full head-to-head comparison on all metrics
- **10Y results (fixed weights):** Sharpe 1.85 | Ann. Return 30.1% | Max Drawdown −24.9%

**Part 2 — Live Thesis Pulse Monitor**

Automated daily monitoring against the constructed portfolio. Runs on GitHub Actions every weekday morning and delivers a structured email with AI-generated interpretation and raw data.

- Monitors 8 positions across 4 buckets: Hedges (Gold, Silver), Carry (LLY, WMT, JNJ), Cyclical (CCJ), Convexity (VRT, AVGO)
- FRED: 10Y real yield, WTI spot, uranium price; Yahoo Finance: prices, 52wH drawdowns, 1/3/12M momentum
- EDGAR XBRL: quarterly/annual revenue per position; hyperscaler capex (MSFT, GOOGL, AMZN, META) as AI spend proxy
- IMF IFS / WGC: central bank gold demand — monthly TTM net purchases vs prior year
- Oil term structure: WTI spot vs 12-month forward — STRESS / ELEVATED / NORMAL / CONTANGO signal
- Claude AI (Haiku): interprets pre-computed facts against thesis document; outputs per-bucket verdict with OVERALL intact/flag/review
- Rules-based invalidation thresholds with velocity tracking (weeks to breach at current pace)

**Stack:** Python, FRED API, EDGAR XBRL API, Yahoo Finance, IMF IFS API, Anthropic Claude API, GitHub Actions, scipy (SLSQP), pandas, openpyxl, smtplib

---

*Last updated: May 2026*
