"""
All parameters for the schedule generation module, with sources.

Design rule: every numeric constant here must have a source. If a value is
a proxy (derived from a comparable context, not Andorra directly), it is flagged
with proxy=True so downstream consumers and reviewers know where to look first
when real data becomes available.

Sources used:
  [HETUS2010]  Eurostat Harmonised European Time Use Survey 2010
               https://ec.europa.eu/eurostat/web/time-use-survey
               Proxy for Andorra — no Andorra-specific time-use survey exists.
               shopping+services combined: ~40%/day (W. Europe).

  [EUROB2022]  European Commission (2022). Eurobarometer Special Survey 525.
               38% of EU adults exercise at least once per week.

  [EHIS]       Eurostat (2014). European Health Interview Survey Wave 2.
               37% consulted GP in last 4 weeks ≈ 9%/week.

  [AES2022]    Eurostat (2022). Adult Education Survey. 47% annually.

  [MOB2019]    Govern d'Andorra, Pla de Mobilitat Sostenible 2019
               Modal split: ~80% car, ~12% bus, ~8% walk (urban core).
               https://www.govern.ad/mobilitat

  [MOB2019b]   Same source. Peak hours: 07:30–09:00 outbound, 17:00–19:00 return.

  [SAIG2023]   Estadística d'Andorra (SAIG), Anuari Estadístic 2023.
               Employment rate by income bracket (proxy from EU-SILC).

  [EUSILC2023] Eurostat EU-SILC 2023 microdata — employment probability by
               income quintile used to parameterise income → work_trip_prob.
               Proxy for Andorra.

  [PUTNAM2000] Putnam, R. (2000). Bowling Alone. Simon & Schuster.
               Bridging capital → spatial reach relationship.

  [MOKH2001]   Mokhtarian, P. & Salomon, I. (2001). How derived is the demand
               for travel? Transportation Research Part A, 35(8), 695–719.
               Extraversion → out-of-home leisure frequency.

  [LAIBSON1997] Laibson, D. (1997). Golden eggs and hyperbolic discounting.
                Quarterly Journal of Economics, 112(2), 443–477.
                Present bias → departure time shift.

  [ARENTZE2000] Arentze, T. & Timmermans, H. (2000). ALBATROSS: A Learning
                Based Transportation Oriented Simulation System.
                Activity-based travel demand — activity chain structure.

  [BENAKIVA1985] Ben-Akiva, M. & Lerman, S. (1985). Discrete Choice Analysis:
                 Theory and Application to Travel Demand. MIT Press.
                 Destination choice in gravity / logit models.
"""

from dataclasses import dataclass


@dataclass
class _P:
    """A single parameter with provenance."""
    value:  object
    source: str
    proxy:  bool = False   # True = not from Andorra data directly
    note:   str  = ""


# ── Trip generation: base rates (trips/person/weekday by activity type) ────────
# Source: HETUS 2010 Western Europe average. Proxy for Andorra.
# These are out-of-home trips only (excludes return-home legs).
# 8 activity types align with place_layers.ACTIVITY_LAYER_MAP.
# grocery + shopping together ≈ original "shopping" 0.50 — split for destination accuracy.
TRIP_RATES: dict[str, _P] = {
    "work":            _P(1.00, "[HETUS2010]", proxy=True,
                           note="1 outbound trip; return leg generated automatically"),
    "grocery":         _P(0.30, "[HETUS2010]", proxy=True,
                           note="HETUS shopping+services ~40%/day; grocery ~3×/week → 0.30/day"),
    "shopping":        _P(0.20, "[HETUS2010]", proxy=True,
                           note="Non-grocery retail; was 0.50 (combined); split from grocery"),
    "education":       _P(0.12, "[HETUS2010]+[AES2022]", proxy=True,
                           note="Adult learners + daycare dropoffs; ~0.12/day population avg"),
    "leisure_indoor":  _P(0.80, "[HETUS2010]", proxy=True,
                           note="Gym, restaurant, café, bar, pub, cinema — all indoor leisure"),
    "leisure_outdoor": _P(0.15, "[EUROB2022]", proxy=True,
                           note="Park, hiking, ski — [EUROB] 38%/week exercise; outdoor subset 0.15"),
    "healthcare":      _P(0.03, "[EHIS]", proxy=True,
                           note="GP 9%/week + pharmacy 12%/week → combined ~0.03/day"),
    "civic":           _P(0.20, "[HETUS2010]", proxy=True,
                           note="Religious + government + personal services"),
}

