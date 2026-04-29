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

### 4. AI Daily Macro Briefing Automation
**Personal Project**

Built a GPT-4 powered automation in Pipedream to deliver tailored macroeconomic briefings each morning.

- GPT-4-powered automation in Pipedream
- Structured daily macro briefing covering AI, energy, crypto, and FX
- Automated email delivery each weekday morning
- Scalable template for sentiment triggers and rebalancing alerts

---

### 5. Python Macro Economic Signal Dashboard
**Personal Project**

Automated Python system for monitoring macroeconomic indicators and generating actionable investment signals. Pulls real-time data from FRED (Federal Reserve Economic Data) to track yield curve dynamics, credit spreads, market volatility, and labor market conditions.

- Automated daily data extraction for 10+ macro indicators (Treasury yield curves 10Y-2Y / 10Y-3M, ICE BofA credit spreads, VIX, initial jobless claims)
- Calculates momentum metrics (deltas) across all indicators to identify regime changes
- Exports timestamped data to Excel with historical tracking for trend analysis
- Generates risk-on / risk-off signals based on credit market health and curve dynamics
- Built with Python and pandas; FRED API integration for economic data retrieval

---

### 6. VVS Invoice App — Invoice Automation for Plumbing Contractors
**Personal Project** | [GitHub](https://github.com/LukasGLars/construction_buddy)

Mobile-friendly web app (Streamlit + Supabase) that automates the full invoicing workflow for small VVS firms — from article catalog search to ROT deduction calculation and invoice generation.

- Supabase-backed article catalog with full-text search by item number, description, or category
- Automatic ROT deduction calculation (30% of labor cost including VAT)
- Real-time invoice builder with line-item management
- One-click invoice generation and download
- Swedish UI built for use on-site, not just in the office

**Stack:** Python, Streamlit, Supabase, pandas

---

### 7. Reactor Core — Thesis Pulse Monitor
**Personal Project**

Python-based personal investment tool for monitoring the fundamental thesis behind each portfolio position. Tracks whether the core story for each holding is accelerating, stable, or weakening — not price movements.

- Monitors 8 portfolio positions: Gold, LLY, WMT, Silver, CCJ, VRT, AVGO, JNJ
- Data sources: FRED (real yields, USD index), Yahoo Finance (commodities), EDGAR XBRL (revenue, capex), Trading Economics (uranium spot)
- Tracks hyperscaler AI capex (MSFT, GOOGL, AMZN, META) as a key signal for convexity positions
- Outputs structured thesis pulse signals per position with delta tracking
- Rules-based framework — separates fundamental signal from market noise

**Stack:** Python, EDGAR XBRL API, FRED API, Yahoo Finance, pandas

---

*Last updated: April 2026*
