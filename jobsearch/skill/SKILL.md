# Job Application Workflow Skill

## Purpose
Find and validate job openings, select the correct CV base, and generate a tailored CV and cover letter for each approved role.

## Inputs
- Candidate: Lukas Larsson, lukasglarsson88@gmail.com, 073-740 97 88
- All CV files: /jobsearch/cv/
- Existing tracker: /jobsearch/joblist.md
- Tone reference: /jobsearch/letters/Cover_Letter_Einride.pdf
- Sales reference: /jobsearch/sales_philosophy.md
- Profile image: /jobsearch/profile.png

## Core Rules
- Prefer precision over recall.
- Reject borderline roles that do not clearly fit the filters.
- Never include roles already listed in /jobsearch/joblist.md.
- Never include roles that fail URL validation.
- Never generate mixed-language documents.
- Keep outputs concrete, concise, and human.

## Role Filters

### Include
Only consider roles matching one or more of these keywords:
- business analyst
- BA
- implementation
- solutions engineer
- sales engineer
- teknisk säljare
- affärsutvecklare
- business developer
- automation
- AI
- data analyst
- product specialist
- CSM
- customer success
- construction engineer
- civil works
- entreprenadingenjör
- kalkylingenjör
- projekteringsingenjör
- inköpare
- procurement
- sourcing

### Exclude
Reject roles that:
- Require consulting experience or consulting background.
- Are pure support roles, including helpdesk, kundservice, or customer service.
- Are pure sales without technical component, including phone sales, retail, SDR, or BDR.
- Require security clearance.
- Are academic or research focused.
- Are at management consulting firms expecting prior consulting career, including KPMG, Accenture, McKinsey, and BCG.

## Location Rules
- Primary target: roles within a maximum 40 minute commute from Alingsås.
- Accept anywhere in Sweden if hybrid or remote is explicitly stated.
- Reject on-site roles if the commute from Alingsås exceeds 40 minutes.

## Search Workflow
Run two searches every execution:
1. Check known URLs in /jobsearch/joblist.md and validate current status.
2. Search the web for new roles matching the include filters.

Use concise queries and rotate between Swedish and English search terms.

### Search queries
Swedish:
- business analyst Göteborg
- teknisk säljare hybrid
- affärsutvecklare scale-up
- implementation consultant Sverige
- sales engineer Göteborg
- entreprenadingenjör Göteborg
- kalkylingenjör bygg hybrid
- projekteringsingenjör anläggning

English:
- business analyst Gothenburg
- solutions engineer Sweden hybrid
- implementation manager Sweden
- technical sales Gothenburg
- civil engineer Gothenburg hybrid
- construction project engineer Sweden

## Validation Rules
A role is approved only if all of the following are true:
- It matches at least one include keyword.
- It does not match any exclude rule.
- The URL is valid and accessible.
- It satisfies the location rule.
- It is not already listed in /jobsearch/joblist.md.

If no validated roles are found, return:
```json
{
  "new_jobs": [],
  "closed_jobs": []
}
```

Include all validated roles that pass the filters. Quality is enforced by the filters, not by an arbitrary cap.

## CV Base Selection

| Keywords in job posting | CV base |
|---|---|
| business analyst, BA, product analyst, data analyst, implementation, solutions, automation, AI, CSM, customer success, fintech, healthtech, SaaS, greentech | CV_Einride |
| sales engineer, teknisk säljare, technical sales, B2B sales | CV_Zeppelin |
| HVAC, ventilation, partner sales, kanalförsäljning | CV_Plymovent |
| construction, civil works, entreprenadingenjör, anläggning, bygg, kalkylingenjör, projekteringsingenjör | CV_BYGG |
| business developer, business development, affärsutvecklare, BD, product manager, PM, project manager, inköpare, procurement, sourcing | CV |

### Default
If no keyword match is found, use CV_Einride.

### Priority
If multiple CV bases match, use the most specific match first:
1. CV_Zeppelin
2. CV_BYGG
3. CV_Plymovent
4. CV_Einride
5. CV

## Key Results Library
Always choose 2–3 results that best fit the role.

