# Job Search Skill

## Purpose
Find and validate new job openings matching the candidate profile. Update joblist with new and closed roles.

## Candidate
Lukas Larsson, Alingsås, Sweden. Commutes from Alingsås.

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
- Primary target: roles within a maximum 40 minute commute from Alingsås —
  Alingsås, Göteborg, Partille, Lerum, Mölndal, Mölnlycke, Härryda, Landvetter,
  Vårgårda, Sollebrunn, Gråbo, Floda, Bollebygd, Borås, Ale, Lilla Edet.
- Accept fully remote roles anywhere.
- Hybrid counts only when the office is within the 40 minute range. A Stockholm
  hybrid role still means two or three days a week in Stockholm — reject it.
- Reject on-site and hybrid roles everywhere else — Stockholm, Malmö, Umeå,
  Södertälje, Borlänge, Örnsköldsvik and the like — regardless of role fit.
- Always report the city the ad states in the `location` field, or "Hybrid" /
  "Remote" when the ad states that instead. The pipeline enforces this rule in
  code (`location_verdict` in `pipeline/search.py`), so a missing or vague
  location gets the role dropped.

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
Used to tag new jobs with the correct framing angle for document generation.

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

## Search Workflow
Run two searches every execution:
1. Check known URLs in /jobsearch/joblist.md and validate current status.
2. Search the web for new roles matching the include filters.

Use concise queries and rotate between Swedish and English search terms.

### Search queries
Swedish:
- business analyst Göteborg
- teknisk säljare hybrid
- affärsutvecklare scale-up Göteborg
- affärsutvecklare SaaS Sverige
- affärsutvecklare tech hybrid Sverige
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
- business developer SaaS Sweden
- commercial manager tech scale-up Sweden
- civil engineer Gothenburg hybrid
- construction project engineer Sweden

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
- If a role matches multiple keyword groups, choose the most specific CV base.
- If a role is a borderline match, prefer precision over recall.
- If a role is close but fails location or exclusion rules, reject it.
