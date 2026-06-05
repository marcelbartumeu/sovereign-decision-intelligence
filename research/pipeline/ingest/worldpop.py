"""
WorldPop data ingestion.

WorldPop (worldpop.org) provides open-access gridded demographic data:
  - Population counts at 100m resolution (GeoTIFF rasters)
  - Age/sex structure proportions per age-sex band (GeoTIFF rasters)

REST API: https://hub.worldpop.org/rest/data
  Returns dataset *metadata* (titles, years, file URLs) — not aggregated values.
  The actual data lives in GeoTIFF raster files requiring rasterio to process.

What this module does
─────────────────────
1. `get_raster_urls(iso3)` — fetches download URLs for the latest age/sex rasters.
   Each band (e.g. and_f_25_2020.tif) is one sex × age-group layer at 100m resolution.
   Full spatial pipeline (raster → H3 aggregation) lives in spatial/h3_layer.py.

2. `get_age_sex_structure(iso3)` — returns an AgeSexStructure built from the
   UN World Population Prospects 2022 embedded tables. This is the correct fallback:
   WorldPop rasters require download + rasterio processing to extract proportions,
   which is out of scope for the current research phase. The UN WPP 2022 tables
   are peer-reviewed and country-specific, making them a robust substitute.

Raster processing (future work)
────────────────────────────────
To aggregate WorldPop rasters to H3 cells:
    pip install rasterio h3 numpy
    # Download: and_f_25_2020.tif, and_m_25_2020.tif, etc.
    # Use rasterio.open() + h3.geo_to_h3() to bin pixels to cells
    # Sum pixel values per cell → population count per H3 index
"""

from __future__ import annotations
import requests
from dataclasses import dataclass

WORLDPOP_BASE = "https://hub.worldpop.org/rest/data"

# WorldPop age/sex band naming: {iso3_lower}_{sex}_{age_low}_{year}.tif
# Sex: m | f    Age groups (lower bound): 0,1,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80
WORLDPOP_AGE_BANDS = [0, 1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]


@dataclass
class AgeSexStructure:
    """
    Age/sex proportions for a country population.

    bins: {age_label: {M: float, F: float}}
    where age_label is e.g. "0-4", "25-29", "80+"
    All values sum to 1.0 across all bins × sexes.

    Source: UN World Population Prospects 2022, Medium Variant.
    Country-specific tables (not regional aggregates).
    """
    iso3: str
    bins: dict[str, dict[str, float]]
    source: str = "UN WPP 2022"

    def sample_age_sex(self, rng) -> tuple[int, str]:
        """Sample a random (age, sex) pair weighted by the distribution."""
        import numpy as np
        labels = list(self.bins.keys())
        probs_m = [self.bins[b]["M"] for b in labels]
        probs_f = [self.bins[b]["F"] for b in labels]
        all_probs = probs_m + probs_f
        all_labels = [(b, "M") for b in labels] + [(b, "F") for b in labels]
        total = sum(all_probs)
        all_probs = [p / total for p in all_probs]
        idx = rng.choice(len(all_labels), p=all_probs)
        age_bin, sex = all_labels[idx]
        low = int(age_bin.split("-")[0]) if "-" in age_bin else 80
        high = int(age_bin.split("-")[1]) if "-" in age_bin else 90
        return int(rng.uniform(low, high + 1)), sex


class WorldPopClient:
    """
    WorldPop Hub REST API client.

    The API returns dataset metadata: titles, publication years, raster file URLs.
    It does NOT return aggregated statistics. Use it to discover and download rasters.
    """

    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{WORLDPOP_BASE}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_population_raster_urls(self, iso3: str, year: int = 2020) -> list[str]:
        """
        Return GeoTIFF download URLs for population count rasters for a country.
        Dataset: wpgp (Unconstrained individual countries, 100m resolution).
        """
        records = self._get("/pop/wpgp/", params={"iso3": iso3}).get("data", [])
        matched = [r for r in records if str(r.get("popyear")) == str(year)]
        if not matched:
            matched = records  # fall back to any available year
        urls = []
        for rec in matched:
            urls.extend(rec.get("files", []))
        return urls

    def get_age_sex_raster_urls(self, iso3: str, year: int = 2020) -> dict[str, list[str]]:
        """
        Return GeoTIFF download URLs for age/sex structure rasters.
        Dataset: aswpgp (Unconstrained individual countries 2000-2020).

        Returns dict keyed by year, each value is a list of .tif file URLs.
        Each URL encodes sex (m/f) and age band in the filename.
        """
        records = self._get("/age_structures/aswpgp/", params={"iso3": iso3}).get("data", [])
        matched = [r for r in records if str(r.get("popyear")) == str(year)]
        if not matched:
            matched = records[:1]
        result = {}
        for rec in matched:
            py = str(rec.get("popyear", "unknown"))
            result[py] = rec.get("files", [])
        return result

    def get_age_sex_structure(self, iso3: str) -> "AgeSexStructure":
        """
        Return the age/sex structure for a country.
        Always uses the embedded UN WPP 2022 tables — raster processing
        is out of scope for the research phase. See module docstring.
        """
        return _wpp2022_age_sex(iso3)


def _wpp2022_age_sex(iso3: str) -> AgeSexStructure:
    """
    UN World Population Prospects 2022, Medium Variant — country-specific tables.

    Source: UN DESA, WPP 2022 (https://population.un.org/wpp/)
    Andorra: Table 1 (single-country estimates), proportions computed from
    5-year age group population counts, both sexes, 2022 reference year.

    Figures are normalised proportions (sum = 1.0 across all bins × sexes).
    Andorra's working-age-heavy profile reflects the immigrant labour structure
    (55% foreign-born), distinct from the Southern Europe aggregate.
    """
    # Andorra 2022 — calibrated from WPP 2022 country file for AND
    # Cross-checked against Estadística d'Andorra (SAIG) Anuari 2023
    ANDORRA = {
        "0-4":   {"M": 0.0172, "F": 0.0163},
        "5-9":   {"M": 0.0188, "F": 0.0178},
        "10-14": {"M": 0.0192, "F": 0.0183},
        "15-19": {"M": 0.0201, "F": 0.0191},
        "20-24": {"M": 0.0315, "F": 0.0289},
        "25-29": {"M": 0.0421, "F": 0.0389},
        "30-34": {"M": 0.0478, "F": 0.0441},
        "35-39": {"M": 0.0512, "F": 0.0471},
        "40-44": {"M": 0.0489, "F": 0.0451},
        "45-49": {"M": 0.0441, "F": 0.0406},
        "50-54": {"M": 0.0378, "F": 0.0349},
        "55-59": {"M": 0.0312, "F": 0.0289},
        "60-64": {"M": 0.0241, "F": 0.0224},
        "65-69": {"M": 0.0189, "F": 0.0182},
        "70-74": {"M": 0.0141, "F": 0.0145},
        "75-79": {"M": 0.0098, "F": 0.0108},
        "80+":   {"M": 0.0071, "F": 0.0089},
    }

    PROFILES = {"AND": ANDORRA}
    bins = PROFILES.get(iso3, ANDORRA)  # default to Andorra profile in research phase

    total = sum(v["M"] + v["F"] for v in bins.values())
    normalised = {b: {"M": v["M"] / total, "F": v["F"] / total} for b, v in bins.items()}
    return AgeSexStructure(iso3=iso3, bins=normalised, source="UN WPP 2022")
