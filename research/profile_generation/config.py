"""
Country configuration for the profile generation pipeline.

To switch countries, change one line at the bottom:
    ACTIVE_CONFIG = ANDORRA   →   ACTIVE_CONFIG = BOSTON

What belongs here
─────────────────
REAL empirical data about the country: demographic distributions, economic
indicators, wage data, cultural positioning. These are the ground truth that:
  (a) inform the LLM world context (what the country is actually like), and
  (b) validate the LLM output (does the generated population match reality?).

What does NOT belong here
──────────────────────────
archetypes, sample_demographics — these are LLM OUTPUTS, not inputs.
The workflow is:
  1. Config supplies real-world distributions (this file).
  2. LLM generates N archetypes from the world context.
  3. Code expands archetypes into a synthetic population using parametric variation.
  4. Evaluation compares the synthetic population against config's real distributions.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CountryConfig:
    """
    All country-specific ground-truth data in one place.

    Sections
    ────────
    Identity          → iso3, name, capital, geography
    Demographics      → age distribution, nationality mix
    Economy           → GDP, Gini, sector breakdown
    Wages             → median salary, minimum wage, by-sector breakdown
    Income dist.      → income bracket proportions (for population synthesis)
    Housing           → rent/purchase ranges, residency rules
    Governance        → World Bank WGI percentiles
    Culture           → Inglehart-Welzel, WVS trust, cultural notes
    Social capital    → Putnam bonding/bridging by group
    Situation         → current stresses, active policies
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    iso3: str
    name: str
    capital: str
    area_km2: float
    population: int
    languages: list[str]
    currency: str

    # ── Demographic distributions (real data — used for validation) ───────────
    # Source varies by country; stored as proportions that sum to 1.0.

    age_distribution: dict[str, float]
    # Format: {age_group_label: proportion}
    # e.g. {"0-14": 0.152, "15-24": 0.137, ...}
    # Source: WorldPop / UN WPP 2022 / national census

    nationality_distribution: dict[str, float]
    # Format: {nationality_label: proportion}
    # Source: national statistics office

    foreign_born_share_pct: float
    median_age: float
    working_age_pct: float  # 15–64 as % of total

    # — Household structure (PLACEHOLDER - replace with EPF/SAIG 2023 + Registre Civil data)
    household_type_distribution: dict[str, float]
    # Format: {household_type: proportion}, must sum to 1.0
    # Categories: couple_with_children, couple_no_children, single_with_children, single_no_children

    children_distribution: dict[str, float]
    # Format: {"0": proportion, "1": proportion, "2": proportion, "3+": proportion}

    marital_rate: float
    # Overall proportion of adults currently married. Source: Registre Civil d'Andorra (TODO)

    # ── Economic indicators ───────────────────────────────────────────────────
    gdp_per_capita_ppp: int      # current int'l $
    gdp_growth_pct: float
    gini: float                  # 0–100
    unemployment_pct: float
    inflation_pct: float
    main_sectors: dict[str, float]   # {sector label: GDP share 0–1}
    tax_notes: str
    tourism_notes: str

    # ── Wage data (real data — used for world context and validation) ──────────
    currency_symbol: str
    minimum_wage_monthly: int        # gross, in local currency
    median_salary_monthly: int       # gross, median across all workers
    median_salary_by_sector: dict[str, int]
    # Format: {sector: gross monthly salary}
    # Source: national labour statistics / social insurance records

    # ── Income distribution (real data — used for population synthesis) ───────
    income_distribution: dict[str, float]
    # Format: {income_bracket_label: proportion of workforce}
    # Brackets must match the labels used in population/synthesizer.py
    # Source: tax authority / social insurance data
    # Note: "precarious" = below minimum wage or informal; "wealthy" = top few %

    # ── Housing ───────────────────────────────────────────────────────────────
    rent_range: tuple[int, int]           # monthly (min, max) in local currency
    purchase_price_m2: tuple[int, int]    # (min, max) per m²
    naturalisation_years: int | None      # None = standard process

    # ── Governance (World Bank WGI 2022 — percentiles 0–100) ─────────────────
    wgi: dict[str, int]

    # ── Culture ───────────────────────────────────────────────────────────────
    inglehart_welzel: tuple[float, float]  # (secular_rational, self_expression) 0–1
    inglehart_source: str
    wvs_trust: float                       # generalised trust 0–1
    wvs_source: str
    cultural_notes: str

    # ── Social capital ────────────────────────────────────────────────────────
    social_capital_by_group: dict[str, str]

    # ── Current situation ─────────────────────────────────────────────────────
    current_stresses: list[str]
    active_policies: list[str]

    # ── Derived ───────────────────────────────────────────────────────────────

    def world_context(self) -> str:
        """
        Build the LLM world context string from structured config fields.
        Cached as the system prompt for all agent generation calls.
        """
        lines = [
            f"=== WORLD CONTEXT: {self.name.upper()} ({self.iso3}) ===",
            "",
            "── GEOGRAPHY AND SCALE",
            f"Country/territory: {self.name}. Capital: {self.capital}.",
            f"Area: {self.area_km2:,.1f} km². Languages: {', '.join(self.languages)}.",
            f"Currency: {self.currency}.",
            "",
            "── DEMOGRAPHY",
            f"Estimated population: ~{self.population:,}.",
            f"Foreign-born share: {self.foreign_born_share_pct:.0f}%.",
            f"Median age: {self.median_age} years. Working-age (15–64): {self.working_age_pct:.0f}%.",
            "Age distribution:",
        ]
        for group, share in self.age_distribution.items():
            lines.append(f"  {group}: {share*100:.1f}%")

        lines += ["", "Nationality composition:"]
        for label, share in sorted(self.nationality_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"  {label}: {share*100:.1f}%")
        lines += ["", "Household composition:"]
        for label, share in sorted(self.household_type_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"  {label}: {share*100:.1f}%")
        lines.append(f"Overall marital rate: {self.marital_rate*100:.1f}% of adults currently married.")
        lines += ["", "Children per household:"]
        for label, share in sorted(self.children_distribution.items()):
            lines.append(f"  {label} children: {share*100:.1f}%")

        lines += [
            "",
            "── ECONOMY",
            f"GDP per capita (PPP): {self.currency_symbol}{self.gdp_per_capita_ppp:,} (current int'l $).",
            f"GDP growth: {self.gdp_growth_pct:+.1f}%. Gini: {self.gini:.1f}.",
            f"Unemployment: {self.unemployment_pct:.1f}%. Inflation: {self.inflation_pct:.1f}%.",
            "Main sectors (GDP share):",
        ]
        for sector, share in self.main_sectors.items():
            lines.append(f"  {sector}: {share*100:.0f}%")
        lines += [f"Tax regime: {self.tax_notes}", f"Tourism: {self.tourism_notes}"]

        lines += [
            "",
            "── WAGES AND INCOME",
            f"Minimum wage: {self.currency_symbol}{self.minimum_wage_monthly:,}/month (gross).",
            f"Median salary (all workers): {self.currency_symbol}{self.median_salary_monthly:,}/month (gross).",
            "Median salary by sector (gross monthly):",
        ]
        for sector, salary in self.median_salary_by_sector.items():
            lines.append(f"  {sector}: {self.currency_symbol}{salary:,}")

        lines += ["", "Income distribution of the workforce:"]
        for bracket, share in self.income_distribution.items():
            lines.append(f"  {bracket}: {share*100:.1f}%")

        lines += [
            "",
            "── HOUSING AND COST OF LIVING",
            f"Monthly rent: {self.currency_symbol}{self.rent_range[0]:,}–{self.currency_symbol}{self.rent_range[1]:,}.",
            f"Purchase price: {self.currency_symbol}{self.purchase_price_m2[0]:,}–"
            f"{self.currency_symbol}{self.purchase_price_m2[1]:,}/m².",
        ]
        if self.naturalisation_years:
            lines.append(
                f"Naturalisation: {self.naturalisation_years} years legal residence required. "
                "Creates long-horizon precarity for immigrant cohorts."
            )

        lines += ["", "── GOVERNANCE (World Bank WGI)"]
        for indicator, pct in self.wgi.items():
            lines.append(f"  {indicator}: {pct}th global percentile")

        lines += [
            "",
            "── CULTURAL POSITIONING",
            f"Inglehart-Welzel: secular_rational={self.inglehart_welzel[0]:.2f}, "
            f"self_expression={self.inglehart_welzel[1]:.2f}.",
            f"Source: {self.inglehart_source}",
            f"Generalised interpersonal trust (WVS): {self.wvs_trust:.2f}. Source: {self.wvs_source}",
            self.cultural_notes,
            "",
            "── SOCIAL CAPITAL (Putnam framework)",
        ]
        for group, desc in self.social_capital_by_group.items():
            lines.append(f"  {group}: {desc}")

        lines += ["", "── CURRENT STRUCTURAL STRESSES"]
        for i, s in enumerate(self.current_stresses, 1):
            lines.append(f"  {i}. {s}")

        lines += ["", "── ACTIVE POLICY DEBATES"]
        for i, p in enumerate(self.active_policies, 1):
            lines.append(f"  {i}. {p}")

        lines += [
            "",
            "── AGENT GENERATION INSTRUCTIONS",
            "Generate a preference profile that is:",
            "(a) Internally consistent: Big Five traits must cohere with Schwartz values and",
            "    behavioral economics parameters (high Neuroticism → higher loss_aversion;",
            "    high Conscientiousness → lower discount_rate; high Agreeableness → higher trust).",
            "(b) Sociologically grounded: reflect the structural position of this person in the",
            "    society above — their access to resources, institutional power, and cultural capital.",
            "(c) Empirically calibrated: Big Five scores approximate population norms",
            "    (mean ≈ 0.50, SD ≈ 0.12–0.15). Do not compress variance toward the mean.",
            "(d) Contextually specific: this agent lives here, not a generic city. Fears, goals,",
            "    and political positions must reflect the local realities described above.",
        ]
        return "\n".join(lines)


