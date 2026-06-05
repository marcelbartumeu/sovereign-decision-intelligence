"""
World Bank Open Data API — institutional and economic context layer.

Provides country-level governance, economic, and social indicators that form
the "metaphysical" or institutional layer: rule of law, government effectiveness,
economic inequality, health outcomes, education attainment, etc.

This is what makes Boston different from Madagascar at the macro level —
not just what buildings exist, but what institutions operate, what rights people
have, what economic constraints they face.

API documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
Base URL: https://api.worldbank.org/v2/
No authentication required.

Key indicator families used:
  WGI  — Worldwide Governance Indicators (governance quality)
  WDI  — World Development Indicators (economic, social, health)
"""

from __future__ import annotations
import requests
from dataclasses import dataclass, field

WB_BASE = "https://api.worldbank.org/v2"

# Indicators fetched for each AOI country
# Format: {indicator_code: (label, description)}
INDICATORS: dict[str, tuple[str, str]] = {
    # Governance (WGI)
    "RL.EST":   ("rule_of_law",           "Rule of Law estimate (WGI, −2.5 to +2.5)"),
    "GE.EST":   ("govt_effectiveness",    "Government Effectiveness estimate (WGI)"),
    "CC.EST":   ("control_corruption",    "Control of Corruption estimate (WGI)"),
    "PS.EST":   ("political_stability",   "Political Stability estimate (WGI)"),
    "VA.EST":   ("voice_accountability",  "Voice & Accountability estimate (WGI)"),
    # Economic (WDI)
    "NY.GDP.PCAP.PP.CD": ("gdp_per_capita_ppp", "GDP per capita, PPP (current int'l $)"),
    "SI.POV.GINI":       ("gini",               "Gini coefficient (0–100)"),
    "SL.UEM.TOTL.ZS":    ("unemployment_rate",  "Unemployment, total (% of labour force)"),
    "FP.CPI.TOTL.ZG":    ("inflation_rate",     "Inflation, consumer prices (annual %)"),
    # Social
    "SP.DYN.LE00.IN":    ("life_expectancy",    "Life expectancy at birth, total (years)"),
    "SE.ADT.LITR.ZS":    ("literacy_rate",      "Literacy rate, adult total (% 15+)"),
    "SP.URB.TOTL.IN.ZS": ("urbanisation_rate",  "Urban population (% of total)"),
    "SH.XPD.CHEX.GD.ZS": ("health_expenditure","Current health expenditure (% of GDP)"),
}


@dataclass
class InstitutionalProfile:
    """Country-level institutional and economic indicators."""
    iso3: str
    indicators: dict[str, float | None] = field(default_factory=dict)
    year: int = 2022

    def get(self, key: str, default: float | None = None) -> float | None:
        return self.indicators.get(key, default)

    def governance_summary(self) -> str:
        """Human-readable governance quality summary for LLM context."""
        rl  = self.get("rule_of_law")
        ge  = self.get("govt_effectiveness")
        cc  = self.get("control_corruption")
        ps  = self.get("political_stability")

        def pct(v):
            if v is None: return "N/A"
            # WGI estimates range −2.5 to +2.5; map to percentile approx
            pct_val = min(99, max(1, int((v + 2.5) / 5.0 * 100)))
            return f"{pct_val}th percentile"

        return (
            f"Governance (World Bank WGI {self.year}): "
            f"Rule of Law {pct(rl)}, "
            f"Government Effectiveness {pct(ge)}, "
            f"Control of Corruption {pct(cc)}, "
            f"Political Stability {pct(ps)}"
        )

    def economic_summary(self) -> str:
        gdp   = self.get("gdp_per_capita_ppp")
        gini  = self.get("gini")
        unem  = self.get("unemployment_rate")
        le    = self.get("life_expectancy")
        urban = self.get("urbanisation_rate")

        parts = []
        if gdp:   parts.append(f"GDP/capita (PPP): ${gdp:,.0f}")
        if gini:  parts.append(f"Gini: {gini:.1f}")
        if unem:  parts.append(f"Unemployment: {unem:.1f}%")
        if le:    parts.append(f"Life expectancy: {le:.1f} yrs")
        if urban: parts.append(f"Urbanisation: {urban:.0f}%")
        return f"Economic profile ({self.year}): " + " | ".join(parts)

    def to_context_string(self) -> str:
        return f"{self.governance_summary()}\n{self.economic_summary()}"


class WorldBankClient:
    """
    World Bank Open Data REST API client.
    Fetches the most recent available value for each indicator.
    """

    def __init__(self, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self.timeout = timeout

    def _fetch_indicator(self, iso3: str, indicator: str) -> float | None:
        url = f"{WB_BASE}/country/{iso3}/indicator/{indicator}"
        params = {
            "format": "json",
            "mrv": 5,          # most recent 5 values (in case latest is missing)
            "per_page": 5,
        }
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return None
            for entry in data[1]:
                if entry.get("value") is not None:
                    return float(entry["value"])
        except Exception:
            pass
        return None

    def fetch_profile(self, iso3: str) -> InstitutionalProfile:
        """
        Fetch all configured indicators for a country.
        Returns InstitutionalProfile with the most recent available values.
        """
        print(f"  Fetching World Bank indicators for {iso3}...")
        values: dict[str, float | None] = {}
        for code, (label, _) in INDICATORS.items():
            values[label] = self._fetch_indicator(iso3, code)

        return InstitutionalProfile(iso3=iso3, indicators=values)


# ── Fallback profiles for countries where API returns sparse data ─────────────

ANDORRA_FALLBACK = InstitutionalProfile(
    iso3="AND",
    year=2022,
    indicators={
        # World Bank WGI 2022 — Andorra estimates (mapped from percentile to raw score)
        "rule_of_law":          1.35,   # ~85th percentile
        "govt_effectiveness":   1.48,   # ~88th percentile
        "control_corruption":   1.22,   # ~82nd percentile
        "political_stability":  1.58,   # ~91st percentile
        "voice_accountability": 1.18,   # ~83rd percentile
        # IMF 2024 Article IV — Andorra
        "gdp_per_capita_ppp":   49900.0,
        "gini":                 27.0,
        "unemployment_rate":    2.0,
        "inflation_rate":       5.1,    # 2023 HICP estimate
        # WHO / UNDP 2023
        "life_expectancy":      83.9,
        "urbanisation_rate":    88.0,
        "health_expenditure":   6.8,
    }
)

FALLBACK_PROFILES: dict[str, InstitutionalProfile] = {
    "AND": ANDORRA_FALLBACK,
}


def get_profile(iso3: str, use_api: bool = True) -> InstitutionalProfile:
    """
    Get institutional profile for a country.
    Falls back to embedded estimates if API is unavailable or returns sparse data.
    """
    if use_api:
        client = WorldBankClient()
        profile = client.fetch_profile(iso3)
        filled = sum(1 for v in profile.indicators.values() if v is not None)
        if filled >= 5:
            return profile
    return FALLBACK_PROFILES.get(iso3, WorldBankClient().fetch_profile(iso3))
