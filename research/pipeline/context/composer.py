"""
World Context Composer — the pipeline's output stage.

Combines all ingested data layers into a single structured world context string
that is injected as the cached LLM system prompt for preference generation.

This is the key abstraction that makes the pipeline country-agnostic:
  AOI (any GeoJSON polygon)
    + Physical Layer (OSM features → H3 cells)
    + Institutional Layer (World Bank indicators)
    + Cultural Layer (Inglehart-Welzel + WVS estimates)
    + Demographic Layer (WorldPop age/sex structure)
    → WorldContext (a structured string ready for LLM caching)

The WorldContext is what differentiates a Boston agent from a Dakar agent:
same demographic profile, radically different world context, radically different
preference profiles.

Layer architecture
──────────────────
PHYSICAL LAYER     "What exists here" — infrastructure, services, mobility
DEMOGRAPHIC LAYER  "Who lives here" — age/sex composition, nationality mix
INSTITUTIONAL LAYER "What rules apply here" — governance, law, rights, policies
CULTURAL LAYER     "What is normal here" — values, norms, social expectations
SITUATIONAL LAYER  "What is happening now" — current stresses, debates, events

Optional future layers:
  OPINION LAYER    "What do people think" — surveys, public sentiment
  DILEMMA LAYER    "What conflicts exist" — real policy debates, local tensions
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorldContext:
    """
    Fully assembled world context ready for LLM injection.

    All text is structured for maximum LLM comprehension:
    numbered sections, empirical anchors, explicit uncertainty flags.
    """
    aoi_name: str
    iso3: str
    layers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_prompt(self) -> str:
        """
        Render the world context as a structured system prompt string.
        This string is passed to the LLM with cache_control: ephemeral
        so it is only processed once for the entire population generation run.
        """
        header = (
            f"=== WORLD CONTEXT: {self.aoi_name.upper()} ({self.iso3}) ===\n"
            "This context describes the real-world environment in which synthetic agents exist.\n"
            "Use it to generate preference profiles that are internally consistent with the\n"
            "structural position, affordances, and constraints of this specific place.\n"
        )
        sections = []
        order = ["physical", "demographic", "institutional", "cultural", "situational", "opinion", "dilemma"]
        for key in order:
            if key in self.layers and self.layers[key]:
                title = key.upper().replace("_", " ")
                sections.append(f"\n--- {title} LAYER ---\n{self.layers[key]}")

        footer = (
            "\n=== AGENT GENERATION INSTRUCTIONS ===\n"
            "Generate a preference profile that is:\n"
            "(a) Internally consistent: Big Five traits should cohere with Schwartz values\n"
            "    and behavioral economics parameters (high Neuroticism → higher loss_aversion;\n"
            "    high Conscientiousness → lower discount_rate; high Agreeableness → higher trust).\n"
            "(b) Sociologically grounded: reflect the structural position of this person\n"
            "    in the society described above — their access to resources, institutional\n"
            "    power, mobility options, and cultural capital.\n"
            "(c) Empirically calibrated: Big Five scores approximate population norms\n"
            "    (mean ≈ 0.50, SD ≈ 0.12–0.15 across the full population). Do not compress\n"
            "    variance toward the mean — individuals deviate from the mean.\n"
            "(d) Contextually specific: this agent lives in the AOI described above,\n"
            "    not a generic city. Their fears, goals, and political positions must\n"
            "    reflect local realities.\n"
        )
        return header + "".join(sections) + footer


class WorldContextComposer:
    """
    Assembles a WorldContext from independently computed data layers.

    Each layer is a string produced by its respective builder module.
    Layers are optional — the composer degrades gracefully when data is unavailable.
    """

    def __init__(self, aoi_name: str, iso3: str, metadata: dict | None = None):
        self.aoi_name = aoi_name
        self.iso3 = iso3
        self.metadata = metadata or {}
        self._layers: dict[str, str] = {}

    def add_physical_layer(self, text: str) -> "WorldContextComposer":
        self._layers["physical"] = text
        return self

    def add_demographic_layer(self, text: str) -> "WorldContextComposer":
        self._layers["demographic"] = text
        return self

    def add_institutional_layer(self, text: str) -> "WorldContextComposer":
        self._layers["institutional"] = text
        return self

    def add_cultural_layer(self, text: str) -> "WorldContextComposer":
        self._layers["cultural"] = text
        return self

    def add_situational_layer(self, text: str) -> "WorldContextComposer":
        self._layers["situational"] = text
        return self

    def add_opinion_layer(self, text: str) -> "WorldContextComposer":
        """Optional: survey results, public sentiment, local opinion data."""
        self._layers["opinion"] = text
        return self

    def add_dilemma_layer(self, text: str) -> "WorldContextComposer":
        """Optional: active policy debates, real societal dilemmas."""
        self._layers["dilemma"] = text
        return self

    def build(self) -> WorldContext:
        return WorldContext(
            aoi_name=self.aoi_name,
            iso3=self.iso3,
            layers=dict(self._layers),
            metadata=self.metadata,
        )


# ── Layer builders ────────────────────────────────────────────────────────────

def build_physical_layer_text(physical_layer) -> str:
    """Convert a PhysicalLayer into LLM-ready descriptive text."""
    summary = physical_layer.summary()
    lines = [
        "Physical infrastructure present in the AOI (OpenStreetMap data):",
        "",
    ]
    labels = {
        "healthcare":  ("Healthcare facilities", "hospitals, clinics, pharmacies"),
        "education":   ("Educational institutions", "schools, universities, libraries"),
        "commerce":    ("Commercial nodes", "supermarkets, banks, retail"),
        "transit":     ("Public transit stops", "bus, tram, metro stops"),
        "leisure":     ("Leisure & hospitality", "parks, restaurants, bars, cinemas"),
        "civic":       ("Civic facilities", "town halls, police, post offices"),
        "employment":  ("Employment zones", "offices, industrial, commercial areas"),
    }
    for cat, (label, examples) in labels.items():
        count = summary.get(cat, 0)
        lines.append(f"  {label} ({examples}): {count} mapped nodes")

    total = sum(summary.values())
    lines += [
        "",
        f"Total mapped features: {total}",
        "Interpretation: presence/absence of infrastructure categories directly shapes",
        "which daily activities are feasible and which require crossing cell boundaries.",
    ]
    return "\n".join(lines)


def build_demographic_layer_text(age_sex_structure, nationality_mix: dict | None = None,
                                  total_population: int | None = None) -> str:
    """Build demographic layer text from WorldPop age/sex structure."""
    lines = ["Demographic composition of the AOI population:"]

    if total_population:
        lines.append(f"  Estimated total population: {total_population:,}")

    # Summarise age structure into broad groups
    bins = age_sex_structure.bins
    groups = {
        "Children (0–14)":      ["0-4", "5-9", "10-14"],
        "Youth (15–24)":        ["15-19", "20-24"],
        "Working age (25–54)":  ["25-29", "30-34", "35-39", "40-44", "45-49", "50-54"],
        "Pre-retirement (55–64)":["55-59", "60-64"],
        "Older adults (65+)":   ["65-69", "70-74", "75-79", "80+"],
    }
    lines.append("  Age structure (Source: WorldPop / UN WPP 2022):")
    for group_label, group_bins in groups.items():
        total_pct = sum(
            (bins.get(b, {}).get("M", 0) + bins.get(b, {}).get("F", 0))
            for b in group_bins
        ) * 100
        lines.append(f"    {group_label}: {total_pct:.1f}%")

    if nationality_mix:
        lines.append("  Nationality composition (Estadística d'Andorra 2023):")
        for nat, pct in sorted(nationality_mix.items(), key=lambda x: -x[1]):
            lines.append(f"    {nat}: {pct:.1f}%")

    lines += [
        "",
        "Implication for agent generation: the age structure shapes the dominant life-stage",
        "concerns (housing, childcare, retirement). The nationality mix shapes institutional",
        "trust, acculturation stress, and access to legal protections.",
    ]
    return "\n".join(lines)


def build_institutional_layer_text(profile) -> str:
    """Build institutional layer text from a WorldBank InstitutionalProfile."""
    lines = [
        "Institutional and economic context (World Bank Open Data):",
        "",
        profile.governance_summary(),
        profile.economic_summary(),
        "",
        "Institutional interpretation:",
    ]

    # Governance quality signal
    rl = profile.get("rule_of_law", 0)
    if rl > 1.0:
        lines.append(
            "  Strong rule of law: agents can generally trust legal contracts and property rights."
        )
    elif rl > 0.0:
        lines.append(
            "  Moderate rule of law: formal institutions function but enforcement is uneven."
        )
    else:
        lines.append(
            "  Weak rule of law: institutional trust is structurally low across all groups."
        )

    # Economic stress signal
    gdp = profile.get("gdp_per_capita_ppp", 0) or 0
    gini = profile.get("gini", 0) or 0
    if gdp > 30000 and gini < 35:
        lines.append(
            "  High-income, relatively equal society: economic stress is unevenly distributed\n"
            "  and concentrated in specific demographic groups (immigrants, low-wage workers)."
        )
    elif gdp < 5000:
        lines.append(
            "  Low-income context: economic pressure is a near-universal background condition\n"
            "  across most of the population, not specific to marginal groups."
        )

    return "\n".join(lines)


def build_cultural_layer_text(
    inglehart_welzel: tuple[float, float] | None = None,
    wvs_trust: float | None = None,
    notes: str | None = None,
) -> str:
    """
    Build cultural layer text.

    Parameters
    ----------
    inglehart_welzel : (x, y) position on Inglehart-Welzel map
                       x: Traditional (0) ↔ Secular-rational (1)
                       y: Survival (0) ↔ Self-expression (1)
    wvs_trust        : WVS Wave 7 interpersonal trust score for country (0–1)
    notes            : Country-specific cultural notes
    """
    lines = ["Cultural and values context:"]

    if inglehart_welzel:
        x, y = inglehart_welzel
        trad_sec = "Secular-rational" if x > 0.5 else "Traditional"
        surv_sel = "Self-expression" if y > 0.5 else "Survival"
        lines += [
            f"  Inglehart-Welzel cultural position: {trad_sec} × {surv_sel}",
            "  (Source: World Values Survey 2023 cultural map)",
            f"  Coordinates: Traditional–Secular {x:.2f}, Survival–Self-expression {y:.2f}",
        ]

    if wvs_trust is not None:
        lines += [
            f"  Generalised interpersonal trust (WVS Q57): {wvs_trust:.2f}",
            "  ('Most people can be trusted' — 0=No, 1=Yes)",
        ]

    if notes:
        lines += ["", notes]

    lines += [
        "",
        "Cultural implication for Schwartz values: the Inglehart-Welzel position predicts",
        "which Schwartz value types are dominant. Secular-rational × Self-expression societies",
        "emphasise Self-direction and Universalism. Traditional × Survival societies",
        "emphasise Security and Conformity.",
    ]
    return "\n".join(lines)


def build_situational_layer_text(current_stresses: list[str], active_policies: list[str]) -> str:
    """Build the situational layer — what is actively happening in the AOI right now."""
    lines = ["Current situational context (active stresses and policy debates):"]
    if current_stresses:
        lines.append("  Active structural stresses:")
        for s in current_stresses:
            lines.append(f"    - {s}")
    if active_policies:
        lines.append("  Active or debated policy interventions:")
        for p in active_policies:
            lines.append(f"    - {p}")
    lines += [
        "",
        "These stresses and debates are salient to agents — they appear in daily news,",
        "conversations, and personal experience. They should influence political issue salience,",
        "primary fears, and short-term goals in the generated preference profiles.",
    ]
    return "\n".join(lines)
