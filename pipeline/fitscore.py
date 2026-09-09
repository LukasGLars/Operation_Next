# -*- coding: utf-8 -*-
"""Fit scoring — how well a role matches the candidate, 0-100.

Why this exists: the sweep finds far more candidates than the joblist should
hold, and the cap used to keep the *newest* ones. Publication date says nothing
about whether a role is winnable, so an ABB technical sales role posted three
weeks ago lost to a warehouse ad posted yesterday. The score replaces date as
the thing the cap sorts on.

Two deliberate constraints:

- **It orders, it does not filter.** `judge_fit` still decides what is in or out
  on the role filters. A scoring mistake pushes a role down the list; it never
  makes it disappear. The relevance gate's 46% false-positive rate is why —
  a silent drop is the one failure mode that cannot be noticed.
- **It is a rubric, not a learned model.** Four interviews cannot calibrate
  anything. This encodes judgement that can be read and argued with; it does not
  discover a pattern. Change the weights when the evidence changes, and re-run
  `validate.py` to see what it does to the rows that actually converted.
"""
from __future__ import annotations

# Weights sum to 100. Category dominates because it is the only axis with
# outcome evidence behind it: every Intervju row is technical sales or BD.
AXES = {
    "category":    35,   # is this the category that converts?
    "technical":   25,   # does selling it require explaining something?
    "requirement": 25,   # does the candidate meet the stated must-haves?
    "evidence":    15,   # is there a story in master_cv.md for the main ask?
}

MAX_SCORE = sum(AXES.values())

# Anchors are the whole trick. Asked for a bare 0-100 an LLM clusters everything
# at 70-85 and the ranking is noise; shown four real rows from this joblist with
# their scores, it spreads. These are actual rows — three converted, one is the
# churn the group sweep now surfaces.
ANCHORS = """Anchor the scale on these real examples:
- "Teknisk säljare till Profcon" (Oddwork) = 90. Technical B2B sales, reached interview.
- "Affärsutvecklare" (Wioniq) = 88. BD rather than sales, but the same motion — also reached interview.
- "Kalkyl/entreprenadingenjör" (Göteborgs Kommun) = 40. Applicable, never applied to in practice.
- "Operativ inköpare till tillverkande industri" (SJR) = 25. Procurement, the category that has never converted.
- "Är du redo att ta plats som säljare i Bollebygd?" (Exaltera) = 5. Commission churn."""

RUBRIC = f"""Also score each role 0-100 for fit, as the sum of four axes:
- category (0-{AXES['category']}): technical sales and business development score
  full marks; customer success and business/data analyst around half; procurement
  and construction low. This ordering is from outcomes, not preference.
- technical (0-{AXES['technical']}): does the role require explaining a product or
  system? A named technical product scores high; reselling subscriptions or
  door-to-door scores near zero.
- requirement (0-{AXES['requirement']}): does the candidate meet the stated
  must-haves? Deduct for a hard gate they miss — years of experience well beyond
  their level, a degree above högskoleingenjör, a named platform or domain they
  do not have (ERP, telecom, life science). Preferences ("gärna", "meriterande")
  are not gates and cost nothing.
- evidence (0-{AXES['evidence']}): is there concrete experience to write a cover
  letter from — technical sales, construction, procurement, AI/automation,
  analytics? Transferable-only scores low.

{ANCHORS}"""


def clamp(value):
    """A score the model did not supply, or supplied as nonsense, must not sort
    to the top. Missing means unknown, and unknown sorts low but is still kept —
    the caller decides what to do with it, the same way a failed judge chunk
    passes candidates through rather than dropping them."""
    try:
        return max(0, min(MAX_SCORE, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def from_verdict(verdict):
    """Pull the score out of one judge verdict. Accepts either a flat `score` or
    the per-axis breakdown, so a model that answers with axes still works."""
    if not isinstance(verdict, dict):
        return 0
    if verdict.get("score") is not None:
        return clamp(verdict["score"])
    axes = verdict.get("axes")
    if isinstance(axes, dict):
        return clamp(sum(clamp(axes.get(name, 0)) for name in AXES))
    return 0