### Available results
- Aftermarket data model: SE +155%, NO +203% match rate over 12 months.
- Python/AI pipeline: 4,100 products × 7 languages in hours vs 28,000 manual edits.
- AI email engine: Claude API + Graph API + Power Automate.
- BHG rollout: nationwide installer network, expansion to Finland.
- Reactor Core: Sharpe 1.85, GitHub Actions, Claude API, scipy.
- Spirax Sarco: reached offer stage for Sales Engineer role.
- VVS Invoice App: full-stack web app for plumbing contractors, including ROT deduction, PDF generation, Claude Vision OCR, automatic benchmark price lookup, and self-hosted deployment.
- Valeryd technical sales: full-cycle B2B account management across Nordic distributors and e-commerce partners in automotive aftermarket.
- Valeryd procurement: supplier sourcing across Europe and Asia, aligned with pricing strategy and product positioning.

### Selection logic
- BA / analyst roles: use the data model and Python pipeline.
- Implementation / solutions roles: use BHG rollout, AI email engine, and VVS Invoice App.
- Technical sales roles: use Spirax Sarco, Valeryd technical sales, and BHG rollout.
- Automation / AI roles: use AI email engine, Reactor Core, and VVS Invoice App.
- Procurement / supply chain roles: use Valeryd procurement and BHG rollout.

## Cover Letter Rules

### Language
- Detect the language of the job posting.
- Generate the cover letter in the same language.
- Never mix languages within one document.

### Tone
- Direct, human, and concrete.
- No filler.
- Write like someone who knows what they did.
- Use results and specifics over vague claims.
- Match the tone and structure of /jobsearch/letters/Cover_Letter_Einride.pdf closely, regardless of output language.
- Never use these phrases:
  - leverage
  - synergies
  - passionate
  - driven
  - dynamic
  - results-oriented
  - team player

### Opening line
Always start with the opening line in the language of the job posting:

English:
> I have taken the work at Valeryd as far as I can and I am now looking for the next challenge.

Swedish:
> Jag har tagit arbetet på Valeryd så långt jag kan och söker nu nästa utmaning.

### Structure
- Maximum 4 paragraphs.
- No bullet points.
- No headers.
- Plain prose.
- One page maximum.
- Same length as /jobsearch/letters/Cover_Letter_Einride.pdf.

### Paragraph order
1. Opening: why now + why this company.
2. Most relevant key result for the role.
3. Second relevant result or broader context.
   - For technical sales roles, include one paragraph from /jobsearch/sales_philosophy.md here, translated if needed.
4. Closing: one sentence inviting conversation.

### Never
- Start with "I am writing to apply for...".
- End with "I look forward to hearing from you" or similar clichés.

## CV Rules
- CV is always generated in Swedish regardless of job posting language.
- Keep the document tailored to the selected CV base.
- Include /jobsearch/profile.png in every CV document.
- Favor concrete achievements and role-relevant keywords.
- Avoid generic phrasing.

## Output Format
Return results.json in this exact structure:
```json
{
  "new_jobs": [
    {
      "company": "string",
      "role": "string",
      "role_type": "string",
      "cv_base": "string",
      "url": "string",
      "location": "string",
      "status": "Identifierad",
      "date_added": "YYYY-MM-DD"
    }
  ],
  "closed_jobs": [
    {
      "company": "string",
      "url": "string"
    }
  ]
}
```

## Edge Cases
- If language is unclear, infer from the posting and keep the entire document in that language.
- If a role matches multiple keyword groups, choose the most specific CV base.
- If a role is a borderline match, prefer precision over recall.
- If a role is close but fails location or exclusion rules, reject it.

## Style
- Direct, human, no filler.
- Concrete results over vague claims.
- Never sound AI-generated.
- Keep the tone close to /jobsearch/letters/Cover_Letter_Einride.pdf.
### CV adaptation rules
- Job titles must reflect what is accurate and role-relevant, not what sounds impressive
- Project details must be selected based on what the recipient cares about, not what is technically interesting
- Remove details that do not add value for the specific role or reader

### Language rules
- Never use directly translated verbs that sound unnatural in Swedish, such as "förflyttar", "transformerar", or "förändrar hur X fungerar"
- When referencing a company's work, describe concretely what they do rather than using abstract impact language
- Example: instead of "ett företag som förändrar hur energisystemet fungerar", write "CheckWatts arbete med virtuella kraftverk och smart energistyrning"

### Reference example — approved output:
- Approved CV: /jobsearch/applications/checkwatt_csm/cv_edited.md
- Approved cover letter: /jobsearch/applications/checkwatt_csm/cover_letter_edited.md
- These are real approved outputs after human review — use as quality reference