# ── Andorra ────────────────────────────────────────────────────────────────────
# Sources:
#   Estadística d'Andorra (SAIG) — Anuari Estadístic 2023
#   CASS (Caixa Andorrana de Seguretat Social) — labour and wage statistics 2022–2023
#   IMF 2024 Article IV Consultation — Staff Report for Andorra
#   UN World Population Prospects 2022, Medium Variant
#   World Bank Governance Indicators 2022
#   EVS Wave 5 (2017–2021) — Spain/France used as cultural proxies

ANDORRA = CountryConfig(
    iso3="AND",
    name="Andorra",
    capital="Andorra la Vella",
    area_km2=467.6,
    population=90000,
    languages=["Catalan", "Spanish", "French", "Portuguese"],
    currency="EUR",
    currency_symbol="€",

    # ── Age distribution ──────────────────────────────────────────────────────
    # Source: UN WPP 2022, Andorra country file. Cross-checked against SAIG 2023.
    # Working-age-heavy profile reflects immigrant labour structure (55% foreign-born).
    age_distribution={
        "0–14":  0.152,   # children and early adolescents
        "15–24": 0.137,   # youth (school + early labour market)
        "25–39": 0.254,   # prime working age (largest immigrant cohort)
        "40–54": 0.243,   # established working age
        "55–64": 0.108,   # pre-retirement
        "65+":   0.106,   # retired (growing Andorran elder cohort)
    },

    # ── Nationality distribution ───────────────────────────────────────────────
    # Source: SAIG Anuari Estadístic 2023 (registered residents)
    nationality_distribution={
        "Andorran":   0.356,
        "Spanish":    0.335,
        "Portuguese": 0.171,
        "French":     0.066,
        "Other":      0.072,
    },
    foreign_born_share_pct=55.0,
    median_age=38.4,
    working_age_pct=67.2,

    # ── Economy ───────────────────────────────────────────────────────────────
    # Source: IMF 2024 Article IV; SAIG Anuari 2023
    gdp_per_capita_ppp=49900,
    gdp_growth_pct=2.1,
    gini=27.0,
    unemployment_pct=2.0,
    inflation_pct=5.1,
    main_sectors={
        "Tourism & hospitality": 0.30,
        "Retail & commerce":     0.25,
        "Finance":               0.15,
        "Real estate":           0.12,
        "Public administration": 0.10,
        "Construction":          0.05,
        "Other":                 0.03,
    },
    tax_notes=(
        "No personal income tax. VAT capped at 4.5%. Corporate tax 10%. "
        "Creates a consumption/retail economy and significant cross-border shopping tourism."
    ),
    tourism_notes=(
        "~8–10 million visitors/year vs ~90,000 residents (ratio ≈ 100:1). "
        "Largest economic engine and primary quality-of-life stressor simultaneously."
    ),

    # ── Wages ─────────────────────────────────────────────────────────────────
    # Source: CASS (Caixa Andorrana de Seguretat Social) wage statistics 2022–2023;
    #         AEA (Associació d'Empresaris d'Andorra) sector surveys.
    # Note: all figures are GROSS monthly salary in EUR.
    # Minimum wage 2024: SMI d'Andorra = €1,376.88/month.
    minimum_wage_monthly=1377,
    median_salary_monthly=2050,
    median_salary_by_sector={
        "Retail & commerce":     1600,
        "Hospitality & tourism": 1550,
        "Construction":          1650,
        "Domestic & cleaning":   1400,
        "Finance":               3200,
        "Public administration": 2100,
        "Education":             2000,
        "Real estate":           2000,
        "Healthcare":            2400,
    },

    # ── Income distribution ───────────────────────────────────────────────────
    # Source: CASS 2022 contribution data (proxy for wage distribution);
    #         SAIG Enquesta sobre condicions de vida 2022.
    # Brackets align with population/synthesizer.py income_bracket labels.
    # "Precarious" includes informal workers and those below minimum wage.
    income_distribution={
        "precarious":    0.12,   # < €1,000/month net
        "low":           0.15,   # €1,000–€1,300 net
        "lower_middle":  0.27,   # €1,300–€1,800 net
        "middle":        0.22,   # €1,800–€2,500 net
        "upper_middle":  0.13,   # €2,500–€3,500 net
        "comfortable":   0.08,   # €3,500–€6,000 net
        "wealthy":       0.03,   # > €6,000 net
    },

    # ── Housing ───────────────────────────────────────────────────────────────
    # Source: SAIG Anuari 2021; real estate portals (Habitatge.ad) 2023–2024.
    rent_range=(900, 1800),
    purchase_price_m2=(2500, 5500),
    naturalisation_years=20,
    # — Household structure (PLACEHOLDER - replace with EPF/SAIG 2023 + Registre Civil data)
    household_type_distribution={
        "couple_with_children": 0.25,
        "couple_no_children": 0.25,
        "single_with_children": 0.10,
        "single_no_children": 0.40,
    },
    children_distribution={
        "0": 0.55,
        "1": 0.25,
        "2": 0.15,
        "3+": 0.05,
    },
    marital_rate=0.45,

    # ── Governance ────────────────────────────────────────────────────────────
    # Source: World Bank WGI 2022 (wgi.worldbank.org)
    wgi={
        "Rule of Law":             85,
        "Government Effectiveness":88,
        "Control of Corruption":   82,
        "Political Stability":     91,
        "Regulatory Quality":      80,
        "Voice & Accountability":  83,
    },

    # ── Culture ───────────────────────────────────────────────────────────────
    # Andorra has no own WVS datapoint. Position interpolated from
    # Spain (0.82, 0.71) and France (1.12, 0.89) on the WVS 2023 cultural map.
    inglehart_welzel=(0.95, 0.78),
    inglehart_source="Interpolated from Spain/France (WVS 2023); Andorra not in WVS sample",
    wvs_trust=0.44,
    wvs_source="WVS Wave 7 Western Europe average (Spain/France proxy)",
    cultural_notes=(
        "Catalan national identity coexists with multilingualism and cosmopolitan outlook. "
        "Historical neutrality and co-principality create pragmatic, consensus-oriented politics. "
        "Immigrant communities (esp. Portuguese) maintain origin-country cultural values for "
        "5–8 years before gradual adaptation (Berry 1997 acculturation model). "
        "Tax-haven reputation shapes attitudes to wealth, privacy, and state redistribution."
    ),

    # ── Social capital ────────────────────────────────────────────────────────
    social_capital_by_group={
        "Andorran nationals":
            "High bonding capital (dense family/community networks). Moderate bridging "
            "via comú governance and local associations.",
        "Long-term immigrants (8+ years)":
            "Moderate bonding within ethnic community. Low-moderate bridging to host society. "
            "Limited civic participation due to non-citizen status.",
        "Recent immigrants (<4 years)":
            "High bonding within migration network. Very low bridging. "
            "Spatial knowledge limited to work-home corridor.",
    },

    # ── Current situation ─────────────────────────────────────────────────────
    current_stresses=[
        "Housing affordability crisis: rents consuming 50–70% of net income for working-class "
        "immigrants. No rent control mechanism, limited social housing stock (CASS 2022).",
        "Tourism saturation: ~100 visitors/resident ratio generating quality-of-life backlash.",
        "Climate risk to ski economy: IPCC AR6 projects Pyrenean snowline rising 200–400m by "
        "2050 under RCP4.5; 3 of 7 ski areas face structural viability risk.",
        "Demographic dependency: ageing Andorran cohort, structural reliance on immigrant "
        "labour with no citizenship pathway below the 20-year threshold.",
        "Cross-border labour competition: wage premium eroding relative to Barcelona/Toulouse.",
    ],
    active_policies=[
        "Housing regulation debate: proposed rent caps and social housing expansion (parliament 2025).",
        "Tourism volume management: environmental impact assessment for peak-season caps.",
        "Labour law reform: improving protections for temporary and seasonal workers.",
        "Climate adaptation: investment in non-ski tourism diversification.",
        "EU alignment process: partial convergence with EU regulatory standards (ongoing).",
    ],
)


# ── Active configuration ───────────────────────────────────────────────────────
# Change this one line to switch countries. Nothing else needs to change.
ACTIVE_CONFIG: CountryConfig = ANDORRA


# ── Module-level exports ───────────────────────────────────────────────────────
# Experiments and pipeline modules import these names.
ANDORRA_WORLD_CONTEXT = ACTIVE_CONFIG.world_context()