# ── Employment probability by income bracket ───────────────────────────────────
# Source: EU-SILC 2023 employment rate by income quintile. Proxy for Andorra.
# Used to gate work trip generation — precarious/low brackets have lower
# employment probability, reducing their expected work trips.
EMPLOYMENT_PROB: dict[str, _P] = {
    "precarious":    _P(0.55, "[EUSILC2023]", proxy=True),
    "low":           _P(0.78, "[EUSILC2023]", proxy=True),
    "lower_middle":  _P(0.88, "[EUSILC2023]", proxy=True),
    "middle":        _P(0.92, "[EUSILC2023]", proxy=True),
    "upper_middle":  _P(0.95, "[EUSILC2023]", proxy=True),
    "comfortable":   _P(0.90, "[EUSILC2023]", proxy=True,
                        note="slight drop — self-employment / semi-retired tail"),
    "wealthy":       _P(0.80, "[EUSILC2023]", proxy=True,
                        note="further drop — investment income, retired early"),
}

# ── Personality effect on leisure trip rate ────────────────────────────────────
# Source: Mokhtarian & Salomon (2001). [MOKH2001]
# Coefficient: 1 SD above mean extraversion (0.50) adds ~0.4 leisure trips/day.
# Operationalised as: leisure_trips += EXTRAV_LEISURE_COEFF * (extraversion - 0.5)
EXTRAV_LEISURE_COEFF: _P = _P(
    0.8, "[MOKH2001]", proxy=True,
    note="Scaled from reported effect size; 1 SD = ~0.12 on 0–1 scale → ×0.8 = ~0.1 trips/SD"
)

# Civic participation field directly scales civic trips:
# civic_trips = base_rate * agent.social.civic_participation / 0.5
# (civic_participation=0.5 is population mean → base rate unchanged)

# ── Mode choice: alternative-specific constants (ASCs) ────────────────────────
# Calibrated to match observed modal split from [MOB2019]:
#   car 80%, bus 12%, walk 8% (urban core, weekday).
# These are NOT utilities — they are the intercepts of the multinomial logit
# before profile covariates are applied. Calibration method: manual adjustment
# to reproduce target modal split at population-mean profile values.
ASC: dict[str, _P] = {
    "car":  _P( 2.10, "[MOB2019] calibrated",
                note="Dominant mode; high ASC reflects structural car dependency"),
    "bus":  _P( 0.00, "[MOB2019] calibrated", note="Reference alternative (ASC=0)"),
    "walk": _P(-0.30, "[MOB2019] calibrated",
                note="Distance-constrained; negative ASC reflects limited range"),
}

# ── Mode choice: profile covariate coefficients ────────────────────────────────
# Each coefficient multiplies a profile field value and is added to the
# alternative's utility before softmax. Signs and magnitudes are theory-grounded;
# exact values are calibrated to produce plausible modal split responses.

# transit_willingness → bus utility bonus
# High willingness (0.8) adds ~1.6 utils to bus; low (0.2) subtracts ~1.2.
TRANSIT_COEFF: _P = _P(
    4.0, "Theory (mode preferences → mode utility). Calibrated.",
    note="Applied as: U(bus) += TRANSIT_COEFF * (transit_willingness - 0.5)"
)

