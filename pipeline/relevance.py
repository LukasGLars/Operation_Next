"""Relevance gate — rejects postings the candidate cannot realistically win.

Runs as stage 1.6, after the location gate and before the batched quality
validation, so an irrelevant role is dropped before it costs a Claude call.

Every rule here matches on the job *title* or an explicit numeric threshold,
never on a bare keyword in the body. Body-keyword matching was measured at a
46% false-positive rate on the live joblist: "du har gärna erfarenhet av
inköp" and "minst fem års erfarenhet av projektinköp" both contain the same
words, and only the second one disqualifies. `_soft_wish` is what separates
them.
"""

import re

# Sentences containing these phrase a requirement as a preference. A match
# inside one of them is not a gate.
_SOFT_WISH = re.compile(
    r"\bgärna\b|\bmeriterande\b|\bett plus\b|\bstort plus\b|\bfördel om\b"
    r"|\bser vi positivt på\b|\bnice to have\b|\bpreferab\w+|\ba plus\b",
    re.I,
)

_DEAD_AD = re.compile(
    r"inte längre (?:tillgänglig|aktiv)|jobbannonsen är (?:borttagen|stängd)"
    r"|no longer (?:available|active|accepting)|tjänsten är tillsatt|jobbet tillsatt"
    r"|ansökningstiden (?:har )?(?:löpt ut|gått ut)|sista ansökningsdag har passerat"
    r"|position (?:has been )?filled|this (?:job|position) (?:is closed|has closed)",
    re.I,
)

# Rule 2 — procurement seniority.
_PROCUREMENT = re.compile(r"inköp|purchas|buyer|upphandl|sourcing", re.I)
_SENIOR_TITLE = re.compile(r"\bsenior\b|\berfaren\b|\bstrategisk\w*\b|\bstrategic\b", re.I)
# Swedish ads spell the number out at least as often as they use a digit —
# "minst fem års erfarenhet" is the common phrasing, and a digits-only pattern
# silently missed every one of them.
_NUMBER_WORDS = {
    "en": 1, "ett": 1, "två": 2, "tre": 3, "fyra": 4, "fem": 5, "sex": 6,
    "sju": 7, "åtta": 8, "nio": 9, "tio": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_YEARS = re.compile(
    r"(?:minst|minimum|at least)?\s*"
    r"(\d+|" + "|".join(_NUMBER_WORDS) + r")"
    r"\s*(?:[-–]\s*(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\s*)?(?:\+\s*)?"
    # filler words may sit between: "3-7 års *relevant* erfarenhet",
    # "5+ years *of relevant procurement* experience"
    r"(?:års?|year)s?\s+(?:\w+\s+){0,3}(?:erfarenhet|experience|arbetslivserfarenhet)",
    re.I,
)
_SENIOR_YEARS_THRESHOLD = 4

# Rule 3 — public procurement law as a duty.
_LOU = re.compile(r"\bLOU\b|\bLUF\b|offentlig upphandling|upphandlingslagstiftning", re.I)

# Rule 4 — real security clearance. Deliberately excludes registerkontroll and
# belastningsregister: those are background checks run on the person hired, not
# a clearance the applicant must already hold. Every Göteborgs Kommun ad carries
# one, and treating them as gates dropped four perfectly applicable roles.
_CLEARANCE = re.compile(
    r"säkerhetsprövning|säkerhetsskyddslag|säkerhetsklass"
    r"|security clearance|svenskt medborgarskap", re.I,
)

# Rule 5 — degree above the candidate's level. Högskoleingenjör passes.
_HIGH_DEGREE = re.compile(
    r"civilingenjör|\bM\.?Sc\.?\b|masterexamen|magisterexamen|master'?s degree", re.I,
)


def _sentences(text):
    return re.split(r"(?<=[.!?•\n])\s+", text or "")


def _hard_matches(text, pattern):
    """Sentences matching `pattern` that are not phrased as a preference."""
    return [s for s in _sentences(text) if pattern.search(s) and not _SOFT_WISH.search(s)]


def is_dead_ad(page_text):
    """Return (dead, reason). A page too short to be an ad counts as dead —
    a pulled posting often redirects to a stub or a cookie notice."""
    text = (page_text or "").strip()
    if len(text) < 300:
        return True, f"page too short to be an ad ({len(text)} chars)"
    match = _DEAD_AD.search(text)
    if match:
        return True, f"ad withdrawn ({match.group(0).strip()})"
    return False, ""


def _required_years(text):
    """The *minimum* the ad asks for. A "3-7 års" range reports 3, not 7 —
    the floor is what the ad will actually accept, so gating on the ceiling
    would reject roles that are open to the candidate."""
    values = []
    for match in _YEARS.finditer(text or ""):
        token = match.group(1).lower()
        values.append(int(token) if token.isdigit() else _NUMBER_WORDS[token])
    return max(values) if values else 0


def relevance_verdict(role, company="", page_text=""):
    """Return (ok, reason). Rejects roles the candidate cannot realistically
    win — see the module docstring for why each rule is shaped this way."""
    title = f"{role} {company}"
    text = page_text or ""

    if _PROCUREMENT.search(title):
        if _SENIOR_TITLE.search(role or ""):
            return False, "senior/strategic procurement (in title)"
        for sentence in _hard_matches(text, _PROCUREMENT):
            years = _required_years(sentence)
            if years >= _SENIOR_YEARS_THRESHOLD:
                return False, f"senior procurement ({years}+ years required)"

    if _hard_matches(text, _LOU):
        return False, "requires LOU / offentlig upphandling"

    if _hard_matches(text, _CLEARANCE):
        return False, "requires security clearance"

    if _hard_matches(text, _HIGH_DEGREE):
        return False, "requires civilingenjör/MSc"

    return True, "relevant"
