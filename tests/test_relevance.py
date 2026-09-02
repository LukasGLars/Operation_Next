# -*- coding: utf-8 -*-
"""Relevance gate.

The soft-wish cases are the point of this suite. Matching these rules on a bare
body keyword had a 46% false-positive rate against the live joblist, so every
rule has a paired "same words, phrased as a preference" case below.
"""
import pytest

from pipeline.relevance import (
    is_dead_ad,
    relevance_verdict,
    _required_years,
)

PAD = "Vi söker en ny kollega till vårt team i Göteborg. " * 10


def verdict(role, body, company=""):
    return relevance_verdict(role, company, PAD + body)


# ── Rule 1: dead ads ───────────────────────────────────────

@pytest.mark.parametrize("body", [
    "Jobbannonsen är inte längre tillgänglig",
    "Jobbannonsen är inte längre aktiv. Antingen är jobbet tillsatt.",
    "Ansökningstiden har löpt ut",
    "This position has closed",
])
def test_withdrawn_ads_are_dead(body):
    dead, _ = is_dead_ad(PAD + body)
    assert dead


def test_short_page_counts_as_dead():
    # A pulled posting usually redirects to a stub or a cookie notice.
    dead, reason = is_dead_ad("Fortifikationsverket Jobbannonsen Tillbaka")
    assert dead and "too short" in reason


def test_live_ad_is_not_dead():
    dead, _ = is_dead_ad(PAD + "Vi ser fram emot din ansökan!")
    assert not dead


# ── Rule 2: procurement seniority ──────────────────────────

@pytest.mark.parametrize("role", [
    "Senior Strategic Purchaser",
    "Erfaren strategisk inköpare till tekniskt bolag",
    "Strategisk inköpare med kategoriledaransvar",
    "Strategisk Inköpare – Konsultuppdrag",
])
def test_senior_procurement_title_rejected(role):
    ok, reason = verdict(role, "Du blir en del av ett trevligt team.")
    assert not ok and "procurement" in reason


def test_five_years_spelled_out_rejected():
    # Swedish ads spell the number out at least as often as they use a digit.
    ok, reason = verdict(
        "Inköpare bygg",
        "Vi söker dig som: Har minst fem års erfarenhet av projektinköp inom byggbranschen.",
    )
    assert not ok and "5+ years" in reason


def test_three_years_operational_procurement_accepted():
    ok, _ = verdict(
        "Operativ Inköpare - Konsultuppdrag",
        "Vi söker dig som har Minst 3 års erfarenhet av inköp, gärna operativt inköp.",
    )
    assert ok


def test_range_reports_the_floor_not_the_ceiling():
    # "3-7 års" will accept 3, so it is not a gate.
    assert _required_years("cirka 3–7 års relevant erfarenhet") == 3


def test_soft_wish_procurement_experience_accepted():
    ok, _ = verdict(
        "Inköpare till Huvudkontoret",
        "Du har gärna en utbildning eller arbetslivserfarenhet inom inköp, ekonomi eller försäljning.",
    )
    assert ok


def test_seniority_outside_procurement_is_fine():
    # The candidate converts in technical sales regardless of stated seniority.
    ok, _ = verdict(
        "Senior Sales Engineer",
        "Vi söker dig med minst åtta års erfarenhet av teknisk försäljning.",
    )
    assert ok


# ── Rule 3: LOU ────────────────────────────────────────────

def test_lou_as_a_duty_rejected():
    ok, reason = verdict(
        "Inköpare till Utbildningsförvaltningen",
        "I rollen ingår avrop på ramavtal samt Lag om offentlig upphandling (LOU).",
    )
    assert not ok and "LOU" in reason


def test_lou_as_a_merit_accepted():
    ok, _ = verdict(
        "Entreprenadingenjör - Anläggning",
        "Vi ser gärna att du har erfarenhet av LOU (Lagen om offentlig upphandling).",
    )
    assert ok


# ── Rule 4: clearance ──────────────────────────────────────

def test_real_clearance_rejected():
    ok, reason = verdict(
        "Kalkylingenjör",
        "Tjänsten är placerad i säkerhetsklass och kräver säkerhetsprövning.",
    )
    assert not ok and "clearance" in reason


@pytest.mark.parametrize("body", [
    "Vid inköps- och upphandlingsförvaltningen bedöms flera tjänster omfattas av "
    "Lagen om registerkontroll vid anställning till ledande befattningar i kommuner.",
    "Med hänvisning till lagarna som reglerar registerkontroll måste den som "
    "erbjuds denna tjänst uppvisa utdrag ur belastningsregistret innan anställning.",
])
def test_background_check_on_hire_is_not_a_clearance(body):
    # Every Göteborgs Kommun ad carries one of these. Treating them as clearance
    # gates dropped four perfectly applicable roles.
    ok, _ = verdict("Kalkyl/entreprenadingenjör", body)
    assert ok


# ── Rule 5: degree ─────────────────────────────────────────

def test_civilingenjor_requirement_rejected():
    ok, reason = verdict("Sales Engineer", "Du har en examen som civilingenjör.")
    assert not ok and "civilingenjör" in reason


def test_hogskoleingenjor_accepted():
    ok, _ = verdict("Sales Engineer", "Du är utbildad högskoleingenjör eller motsvarande.")
    assert ok


def test_msc_as_a_merit_accepted():
    ok, _ = verdict("Business Analyst", "Det är meriterande om du är civilingenjör.")
    assert ok
