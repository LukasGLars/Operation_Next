# Generation Skill

## Purpose
Generate a tailored CV and cover letter for a specific job posting, using the candidate's master CV and the job posting content.

## Candidate
- Name: Lukas Larsson
- Contact: lukasglarsson88@gmail.com · 073-740 97 88
- Location: Alingsås, Sweden
- LinkedIn: linkedin.com/in/lukas-larsson-062163169

## Core Rules
- Never generate mixed-language documents.
- Keep outputs concrete, concise, and human.
- Never sound AI-generated.
- Concrete results over vague claims.
- Write like someone who knows what they did.

## Framing Angle
The cv_base field on the job indicates which angle to emphasise. Use it to weight what you select and how you frame it — do not let it limit what you include.

| cv_base | Emphasise |
|---|---|
| CV_Einride | Analytical depth, data systems, AI integration, scalable solutions. Lead with data model and Python pipeline. Analytical work is the headline. |
| CV_Zeppelin | Full sales cycle, B2B relationships, technical product knowledge |
| CV_Plymovent | HVAC/ventilation domain, partner and channel sales |
| CV_BYGG | Construction process, project management, cost estimation, site experience |
| CV | Business development and commercial ownership. Lead with BHG rollout (100+ installer network, Finland expansion, e-commerce integration) and MedTech co-founder. Treat the analytical/automation work as a differentiator — "BD candidate who can also build the systems that make decisions data-driven" — not the headline. Valeryd commercial work (full-cycle B2B, procurement, Nordic distributors) is the body. |

## Key Results Library
Always choose 2–3 results that best fit the role.

### Available results
- Aftermarket data model: SE +155%, NO +203% match rate over 12 months.
- Python/AI pipeline: 4,100 products × 7 languages in hours vs 28,000 manual edits.
- AI email engine: Claude API + Graph API + Power Automate — handles inbound emails, generates contextual replies in sender's language within seconds.
- BHG rollout: nationwide installer network of 100+ certified partners, expansion to Finland, integrated into e-commerce flows.
- Reactor Core: Sharpe 1.85, GitHub Actions, Claude API, scipy — automated daily portfolio monitoring.
- Spirax Sarco: reached offer stage for Sales Engineer role.
- VVS Invoice App: full-stack web app for plumbing contractors — ROT deduction, PDF generation, Claude Vision OCR, automatic price benchmarking, self-hosted.
- Valeryd technical sales: full-cycle B2B account management across Nordic distributors and e-commerce partners in automotive aftermarket.
- Valeryd procurement: supplier sourcing across Europe and Asia, aligned with pricing strategy and product positioning.
- Valeryd Toolkit: internal Flask app used daily by 5 people — PDF order extraction via Claude Vision (3–10 min → under 1 min), axle matching distributing specialist knowledge to the full team, semantic KB search over ~7,500 entries from resolved customer cases (TF-IDF + Haiku rerank + Sonnet synthesis).

### Selection logic
- BA / analyst roles: use the data model and Python pipeline.
- Business developer / affärsutvecklare roles: use BHG rollout, MedTech co-founder, and Valeryd commercial work. Mention automation as a supporting differentiator only.
- CSM / customer success roles: use Valeryd Toolkit, BHG rollout, and AI email engine.
- Implementation / solutions roles: use BHG rollout, Valeryd Toolkit, and VVS Invoice App.
- Technical sales roles: use Spirax Sarco, Valeryd technical sales, and BHG rollout.
- Automation / AI roles: use AI email engine, Valeryd Toolkit, and Reactor Core.
- Procurement / supply chain roles: use Valeryd procurement and BHG rollout.

## CV Rules
- Generate the CV in the same language as the job posting. English posting → English CV. Swedish posting → Swedish CV.
- Select the 3–4 most relevant work history entries and 2–3 most relevant projects. Cut anything that does not directly serve this role.
- Favour concrete achievements and role-relevant keywords.
- Avoid generic phrasing.
- Job titles must reflect what is accurate and role-relevant, not what sounds impressive.
- Do not include profile.png or any image references — output is markdown only.

### Language rules
- Never use directly translated verbs that sound unnatural in Swedish, such as "förflyttar", "transformerar", or "förändrar hur X fungerar".
- When referencing a company's work, describe concretely what they do rather than using abstract impact language.
- Example: instead of "ett företag som förändrar hur energisystemet fungerar", write "CheckWatts arbete med virtuella kraftverk och smart energistyrning".

## Cover Letter Rules

### Language
- Detect the language of the job posting.
- Generate the cover letter in the same language.
- Never mix languages within one document.

### Tone
- Direct, human, and concrete.
- No filler.
- Match the tone and length of the approved reference cover letter below.
- Never use these phrases: leverage, synergies, passionate, driven, dynamic, results-oriented, team player.

### Opening line
Always start with the opening line in the language of the job posting:

Swedish:
> Jag har tagit arbetet på Valeryd så långt jag kan och söker nu nästa utmaning.

English:
> I have taken the work at Valeryd as far as I can and I am now looking for the next challenge.

### Structure
- Maximum 4 paragraphs.
- No bullet points.
- No headers.
- Plain prose.
- One page maximum.

### Paragraph order
1. Opening: why now + why this company specifically. Reference what they actually do, not abstract praise.
2. Most relevant key result for the role — concrete, specific, with numbers where possible.
3. Second relevant result or broader context. For technical sales roles, include a paragraph reflecting the sales philosophy: SPIN methodology, ROI focus, systematic approach to pipeline.
4. Closing: one sentence inviting conversation.

### Never
- Start with "I am writing to apply for...".
- End with "I look forward to hearing from you" or similar clichés.

