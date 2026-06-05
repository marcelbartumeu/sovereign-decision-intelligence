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
    Reference WEEKLY activity-participation rate for this layer type across
    the general population.
    Source: Gershuny, J. & Fisher, K. (2014).  Multinational Time Use Study
            (MTUS) Wave 6 (2005–2015), Western Europe subset
            (AT, BE, DE, ES, FR, IT, NL, UK).  University of Oxford.
            https://www.timeuse.org/mtus
    None for housing layers and employment layers where a weekly participation
    rate is structural (every working adult "participates" daily).

structural_prior: float | None
    Baseline preference probability used when mtus_ref_rate is None.
    Derived from demographic base rates (income distribution, age share).
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
3. Provide mtus_ref_rate if a MTUS-equivalent activity exists, else structural_prior.
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
# mtus_ref_rate sources
# ─────────────────────
# All MTUS rates are Western Europe weekly participation averages from
# Gershuny & Fisher (2014), MTUS Wave 6.  Activity code mappings:
#   21  → shopping (retail, grocery)
#   23  → personal care / health services
#   41  → socialising (eating out, bars, cafés)
#   51  → sport / exercise / outdoor recreation
#   61  → religious attendance
#   62  → civic / political activities
#   10  → adult education / training
#
# structural_prior sources
# ────────────────────────
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
        mtus_ref_rate    = 0.72,   # MTUS code 21 (non-grocery shopping), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "2100",  # Retail Sales
        osm_tag          = "shop=*",
        notes            = (
            "Non-grocery retail: clothing, electronics, souvenirs, specialty goods.  "
            "Excludes grocery (D15)."
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
        structural_prior = 0.55,   # Estimated from MTUS paid-work activity fraction
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
        mtus_ref_rate    = 0.30,   # MTUS: adult education/training participation (non-mandatory)
        structural_prior = None,
        lbcs_code        = "6100",  # Educational Institutions
        osm_tag          = "amenity=school",
        notes            = (
            "Schools, universities, libraries, adult education centres.  "
            "Mandatory for students; discretionary for adult learners."
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
        mtus_ref_rate    = 0.18,   # MTUS code 61 (religious attendance), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "6610",  # Religious Assembly
        osm_tag          = "amenity=place_of_worship",
        notes            = "Churches, mosques, temples, other places of worship.",
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
        mtus_ref_rate    = 0.12,   # MTUS code 23 (health services), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "6500",  # Health Care
        osm_tag          = "amenity=hospital",
        notes            = "Hospitals, clinics, general practitioners.",
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
        mtus_ref_rate    = 0.08,   # MTUS code 62 (civic/political activities), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "6300",  # Public Administration
        osm_tag          = "amenity=townhall",
        notes            = "Town halls, public offices, administrative buildings.",
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
        structural_prior = 0.38,   # Precarious + low + lower_middle income share (0.54 × salience)
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
        structural_prior = 0.38,   # Estimated from MTUS professional-worker paid-work fraction
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
        mtus_ref_rate    = 0.85,   # MTUS code 21 grocery sub-activity; highest participation
        structural_prior = None,
        lbcs_code        = "2110",  # Food Retail
        osm_tag          = "shop=supermarket",
        notes            = (
            "Supermarkets, food markets, fresh produce vendors.  "
            "Near-universal necessity with very high baseline."
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
        mtus_ref_rate    = 0.42,   # MTUS code 51 (sport/exercise), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "8100",  # Recreational
        osm_tag          = "leisure=sports_centre",
        notes            = "Gyms, sports halls, indoor recreation facilities.",
    ),

    # ── D17: Pharmacy ─────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D17",
        name              = "Pharmacy",
        layer_type        = "destination",
        activity_class    = "maintenance",
        population_served = "Elderly, health-anxious (high neuroticism), and chronically ill",
        mtus_ref_rate    = 0.10,   # Estimated from MTUS healthcare-adjacent activities
        structural_prior = None,
        lbcs_code        = "6530",  # Pharmacy/Drug Store
        osm_tag          = "amenity=pharmacy",
        notes            = "Pharmacies, dispensing chemists.",
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
        mtus_ref_rate    = 0.12,   # MTUS code 10 (adult education/training), W. Europe
        structural_prior = None,
        lbcs_code        = "6140",  # Vocational/Career Education
        osm_tag          = "amenity=college",
        notes            = "Vocational schools, professional development centres, upskilling facilities.",
    ),

    # ── D19: Daycare Center ───────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D19",
        name              = "Daycare Center",
        layer_type        = "destination",
        activity_class    = "mandatory",
        population_served = "Parents of children aged 0–10; agreeableness and family orientation",
        mtus_ref_rate    = 0.18,   # Estimated as parent-age share with young children
        structural_prior = None,
        lbcs_code        = "6120",  # Child Care / Early Education
        osm_tag          = "amenity=childcare",
        notes            = "Childcare centres, nurseries, kindergartens.",
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
        mtus_ref_rate    = 0.48,   # MTUS code 42 (eating out), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "2131",  # Restaurant / Full-Service Dining
        osm_tag          = "amenity=restaurant",
        notes            = "Full-service restaurants; excludes fast food and cafés.",
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
        mtus_ref_rate    = 0.52,   # MTUS: slightly higher than restaurant — lower cost barrier
        structural_prior = None,
        lbcs_code        = "2132",  # Café / Coffee Shop
        osm_tag          = "amenity=cafe",
        notes            = "Coffee shops, patisseries, casual meeting spaces.",
    ),

    # ── D23: Bar ──────────────────────────────────────────────────────────────
    LayerSpec(
        layer_id          = "D23",
        name              = "Bar",
        layer_type        = "destination",
        activity_class    = "discretionary",
        population_served = "Young adults (18–35), extraverted, hedonism-oriented",
        mtus_ref_rate    = 0.28,   # MTUS: lower than café due to age restriction
        structural_prior = None,
        lbcs_code        = "2134",  # Bar / Nightlife
        osm_tag          = "amenity=bar",
        notes            = "Bars, cocktail bars, evening social venues.",
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
        mtus_ref_rate    = 0.30,   # MTUS: slightly higher than bar due to broader age range
        structural_prior = None,
        lbcs_code        = "2135",  # Pub / Local Drinking Establishment
        osm_tag          = "amenity=pub",
        notes            = "Traditional pubs, neighbourhood drinking establishments.",
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
        mtus_ref_rate    = 0.58,   # MTUS code 51 (outdoor recreation/walking), W. Europe weekly
        structural_prior = None,
        lbcs_code        = "8110",  # Park / Open Space
        osm_tag          = "leisure=park",
        notes            = "Urban parks, green spaces, public gardens.",
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
MTUS_BENCHMARKED_IDS: list[str] = [
    s.layer_id for s in LAYER_REGISTRY if s.mtus_ref_rate is not None
]

# Theoretically related destination clusters used in validity metrics
# (see place_preferences.py → PlacePreferenceValidator.social_cluster_coherence)

# Social/leisure cluster: all driven by extraversion + hedonism
SOCIAL_CLUSTER: list[str]       = ["D21", "D22", "D23", "D24"]

# Health/maintenance cluster: both driven by age and neuroticism
HEALTH_CLUSTER: list[str]       = ["D8", "D17"]

# Housing tiers: mutually exclusive by income (should be negatively correlated)
HOUSING_TIER_CLUSTER: list[str] = ["D12", "D13"]


# ── Public helpers ─────────────────────────────────────────────────────────────

def layer(layer_id: str) -> LayerSpec:
    """Return the LayerSpec for a given layer ID.  Raises KeyError if absent."""
    return LAYER_BY_ID[layer_id]


def base_rate(layer_id: str) -> float:
    """Return the baseline preference probability for a layer (MTUS or structural prior)."""
    return LAYER_BY_ID[layer_id].base_rate()
