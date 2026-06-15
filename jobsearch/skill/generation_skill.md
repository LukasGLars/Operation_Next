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
| CV_Einride | Analytical depth, data systems, AI integration, scalable solutions |
| CV_Zeppelin | Full sales cycle, B2B relationships, technical product knowledge |
| CV_Plymovent | HVAC/ventilation domain, partner and channel sales |
| CV_BYGG | Construction process, project management, cost estimation, site experience |
| CV | Business development, commercial ownership, broad cross-functional scope |

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
- CSM / customer success roles: use Valeryd Toolkit, BHG rollout, and AI email engine.
- Implementation / solutions roles: use BHG rollout, Valeryd Toolkit, and VVS Invoice App.
- Technical sales roles: use Spirax Sarco, Valeryd technical sales, and BHG rollout.
- Automation / AI roles: use AI email engine, Valeryd Toolkit, and Reactor Core.
- Procurement / supply chain roles: use Valeryd procurement and BHG rollout.

## CV Rules
- CV is always generated in Swedish regardless of job posting language.
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

## Reference example — approved output
These are real approved outputs after human review. Use as quality and tone reference.

### Approved cover letter (CheckWatt CSM):
Lukas Larsson
Alingsås, Sverige · 073-740 97 88 · lukasglarsson88@gmail.com

Ansökan: Customer Success Manager – CheckWatt

Hej CheckWatt,

Jag har tagit arbetet på Valeryd så långt jag kan och söker nu nästa utmaning. CSM-rollen hos er stack ut direkt. Jag har arbetat med energi och tekniska installationer i flera år – värmepumpar, sol, HVAC – och förstår den tekniska verklighet som era kunder och partners lever i. Att kombinera det med CheckWatts arbete med virtuella kraftverk och smart energistyrning känns som rätt nästa steg.

På Valeryd byggde jag ett AI-drivet kundsupportsystem som kombinerar Claude API, Microsoft Graph API och Power Automate. Det analyserar inkommande e-post, genererar kontextuella svarsutkast på avsändarens språk och levererar dem direkt från delade postlådor inom sekunder. Erfarenheten gav mig en tydlig förståelse för hur man bygger skalbar kundkommunikation och processer som fungerar utan konstant manuell input – vilket är precis vad en växande CSM-funktion behöver.

Tidigare ledde jag lanseringen av rikstäckande installationstjänster inom HVAC, VVS, el och sol på BHG Group. Det arbetet handlade om att hålla ihop partners, teknik och kunder i en enda fungerande kedja – och att lösa problem på alla tre nivåer samtidigt. Det är den typen av roll jag trivs i: nära kunden, tekniskt grundad, och med tydligt ansvar för att saker faktiskt fungerar.

Jag skulle gärna berätta mer om hur jag kan bidra till ert team.

Med vänlig hälsning,
Lukas Larsson