## Style
- Direct, human, no filler.
- Concrete results over vague claims.
- CV adaptation: select based on what the recipient cares about, not what is technically interesting.

## Reference examples — approved output
These are real approved outputs after human review. Match this quality, structure, and tone exactly.

### Approved CV (Einride BA) — use as structure and quality benchmark. Match this structure, level of detail, and voice exactly:
Lukas Larsson
Engineer, Business Analyst, Automation & Data
Alingsås, Sweden · 073-740 97 88 · lukasglarsson88@gmail.com · linkedin.com/in/lukas-larsson-062163169

Profile
Engineer with a strong analytical and commercial profile. I work best when I get to take a complex operational problem, break it down, and build a structured solution that scales. My background spans e-commerce, construction, and industrial sales, with hands-on experience in Python, Excel, and AI-driven automation. What drives me is leverage. One well-built system can replace years of manual work, and that is the kind of problem I want to spend my time on.

Core Competencies
Business case modeling & data-driven decision-making
Python (pandas, automation, AI integration), Excel, structured data modeling
Stakeholder management with senior client and supplier counterparts
Process automation, scalability, and operational efficiency
Logistics, installation services, and supply chain coordination

Professional Experience
Valeryd AB – Business Developer & Engineer
2023 – Present
Designed a structured aftermarket data model for trailer parts. Search match rates increased by 155% in Sweden and 203% in Norway over 12 months, with a clear drop in incorrect orders.
Built a Python-based content pipeline using a few-shot AI approach to update titles and descriptions across 4,100 products in 7 languages. What would have been 28,000 manual edits ran in a few hours instead. The pipeline was later handed over to the SEO team to scale further.
Developed an AI-powered customer support engine combining the Claude API, Microsoft Graph API, and Power Automate. It analyzes incoming emails and generates contextual draft replies in the sender's language for inspection before sending, directly from shared mailboxes.

Hercules Grundläggning – Site Manager
2022 – 2023
Led multi-disciplinary project teams and machinery-heavy operations, balancing safety, legal compliance, and profitability across complex foundation projects.
Coordinated suppliers, subcontractors, and client stakeholders, translating technical complexity into clear status reporting and decisions.

Svensk Installationspartner / BHG Group – Product Manager & Business Developer
2017 – 2021
Led the development and rollout of nationwide installation services across HVAC, plumbing, electrical, and solar. The work covered market research, partner network building, and IT system alignment.
Built and negotiated a nationwide installer network with contracts and quality tracking, which enabled expansion into Finland.
Integrated services into e-commerce flows for a seamless purchase-to-installation customer journey.

Polarpumpen – Technical Sales
2014 – 2017
High-volume technical sales of heat pumps and solar panels, with strong client consultation and product matching.

Swedish Armed Forces – Reconnaissance Marine, Corporal
2012 – 2014
Strategic surveillance, intelligence, and amphibious operations. Built leadership, discipline, and the ability to operate calmly under ambiguity.

Selected Projects
Macro Regime Signal & Alert System (Personal Project)
Python-based system that ingests daily macroeconomic data from FRED (yield curves, credit spreads, VIX, labor data), calculates momentum and regime shifts, and generates risk-on/risk-off signals.
AI-assisted interpretation pipeline that produces a daily macro briefing via automated email.

VVS Invoicing App (Personal Project)
Web-based invoicing app for plumbing contractors. Flask, SQLite, Alpine.js. Handles customers, jobs, and invoices end to end. ROT deduction calculations, PDF generation, automatic price benchmarking, self-hosted.

MedTech RegTech Startup (Side project, 2025–Present)
Co-developing a SaaS platform that automates MedTech regulatory compliance (MDR/IVDR). Translates complex regulation into product features that reduce client costs and time-to-market.

Education
B.Sc. in Engineering – Yrgo, Gothenburg
2020 – 2022

Languages
Swedish (Native), English (Fluent), Danish (Working Proficiency)

---

### Approved cover letter (Einride BA) — use as English-language tone benchmark:
Lukas Larsson
Alingsås, Sweden · 073-740 97 88 · lukasglarsson88@gmail.com

Application: Business Analyst, Autonomous Transports
Einride, Gothenburg

Hello Einride,

I came across the Business Analyst role on your team and recognised it as the kind of work I do best. I get energy from taking complex operational problems apart, finding the signal in the noise, and building structured solutions that scale. The fact that Einride is doing this for road freight, one of the largest and most carbon-heavy systems we have, makes the work feel genuinely worth doing.

My background is a mix of engineering, technical sales, and business development. At Valeryd I built a structured aftermarket data model for trailer parts that lifted search match rates by 155% in Sweden and 203% in Norway over twelve months. I also built a Python pipeline using a few-shot AI approach that updated 4,100 products across 7 languages in a few hours, replacing what would have been 28,000 manual edits. Earlier, at BHG Group, I led the rollout of nationwide installation services across HVAC, plumbing, electrical, and solar, including the contract structure and the integration with the e-commerce flow. That work taught me how to translate messy operational reality into something a customer can actually buy and use.

What draws me to this role is the combination of customer-facing analysis and hands-on data work. Building business cases from logistics data, presenting findings to senior stakeholders, and supporting strategic projects is exactly the kind of dedicated, problem-by-problem work I want to spend my time on. I am most useful when I can go deep on one thing at a time and deliver something measurable.

I would welcome the chance to talk about how I could contribute to the team. Thank you for taking the time to read this.

Best regards,
Lukas Larsson

---

### Swedish cover letters
Follow the exact same structure, voice, and directness as the Einride cover letter above. Translate the approach — not the words. Same paragraph order, same result-specificity, same closing tone. Write "Hej [Company]," as the greeting.