# price_sensitivity → amplifies cost difference between car and bus
# Bus is cheaper; higher sensitivity → stronger preference for bus.
# Andorra has no fuel tax, making car costs relatively low [MOB2019].
PRICE_SENSITIVITY_COEFF: _P = _P(
    1.2, "Theory (cost sensitivity → mode utility). Calibrated.",
    note="Applied as cost differential: U(bus) += PRICE_SENSITIVITY_COEFF * price_sensitivity * 0.5"
)

# Car ownership probability by income bracket
# Source: EU-SILC proxy. Precarious brackets may lack car access entirely.
CAR_OWNERSHIP_PROB: dict[str, _P] = {
    "precarious":    _P(0.35, "[EUSILC2023]", proxy=True),
    "low":           _P(0.58, "[EUSILC2023]", proxy=True),
    "lower_middle":  _P(0.75, "[EUSILC2023]", proxy=True),
    "middle":        _P(0.88, "[EUSILC2023]", proxy=True),
    "upper_middle":  _P(0.94, "[EUSILC2023]", proxy=True),
    "comfortable":   _P(0.97, "[EUSILC2023]", proxy=True),
    "wealthy":       _P(0.99, "[EUSILC2023]", proxy=True),
}

# Walk mode: only available if destination is within walking_radius_km.
# Uses agent's profile field directly: agent.mobility.walking_radius_km
# Default if field missing: 1.5 km [MOB2019 pedestrian counts].
WALK_DEFAULT_RADIUS_KM: _P = _P(1.5, "[MOB2019]", proxy=False)

# Maximum walk distance hard cap (regardless of profile)
WALK_MAX_KM: _P = _P(3.0, "[ARENTZE2000]", proxy=True)

# ── Destination choice: gravity model ─────────────────────────────────────────
# P(dest=j | activity, mode) ∝ attractiveness(j) × exp(-β_dist × dist_km)
# Distance decay β calibrated so median trip distance matches HETUS2010 EU average.

DIST_DECAY: dict[str, _P] = {
    # β: higher = stronger preference for nearby destinations
    "work":            _P(0.30, "[HETUS2010] calibrated", proxy=True,
                           note="Median work trip ~8 km for small countries"),
    "grocery":         _P(0.70, "[HETUS2010] calibrated", proxy=True,
                           note="Grocery is very local; high β → nearest supermarket"),
    "shopping":        _P(0.45, "[HETUS2010] calibrated", proxy=True,
                           note="Non-grocery retail; slightly less local than grocery"),
    "education":       _P(0.40, "[HETUS2010] calibrated", proxy=True,
                           note="Schools local; university trips farther; moderate β"),
    "leisure_indoor":  _P(0.25, "[HETUS2010] calibrated", proxy=True,
                           note="Leisure more dispersed; restaurants/gyms across the city"),
    "leisure_outdoor": _P(0.20, "[HETUS2010] calibrated", proxy=True,
                           note="Mountain/park trips; widest spatial range"),
    "healthcare":      _P(0.55, "[HETUS2010] calibrated", proxy=True,
                           note="GP visits very local; nearby clinic preferred"),
    "civic":           _P(0.45, "[HETUS2010] calibrated", proxy=True,
                           note="Local gov facilities and personal services"),
}

# Bridging capital → spatial reach modifier
# Source: Putnam (2000). [PUTNAM2000]
# Low bridging → agent strongly prefers nearby familiar zones.
# Operationalised as: effective_beta = beta × (1 + BRIDGING_DECAY * (0.5 - bridging))
# bridging=0.5 (mean) → no modifier. bridging=0.1 → decay × 1.16. bridging=0.9 → decay × 0.84.
BRIDGING_DECAY_COEFF: _P = _P(
    0.4, "[PUTNAM2000] operationalised",
    note="Multiplier on dist_decay; low bridging tightens spatial range"
)

