"""
H3 destination layer taxonomy — authoritative source of truth.

Design
──────
This module is the SINGLE SOURCE OF TRUTH for all H3 destination layer IDs
used in the profile generation pipeline.  Every pipeline component that needs
to know which layers exist — preference computation, validation metrics, export,
visualisation — MUST import from here rather than hardcoding layer strings.

Layer classification axes
─────────────────────────
layer_type:
    "destination"  — place agents travel to for a specific activity
    "housing"      — residential layer (semi-permanent home-base)
    "employment"   — layer associated with work / income-generating activity

activity_class:
    "mandatory"    — non-negotiable activities (work, school, essential care)
    "maintenance"  — household upkeep and personal health (grocery, pharmacy)
    "discretionary"— social, leisure, or self-development activities
    "residential"  — home location (housing layers only)

mtus_ref_rate: float | None
    DEPRECATED — all entries are None.  The original MTUS rates were
    not reproducibly sourced from published MTUS tables and have been
    replaced by structural_prior values derived from verified Eurostat
    surveys.  Field retained for schema compatibility.

structural_prior: float | None
    Reference WEEKLY activity-participation rate (proportion of adults
    doing the activity at least once per week) used as the RUM intercept.
    Verified sources (see LAYER_REGISTRY header):
      HETUS 2010   — shopping + personal services combined: ~40%/day
      Eurobarometer 525 (2022) — sport/exercise: 38% weekly
      EU-SILC 2015 (ilc_scp03) — cultural activities: 45%/43%/42% annually
      EHIS Wave 2 (2013–15)    — GP consultations: 37% in last 4 weeks
      Pew Research 2018        — W. Europe weekly religious: ~10–15%
      AES 2022                 — adult education: 47% annually
    PROXY entries are marked in notes; no direct Eurostat sub-category
    data is available for those layers.
    Both fields cannot be None simultaneously — at least one must be set.

lbcs_code:
    Land-Based Classification Standards code (APA/AICP 2001).
    Enables cross-country mapping to an internationally used standard.

osm_tag:
    Primary OpenStreetMap tag.  Used to link this taxonomy to OSM-derived
    H3 activity layers in automated pipeline ingestion.

Handling missing / unavailable layers
───────────────────────────────────────
If a layer ID is absent from the H3 data for a given country deployment:
  ■ The layer remains defined in this registry.
  ■ Its preference weight is stored as None in the agent profile.
  ■ Validation metrics exclude None-weight layers from their denominators.
  ■ Downstream consumers must handle None gracefully.

Adding layers for new countries
────────────────────────────────
1. Add a LayerSpec entry to LAYER_REGISTRY.
2. Use the D<integer> convention for layer_id.
3. Provide structural_prior from the best available Eurostat or equivalent survey.
4. Add a coefficient row to COEFFICIENT_MATRIX in place_preferences.py.
5. Add any expected monotonic relationships to MONOTONE_CHECKS in place_preferences.py.
6. Nothing else needs to change — all downstream modules iterate over LAYER_REGISTRY.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class LayerSpec:
    """
    Immutable specification for one H3 destination layer.
    Defined once in LAYER_REGISTRY; never modified at runtime.
    """
    layer_id:          str            # e.g. "D3"
    name:              str            # human-readable label
    layer_type:        str            # "destination" | "housing" | "employment"
    activity_class:    str            # "mandatory" | "maintenance" | "discretionary" | "residential"
    population_served: str            # primary user group
    mtus_ref_rate:     Optional[float]  # MTUS weekly participation rate; None if not applicable
    structural_prior:  Optional[float]  # fallback base rate for housing/employment layers
    lbcs_code:         Optional[str]    # APA/AICP LBCS code
    osm_tag:           Optional[str]    # primary OSM tag for automated ingestion
    notes:             str = ""

    def base_rate(self) -> float:
        """
        Return the reference base rate for this layer.
        Prefers mtus_ref_rate; falls back to structural_prior.
        Raises ValueError if neither is set.
        """
        if self.mtus_ref_rate is not None:
            return self.mtus_ref_rate
        if self.structural_prior is not None:
            return self.structural_prior
        raise ValueError(f"Layer {self.layer_id!r} has no base rate defined.")


# ── Authoritative H3 Layer Registry ───────────────────────────────────────────
#
# structural_prior sources (verified Eurostat surveys — all rates are weekly)
# ─────────────────────────────────────────────────────────────────────────────
# [HETUS]   Eurostat (2018). Harmonised European Time Use Survey 2010.
#           shopping+services combined: ~40%/day (W. Europe).
#           Daily → weekly not simply additive (clustering); see per-layer notes.
# [EUROB]   European Commission (2022). Eurobarometer Special Survey 525:
#           Sport and Physical Activity.  38% exercise at least 1×/week.
# [SILC]    Eurostat (2015). EU-SILC cultural participation (ilc_scp03).
#           Cinema: 45%, Museums: 43%, Theatre: 42% at least once/year.
# [EHIS]    Eurostat (2014). European Health Interview Survey Wave 2.
#           37% consulted GP in last 4 weeks (≈ 9%/week).
# [PEW]     Pew Research Center (2018). Being Christian in Western Europe.
#           W. Europe monthly religious attendance median ~22%; weekly ~10–15%.
#           Southern Europe (Spain proxy) weekly ~15%.
# [AES]     Eurostat (2022). Adult Education Survey.  47% annually.
# [PROXY]   No direct Eurostat sub-category data; derived estimate documented.
#
# Housing/employment structural_prior sources
# ────────────────────────────────────────────
# Derived from Andorra ACTIVE_CONFIG income distribution and age shares
# (SAIG Anuari Estadístic 2023 / UN WPP 2022).  Generalise by substituting
# a different country's ACTIVE_CONFIG when deploying elsewhere.

LAYER_REGISTRY: list[LayerSpec] = [

    # ── D3: Retail Store ───────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D3",
        name              = "Retail Store",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = (
            "General population; amplified among extraverted and higher-income "
            "individuals; suppressed among highly price-sensitive agents"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.52,   # PROXY: non-grocery retail weekly participation; HETUS 2010
                                   # diary-day shopping participation ~28–35% weekday, ~55% weekend;
                                   # weekly rate (≥1 visit/week) estimated ~52% for retail-heavy Andorra
        lbcs_code        = "2100",  # Retail Sales
        osm_tag          = "shop=*",
        notes            = (
            "Non-grocery retail: clothing, electronics, souvenirs, specialty goods.  "
            "Excludes grocery (D15).  [PROXY: derived from HETUS combined shopping daily rate]"
        ),
    ),

    # ── D4: Commercial ────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D4",
        name              = "Commercial",
        layer_type        = "employment",
        activity_class    = "mandatory",
        population_served = (
            "Working-age adults employed in commercial or service sectors"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.55,   # PROXY: Andorra employment rate ~74% (SAIG 2023);
                                   # commercial sector ~75% of employed → ~55% of adults [PROXY]
        lbcs_code        = "2200",  # Commercial Services
        osm_tag          = "landuse=commercial",
        notes            = (
            "General commercial district: service offices, business services.  "
            "Employment destination rather than discretionary visit."
        ),
    ),

    # ── D5: Education ─────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D5",
        name              = "Education",
        layer_type        = "destination",
        activity_class    = "mandatory",
        population_served = (
            "Students (all ages) and educators; higher preference among "
            "curious and achievement-oriented adults"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.22,   # PROXY [AES]: AES 2022: 47%/year adult education →
                                   # ~4%/week derived; student school trips structural ~14%/day;
                                   # combined weekly estimate ~22% [PROXY]
        lbcs_code        = "6100",  # Educational Institutions
        osm_tag          = "amenity=school",
        notes            = (
            "Schools, universities, libraries, adult education centres.  "
            "Mandatory for students; discretionary for adult learners.  "
            "[PROXY: AES 2022 adult 47%/yr; student school attendance structural]"
        ),
    ),

    # ── D6: Housing ───────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D6",
        name              = "Housing",
        layer_type        = "housing",
        activity_class    = "residential",
        population_served = "General population — aggregate residential preference",
        mtus_ref_rate    = None,
        structural_prior = 0.75,   # Near-universal base; high housing salience skews further
        lbcs_code        = "1100",  # General Residential
        osm_tag          = "landuse=residential",
        notes            = (
            "General-purpose residential land; base home layer.  "
            "Preference weight reflects salience of housing choice, not a trip destination."
        ),
    ),

    # ── D7: Religious ─────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D7",
        name              = "Religious",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Tradition/conformity value holders; older cohorts; "
            "high bonding-capital communities"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.12,   # [PEW]: Pew 2018 W. Europe weekly attendance median ~10–15%;
                                   # Southern Europe (Spain proxy for Andorra) ~15%; using 0.12
        lbcs_code        = "6610",  # Religious Assembly
        osm_tag          = "amenity=place_of_worship",
        notes            = "Churches, mosques, temples, other places of worship.  [PEW 2018]",
    ),

    # ── D8: Healthcare ────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D8",
        name              = "Healthcare",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = (
            "Elderly, neurotic (health-anxious), and financially stressed individuals; "
            "gradient increases with age"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.09,   # [EHIS]: EHIS Wave 2: 37% consulted GP in last 4 weeks
                                   # → 9.25%/week (37%/4); rounds to 0.09
        lbcs_code        = "6500",  # Health Care
        osm_tag          = "amenity=hospital",
        notes            = "Hospitals, clinics, general practitioners.  [EHIS Wave 2]",
    ),

    # ── D9: Government Operations ─────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D9",
        name              = "Government Operations",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = (
            "Civically engaged adults; predicted by local_engagement "
            "and institutional trust"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.06,   # PROXY: civic/admin visits infrequent; less than healthcare;
                                   # no direct Eurostat sub-category published; proxy ~6%/week
        lbcs_code        = "6300",  # Public Administration
        osm_tag          = "amenity=townhall",
        notes            = "Town halls, public offices, administrative buildings.  [PROXY]",
    ),

    # ── D10: Mid-Career Housing ───────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D10",
        name              = "Mid-Career Housing",
        layer_type        = "housing",
        activity_class    = "residential",
        population_served = (
            "Working-age adults (25–55) in middle-income brackets"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.42,   # Working age (67%) × mid-income bracket (22%+13%+27% = 62%)
        lbcs_code        = "1500",  # Mixed-density Residential
        osm_tag          = "landuse=residential",
        notes            = (
            "Mid-density residential zone suited to employed middle-income households.  "
            "Preference peaks at middle-income / working-age intersection."
        ),
    ),

    # ── D11: Senior Housing ───────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D11",
        name              = "Senior Housing",
        layer_type        = "housing",
        activity_class    = "residential",
        population_served = "Adults 60+; increases sharply with age",
        mtus_ref_rate    = None,
        structural_prior = 0.11,   # Age 65+ share: 10.6% (SAIG 2023)
        lbcs_code        = "1720",  # Senior/Retirement Housing
        osm_tag          = "building=retirement_home",
        notes            = "Assisted living, retirement communities, senior-adapted residential.",
    ),

    # ── D12: Affordable Housing ───────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D12",
        name              = "Affordable Housing",
        layer_type        = "housing",
        activity_class    = "residential",
        population_served = "Low-income, financially stressed, and precarious-income individuals",
        mtus_ref_rate    = None,
        structural_prior = 0.38,   # PROXY: precarious (10%) + low (18%) + lower_middle (22%)
                                   # income share = 50% of population; only subset actively
                                   # seek/occupy affordable housing → estimated 38% [PROXY]
        lbcs_code        = "1400",  # Social/Affordable Housing
        osm_tag          = "social_facility=housing",
        notes            = "Social housing, subsidised rentals, affordable housing units.",
    ),

    # ── D13: Executive Housing ────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D13",
        name              = "Executive Housing",
        layer_type        = "housing",
        activity_class    = "residential",
        population_served = "High-income (comfortable, wealthy) individuals with low financial stress",
        mtus_ref_rate    = None,
        structural_prior = 0.11,   # Comfortable + wealthy income share: 8% + 3% = 11%
        lbcs_code        = "1600",  # Luxury/High-End Residential
        osm_tag          = "landuse=residential",
        notes            = "High-end residential zones; villas, upscale apartments.",
    ),

    # ── D14: Headquarter Office ───────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D14",
        name              = "Headquarter Office",
        layer_type        = "employment",
        activity_class    = "mandatory",
        population_served = "Professional and managerial workers; achievement/self-direction oriented",
        mtus_ref_rate    = None,
        structural_prior = 0.38,   # PROXY: professional/managerial workers ~22% of employed;
                                   # Andorra financial/HQ sector elevated; estimated ~38% [PROXY]
        lbcs_code        = "2300",  # Office
        osm_tag          = "office=*",
        notes            = "Corporate headquarters, professional offices, financial centres.",
    ),

    # ── D15: Grocery-Market ───────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D15",
        name              = "Grocery-Market",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = "Near-universal; essential for all households regardless of income",
        mtus_ref_rate    = None,
        structural_prior = 0.85,   # [HETUS]: HETUS 2010 shopping+services combined ~40%/day
                                   # → weekly near-universal; grocery-specific ~3–4×/week
                                   # → weekly participation ~85% [derived]
        lbcs_code        = "2110",  # Food Retail
        osm_tag          = "shop=supermarket",
        notes            = (
            "Supermarkets, food markets, fresh produce vendors.  "
            "Near-universal necessity with very high baseline.  [HETUS 2010, derived]"
        ),
    ),

    # ── D16: Recreation & Fitness ─────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D16",
        name              = "Recreation & Fitness",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Active adults; extraversion and hedonism drivers; "
            "declines with age post-65"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.38,   # [EUROB]: Eurobarometer Special Survey 525 (2022):
                                   # 38% of EU adults exercise at least once per week
        lbcs_code        = "8100",  # Recreational
        osm_tag          = "leisure=sports_centre",
        notes            = "Gyms, sports halls, indoor recreation facilities.  [EUROB 2022]",
    ),

    # ── D17: Pharmacy ─────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D17",
        name              = "Pharmacy",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = "Elderly, health-anxious (high neuroticism), and chronically ill",
        mtus_ref_rate    = None,
        structural_prior = 0.12,   # PROXY [EHIS]: GP ~9%/week [EHIS]; pharmacy visits higher
                                   # (OTC purchases, repeat prescriptions); estimated ~12%/week
        lbcs_code        = "6530",  # Pharmacy/Drug Store
        osm_tag          = "amenity=pharmacy",
        notes            = "Pharmacies, dispensing chemists.  [PROXY: EHIS GP rate + OTC uplift]",
    ),

    # ── D18: Career Training ──────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D18",
        name              = "Career Training",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Achievement and self-direction oriented adults; youth; "
            "upwardly mobile workers"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.08,   # PROXY [AES]: AES 2022: 47%/year; ~4%/week derived;
                                   # course-based attendance clusters → effective weekly
                                   # trip rate when enrolled ~8% [PROXY]
        lbcs_code        = "6140",  # Vocational/Career Education
        osm_tag          = "amenity=college",
        notes            = "Vocational schools, professional development centres, upskilling.  [AES 2022, PROXY]",
    ),

    # ── D19: Daycare Center ───────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D19",
        name              = "Daycare Center",
        layer_type        = "destination",
        activity_class    = "mandatory",
        population_served = "Parents of children aged 0–10; agreeableness and family orientation",
        mtus_ref_rate    = None,
        structural_prior = 0.14,   # PROXY: ~20% of adults have child under 10;
                                   # ~70% use formal childcare → 14% weekly participation
                                   # (20% × 70% = 14%); drop-off rate near-daily for users [PROXY]
        lbcs_code        = "6120",  # Child Care / Early Education
        osm_tag          = "amenity=childcare",
        notes            = "Childcare centres, nurseries, kindergartens.  [PROXY: structural]",
    ),

    # ── D20: Coworking Office ─────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D20",
        name              = "Coworking Office",
        layer_type        = "employment",
        activity_class    = "mandatory",
        population_served = "Self-employed, remote workers, entrepreneurs; high bridging capital",
        mtus_ref_rate    = None,
        structural_prior = 0.22,   # Eurostat 2022: ~22% EU workers in hybrid/remote arrangements
        lbcs_code        = "2310",  # Flexible/Coworking Office
        osm_tag          = "amenity=coworking_space",
        notes            = "Shared workspaces, innovation hubs, freelancer offices.",
    ),

    # ── D21: Restaurant ───────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D21",
        name              = "Restaurant",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = "Extraverted, hedonistic, higher-income adults; social dining",
        mtus_ref_rate    = None,
        structural_prior = 0.38,   # PROXY: no direct Eurostat restaurant-visit weekly rate;
                                   # NRA/Euromonitor industry estimates suggest 30–40% weekly
                                   # in Western Europe; tourism economy uplifts Andorra [PROXY]
        lbcs_code        = "2131",  # Restaurant / Full-Service Dining
        osm_tag          = "amenity=restaurant",
        notes            = "Full-service restaurants; excludes fast food and cafés.  [PROXY: Nielsen 2015]",
    ),

    # ── D22: Cafe ─────────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D22",
        name              = "Cafe",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Open, extraverted, socially bridging adults; "
            "work-from-café users; broader income range than restaurants"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.42,   # PROXY: slightly higher than restaurant (lower cost, faster visit);
                                   # estimated ~42% visit café at least once/week [PROXY]
        lbcs_code        = "2132",  # Café / Coffee Shop
        osm_tag          = "amenity=cafe",
        notes            = "Coffee shops, patisseries, casual meeting spaces.  [PROXY]",
    ),

    # ── D23: Bar ──────────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D23",
        name              = "Bar",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = "Young adults (18–35), extraverted, hedonism-oriented",
        mtus_ref_rate    = None,
        structural_prior = 0.20,   # PROXY: less frequent than café; younger skew;
                                   # estimated ~20% visit bar at least once/week [PROXY]
        lbcs_code        = "2134",  # Bar / Nightlife
        osm_tag          = "amenity=bar",
        notes            = "Bars, cocktail bars, evening social venues.  [PROXY]",
    ),

    # ── D24: Pub ──────────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D24",
        name              = "Pub",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Bonding-capital rich adults; community regulars; "
            "broader age range than bars"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.22,   # PROXY: slightly higher than bar (broader age range, local regulars);
                                   # estimated ~22%/week [PROXY]
        lbcs_code        = "2135",  # Pub / Local Drinking Establishment
        osm_tag          = "amenity=pub",
        notes            = "Traditional pubs, neighbourhood drinking establishments.  [PROXY]",
    ),

    # ── D25: Park ─────────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D25",
        name              = "Park",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Environmentally salient adults, walkers, open-trait individuals; "
            "near-universal appeal but highest among active outdoor users"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.48,   # PROXY: no direct Eurostat park-visit frequency published;
                                   # WHO (2016) active transport guidelines + Nordic park-use studies
                                   # suggest ~40–55% weekly for urban/peri-urban populations; 0.48 [PROXY]
        lbcs_code        = "8110",  # Park / Open Space
        osm_tag          = "leisure=park",
        notes            = "Urban parks, green spaces, public gardens.  [PROXY: Eurobarometer 2022]",
    ),

    # ── D26: Cultural Venue ───────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D26",
        name              = "Cultural Venue",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Open, achievement-oriented, higher-income adults; "
            "family audiences; broader age range for cinema vs. museum"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.12,   # [SILC]: EU-SILC 2015: cinema 45%/yr + museum 43%/yr
                                   # + theatre 42%/yr (ilc_scp03); combined cultural outing
                                   # ~3×/month for participants → ~12%/week [derived]
        lbcs_code        = "6200",  # Cultural / Entertainment
        osm_tag          = "amenity=cinema",
        notes            = "Cinema, museum, theatre, library, concert hall.  [SILC 2015, derived]",
    ),

    # ── D27: Mountain / Outdoor Sports ────────────────────────────────────────
    LayerSpec(
        layer_id          = "D27",
        name              = "Mountain / Outdoor Sports",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = (
            "Active adults and youth; environmentally salient; "
            "Andorra-specific: ski resorts, hiking trails, mountain biking"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.30,   # PROXY [EUROB + Andorra]: Eurobarometer 38%/week exercise;
                                   # Andorra mountain context elevates outdoor sports;
                                   # estimated 30% weekly [PROXY, Andorra-specific]
        lbcs_code        = "8120",  # Outdoor Recreation / Sports
        osm_tag          = "leisure=ski_resort",
        notes            = (
            "Ski resorts (Grandvalira, Vallnord), hiking trails, mountain biking.  "
            "Andorra-specific; higher base rate than generic European models.  [PROXY: Eurobarometer 2022]"
        ),
    ),

    # ── D28: Personal Services ────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D28",
        name              = "Personal Services",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = (
            "Working-age adults; conscientious, organised individuals; "
            "near-universal necessity across income levels"
        ),
        mtus_ref_rate    = None,
        structural_prior = 0.22,   # PROXY [HETUS]: personal services included in HETUS
                                   # shopping+services combined ~40%/day; services component
                                   # less frequent; banking ~monthly → hairdresser + car etc.
                                   # combined weekly ~22% [PROXY, derived]
        lbcs_code        = "2400",  # Personal / Consumer Services
        osm_tag          = "amenity=bank",
        notes            = "Bank, post office, hairdresser, car repair, dry cleaner.  [PROXY: HETUS derived]",
    ),
]


# ── Index structures ───────────────────────────────────────────────────────────
# These are computed once at import time. All pipeline modules should use these
# rather than filtering LAYER_REGISTRY themselves.

LAYER_BY_ID: dict[str, LayerSpec] = {s.layer_id: s for s in LAYER_REGISTRY}
ALL_LAYER_IDS: list[str]          = [s.layer_id for s in LAYER_REGISTRY]

DESTINATION_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.layer_type == "destination"
]
HOUSING_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.layer_type == "housing"
]
EMPLOYMENT_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.layer_type == "employment"
]
MANDATORY_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.activity_class == "mandatory"
]
MAINTENANCE_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.activity_class == "maintenance"
]
DISCRETIONARY_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.activity_class == "discretionary"
]
EUROSTAT_BENCHMARKED_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.structural_prior is not None
]
# Deprecated alias kept for any existing references
MTUS_BENCHMARKED_IDS = EUROSTAT_BENCHMARKED_IDS

# Theoretically related destination clusters used in validity metrics
# (see place_preferences.py → PlacePreferenceValidator.social_cluster_coherence)

# Social/leisure cluster: all driven by extraversion + hedonism
SOCIAL_CLUSTER: list[str]       = ["D21", "D22", "D23", "D24"]

# Outdoor leisure cluster: driven by environmental values + mobility
OUTDOOR_CLUSTER: list[str]      = ["D25", "D27"]

# Health/maintenance cluster: both driven by age and neuroticism
HEALTH_CLUSTER: list[str]       = ["D8", "D17"]

# Education cluster: different age-group drivers
EDUCATION_CLUSTER: list[str]    = ["D5", "D18", "D19"]

# Housing tiers: mutually exclusive by income (should be negatively correlated)
HOUSING_TIER_CLUSTER: list[str] = ["D12", "D13"]

# Trip-destination layers only (excludes housing — used for trip scheduling)
TRIP_DESTINATION_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY
    if s.layer_type in ("destination", "employment")
]


# ── Public helpers ─────────────────────────────────────────────────────────────

def layer(layer_id: str) -> LayerSpec:
    """Return the LayerSpec for a given layer ID.  Raises KeyError if absent."""
    return LAYER_BY_ID[layer_id]


def base_rate(layer_id: str) -> float:
    """Return the baseline preference probability for a layer (Eurostat/structural prior)."""
    return LAYER_BY_ID[layer_id].base_rate()


# ── Activity → destination layer mapping ───────────────────────────────────────
# Maps schedule activity types to the D-layer IDs that represent plausible
# destinations.  Used by the schedule generator to compute place-preference
# affinity ratios, which modulate Poisson trip rates and gravity-model β.
#
# 8-activity-type architecture (expanded from original 4):
#   work             → employment layers (D4 commercial, D14 HQ, D20 coworking)
#   education        → school (D5), career training (D18), daycare (D19)
#   grocery          → supermarket/food market (D15) — split from non-grocery retail
#   shopping         → non-grocery retail (D3)
#   leisure_indoor   → fitness (D16), dining/drinking (D21-D24), cultural (D26)
#   leisure_outdoor  → urban park (D25), mountain/ski/hiking (D27) [Andorra-specific]
#   healthcare       → hospital/clinic (D8), pharmacy (D17)
#   civic            → religious (D7), government (D9), personal services (D28)
ACTIVITY_LAYER_MAP: dict[str, list[str]] = {
    "work":            ["D4", "D14", "D20"],
    "education":       ["D5", "D18", "D19"],
    "grocery":         ["D15"],
    "shopping":        ["D3"],
    "leisure_indoor":  ["D16", "D21", "D22", "D23", "D24", "D26"],
    "leisure_outdoor": ["D25", "D27"],
    "healthcare":      ["D8", "D17"],
    "civic":           ["D7", "D9", "D28"],
}


def activity_mtus_ref(activity: str) -> float:
    """
    Mean reference base rate across D-layers for an activity type.
    By RUM construction, an average agent's mean place preference equals this value,
    so affinity_ratio = agent_mean_pref / activity_mtus_ref() == 1 at the population mean.
    Returns 0.5 if the activity has no mapped layers.
    Source: HETUS Eurostat aggregate tables (Spain/France proxy for Andorra).
    Values marked PENDING in LayerSpec will be updated once HETUS download is complete.
    """
    ids = ACTIVITY_LAYER_MAP.get(activity, [])
    if not ids:
        return 0.5
    rates = [LAYER_BY_ID[lid].base_rate() for lid in ids]
    return sum(rates) / len(rates)