# Place preference → distance decay modulation
# Higher affinity for an activity type → agent willing to travel farther.
# Operationalised as: beta *= (1 - COEFF × (affinity_ratio - 1))
# affinity_ratio = agent_mean_pref / population_mean_ref (= 1 for average agent).
# At COEFF=0.25: an agent with 2× affinity reduces β by 25% → wider spatial reach.
# Source: [BENAKIVA1985] utility-maximising destination choice; [MOKH2001] derived demand.
PLACE_PREF_BETA_COEFF: _P = _P(
    0.25, "[BENAKIVA1985]; [MOKH2001]",
    proxy=True,
    note="Modulates distance decay by place-preference affinity ratio; clamp keeps beta >= 0.05"
)

# ── Temporal distribution: departure times ────────────────────────────────────
# Source: MOB2019 peak hours. Normal distributions truncated to plausible windows.
# Parameters: (mean_min_from_midnight, sigma_min, window_lo, window_hi)

DEPARTURE_DIST: dict[str, _P] = {
    "work_out":        _P((8*60,    30, 6*60,  10*60),  "[MOB2019b]",
                           note="Peak 07:30–09:00; mean 08:00"),
    "work_ret":        _P((18*60,   40, 16*60, 21*60),  "[MOB2019b]",
                           note="Peak 17:00–19:00; mean 18:00"),
    "grocery":         _P((14*60,   90, 9*60,  20*60),  "[HETUS2010]", proxy=True,
                           note="Midday grocery run; broad window 09:00–20:00"),
    "shopping":        _P((14*60,   90, 10*60, 20*60),  "[HETUS2010]", proxy=True,
                           note="Non-grocery retail; retail hours window"),
    "education":       _P(( 8*60,   30,  7*60, 10*60),  "[HETUS2010]", proxy=True,
                           note="Morning class start; mirrors work departure"),
    "leisure_indoor":  _P((17*60,  120, 14*60, 23*60),  "[HETUS2010]", proxy=True,
                           note="Afternoon/evening; renamed from 'leisure'"),
    "leisure_outdoor": _P(( 9*60,  120,  7*60, 19*60),  "[HETUS2010]", proxy=True,
                           note="Morning preferred for outdoor activity; shorter window"),
    "healthcare":      _P((11*60,   60,  8*60, 17*60),  "[HETUS2010]", proxy=True,
                           note="Appointment hours; daytime only"),
    "civic":           _P((11*60,   90,  9*60, 17*60),  "[HETUS2010]", proxy=True,
                           note="Office hours"),
}

# Conscientiousness → departure time variance reduction
# High conscientiousness (0.8) compresses σ by 30%; low (0.2) expands by 30%.
# Source: theory (Big Five C → behavioural regularity); no direct citation.
CONSCIENTIOUSNESS_SIGMA_COEFF: _P = _P(
    0.6, "Theory (Big Five C → schedule regularity). No direct citation.",
    note="Applied as: sigma *= (1 - COEFF * (conscientiousness - 0.5))"
)

# Present bias → departure time delay
# Source: Laibson (1997) [LAIBSON1997]; Ariely & Wertenbroch (2002).
# High present bias (β close to 0.5) → later departures (procrastination).
# Applied as: departure += PRESENT_BIAS_DELAY * (1 - present_bias)
# present_bias=1.0 (time-consistent) → no delay. present_bias=0.5 → +15 min.
PRESENT_BIAS_DELAY_MIN: _P = _P(
    30.0, "[LAIBSON1997] operationalised",
    note="Applied as: delay = COEFF * (1 - present_bias); range 0–30 min"
)

# ── Travel time estimates ──────────────────────────────────────────────────────
# Simple lookup: travel time ≈ distance / speed, by mode.
# Andorra-specific speeds reflect mountain terrain and traffic congestion.
# Source: [MOB2019] average travel speed estimates.

SPEED_KMH: dict[str, _P] = {
    "car":  _P(25.0, "[MOB2019]", note="Urban Andorra; congestion + switchbacks"),
    "bus":  _P(18.0, "[MOB2019]", note="Includes stops and wait time"),
    "walk": _P( 4.5, "Standard pedestrian speed"),
    "taxi": _P(23.0, "[MOB2019] proxy", proxy=True,
                note="Fallback motorised access for taxi/carpool; slightly slower than private car"),
}
