"""
Destination choice model: gravity model over H3 cells.

Theoretical basis: spatial interaction / gravity model (Wilson 1969; Fotheringham
& O'Kelly 1989). Each destination j has an attractiveness A(j, activity) and
a distance impedance f(d_ij, mode). The choice probability is:

    P(dest=j) ∝ A(j, activity) × exp(-β × d_km)

where β is the distance decay parameter from config.py (activity-specific).

Bridging capital modifies β: low bridging → steeper decay (smaller spatial range).
Source: Putnam (2000). Operationalised per config.BRIDGING_DECAY_COEFF.

H3 grid data
────────────
The model is initialised once with the H3 grid loaded from the project's
accessibility_population.geojson. Each cell contributes:
  - population  : normalised density (proxy for general attractiveness)
  - accessibility: "bus/car" | "walk" | "bike" | None → transit_coverage flag
  - centroid    : (lat, lon) computed from H3 cell polygon centroid

Attractiveness by activity type
────────────────────────────────
We do not have separate commercial / employment density layers for Andorra at H3
resolution. Instead, we use population density as a universal attractiveness proxy
and modulate it by accessibility type:

  work             → pop × 1.0  (employment follows population in small integrated economy)
  grocery          → pop × 1.2  bus/car accessible (food retail in transit-served zones)
  shopping         → pop × 1.1  bus/car accessible (non-grocery retail)
  education        → pop × 1.0  (schools/colleges distributed with population)
  leisure_indoor   → pop × 0.8  (disperses away from dense cores; entertainment zones)
  leisure_outdoor  → pop × 0.3  bus/car (outdoor areas inversely correlated with density)
  healthcare       → pop × 1.0  (GP/pharmacy co-locate with residential population)
  civic            → pop × 1.0  (civic facilities track population)

This is an explicit proxy assumption, flagged for replacement when commercial-zone
or employment-zone GeoJSON becomes available.
"""

import json
import math
from pathlib import Path
import numpy as np

from .config import DIST_DECAY, BRIDGING_DECAY_COEFF, PLACE_PREF_BETA_COEFF
from ._place_bridge import activity_affinity_ratio

# Path to the H3 grid file relative to this module's location.
# The file lives in the main app's public/model/ directory.
_GEOJSON_PATH = (
    Path(__file__).parents[3]
    / "app" / "public" / "model"
    / "accessibility_population.geojson"
)

# Attractiveness multipliers per activity × accessibility type.
# See module docstring for rationale.
_ATTRACT_MULT: dict[str, dict[str, float]] = {
    "work":            {"bus/car": 1.0, "walk": 0.8, "bike": 0.9, None: 0.6},
    "grocery":         {"bus/car": 1.2, "walk": 1.0, "bike": 0.9, None: 0.5},
    "shopping":        {"bus/car": 1.1, "walk": 0.9, "bike": 0.9, None: 0.4},
    "education":       {"bus/car": 1.0, "walk": 0.8, "bike": 1.0, None: 0.5},
    "leisure_indoor":  {"bus/car": 0.7, "walk": 1.0, "bike": 1.1, None: 0.8},
    "leisure_outdoor": {"bus/car": 0.4, "walk": 0.7, "bike": 0.9, None: 1.2},
    "healthcare":      {"bus/car": 1.0, "walk": 1.0, "bike": 0.9, None: 0.5},
    "civic":           {"bus/car": 1.0, "walk": 0.9, "bike": 0.9, None: 0.6},
}


def _centroid(geometry: dict) -> tuple[float, float]:
    """Compute (lat, lon) centroid of a GeoJSON Polygon."""
    coords = geometry["coordinates"][0]   # outer ring
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


class H3Grid:
    """
    Pre-loaded H3 grid with attractiveness and spatial index.
    Initialised once and shared across all agents.
    """

    def __init__(self, geojson_path: Path = _GEOJSON_PATH):
        with open(geojson_path) as f:
            data = json.load(f)

        self.cells: list[dict] = []   # list of cell dicts with precomputed fields

        pop_vals = []
        for feat in data["features"]:
            p = feat["properties"]
            pop = p.get("population")
            if pop is None or pop <= 0:
                continue
            lat, lon = _centroid(feat["geometry"])
            self.cells.append({
                "h3":          p["h3_cell"],
                "lat":         lat,
                "lon":         lon,
                "pop":         float(pop),
                "access":      p.get("accessibility"),   # "bus/car"|"walk"|"bike"|None
            })
            pop_vals.append(float(pop))

        # Normalise population to [0, 1] for attractiveness computation.
        max_pop = max(pop_vals) if pop_vals else 1.0
        for c in self.cells:
            c["pop_norm"] = c["pop"] / max_pop

    def attractiveness(self, cell: dict, activity: str) -> float:
        mult = _ATTRACT_MULT.get(activity, {}).get(cell["access"], 0.7)
        return cell["pop_norm"] * mult

    def choose_destination(
        self,
        origin_h3: str,
        activity: str,
        bridging_capital: float,
        rng: np.random.Generator,
        n_candidates: int = 200,
        place_preferences: dict | None = None,
        beta_mult: float = 1.0,
    ) -> str:
        """
        Sample a destination H3 cell for the given activity.

        For efficiency, we pre-filter to n_candidates cells with non-zero
        attractiveness, compute gravity weights, and sample from those.
        Pre-filtering uses attractiveness alone (no distance); the distance
        decay is applied in the weight computation.

        Parameters
        ──────────
        origin_h3          : H3 cell of the agent's current location
        activity           : one of the 8 activity types from ACTIVITY_LAYER_MAP
        bridging_capital   : from profile — modifies distance decay β (Putnam 2000)
        rng                : seeded numpy Generator
        n_candidates       : candidate pool size before gravity weighting
        place_preferences  : optional dict layer_id → probability from RUM;
                             higher affinity → lower effective β (wider spatial reach)
        """
        # Find origin cell centroid
        origin_cell = next((c for c in self.cells if c["h3"] == origin_h3), None)
        if origin_cell is None:
            # Origin not in grid — fall back to random cell
            return rng.choice([c["h3"] for c in self.cells])

        o_lat, o_lon = origin_cell["lat"], origin_cell["lon"]

        # Distance decay β, modified by bridging capital (Putnam 2000)
        beta_base = DIST_DECAY[activity].value
        beta = beta_base * (1 + BRIDGING_DECAY_COEFF.value * (0.5 - bridging_capital))

        # Place preference → willingness to travel farther (Ben-Akiva & Lerman 1985)
        # affinity_ratio > 1 → agent has stronger-than-average preference for this
        # activity type → willing to travel farther → softer decay (lower β).
        if place_preferences:
            ratio = activity_affinity_ratio(place_preferences, activity)
            beta *= (1.0 - PLACE_PREF_BETA_COEFF.value * (ratio - 1.0))

        # Parenthood effect (Macedo et al. 2026): parents of young children have a
        # tighter radius of action → higher distance decay. beta_mult > 1 tightens.
        beta *= beta_mult

        beta = max(beta, 0.05)   # prevent degenerate flat distribution

        # Compute gravity weights for all cells (or sampled candidates)
        candidates = self.cells
        if len(candidates) > n_candidates:
            # Pre-sample by attractiveness to reduce compute
            attract = np.array([self.attractiveness(c, activity) for c in candidates])
            attract_sum = attract.sum()
            if attract_sum > 0:
                probs = attract / attract_sum
                idxs = rng.choice(len(candidates), size=n_candidates, replace=False, p=probs)
                candidates = [candidates[i] for i in idxs]

        weights = []
        for c in candidates:
            if c["h3"] == origin_h3:
                weights.append(0.0)   # no stay-at-origin trips
                continue
            d = _haversine_km(o_lat, o_lon, c["lat"], c["lon"])
            a = self.attractiveness(c, activity)
            w = a * math.exp(-beta * d)
            weights.append(w)

        weights_arr = np.array(weights, dtype=float)
        total = weights_arr.sum()
        if total <= 0:
            return rng.choice([c["h3"] for c in candidates])

        probs = weights_arr / total
        chosen_idx = int(rng.choice(len(candidates), p=probs))
        return candidates[chosen_idx]["h3"]

    def transit_coverage(self, h3_cell: str) -> bool:
        """Return True if the cell has bus/car accessibility."""
        cell = next((c for c in self.cells if c["h3"] == h3_cell), None)
        if cell is None:
            return False
        return cell["access"] == "bus/car"

    def distance_km(self, h3_a: str, h3_b: str) -> float:
        """Haversine distance between two H3 cell centroids."""
        ca = next((c for c in self.cells if c["h3"] == h3_a), None)
        cb = next((c for c in self.cells if c["h3"] == h3_b), None)
        if ca is None or cb is None:
            return 5.0   # fallback if cell not found
        return _haversine_km(ca["lat"], ca["lon"], cb["lat"], cb["lon"])

    def home_cell(
        self,
        nationality: str,
        income_bracket: str,
        rng: np.random.Generator,
        housing_prefs: dict | None = None,
    ) -> str:
        """
        Assign a single home H3 cell using a three-layer weighting hierarchy:

          1. Population density (base attractiveness)
          2. Nationality spatial prior (census residential patterns, Govern d'Andorra 2023)
          3. Income-tier housing preference (D10–D13 via income_bracket proxy)
          4. Housing D-layer preference deviation from base rate (if available)
             Uses D11 (senior accessibility), D12 (affordable periphery), D13 (executive
             central) deviations from their population base rates to fine-tune placement.

        Connects housing D-layers in agent place_preferences to actual home assignment.
        Source for spatial priors: Govern d'Andorra census 2023 (qualitative pattern).
        No H3-level residential microdata available — proxy assumption flagged.
        """
        is_central   = [42.47 <= c["lat"] <= 42.53 for c in self.cells]
        is_accessible = [c["access"] == "bus/car"  for c in self.cells]

        # Load housing layer base rates for deviation computation
        try:
            from place_layers import LAYER_BY_ID as _LBY
            d11_ref = _LBY["D11"].base_rate()
            d12_ref = _LBY["D12"].base_rate()
            d13_ref = _LBY["D13"].base_rate()
        except Exception:
            d11_ref = d12_ref = d13_ref = 0.11

        def _weight(idx: int) -> float:
            c   = self.cells[idx]
            lat = c["lat"]
            base = c["pop_norm"]
            central    = is_central[idx]
            accessible = is_accessible[idx]

            # Nationality prior
            if nationality == "Andorran":
                base *= (2.0 if central else 0.8)
            elif nationality == "Portuguese":
                base *= (0.6 if central else 1.4)
            elif nationality == "Spanish":
                base *= (0.8 if central else 1.2)

            # Income-tier housing modifier (D10–D13 proxy)
            if income_bracket in ("comfortable", "wealthy"):
                # D13 executive: central + accessible
                base *= (1.8 if central and accessible else 0.65)
            elif income_bracket in ("precarious", "low"):
                # D12 affordable: peripheral
                base *= (0.55 if central else 1.5)
            elif income_bracket in ("upper_middle", "middle"):
                # D10 mid-career: moderate central preference
                base *= (1.2 if central else 0.9)
            # lower_middle: neutral

            # Housing D-layer deviation adjustment (fine-grain signal from RUM)
            if housing_prefs:
                d11 = housing_prefs.get("D11", d11_ref)
                d12 = housing_prefs.get("D12", d12_ref)
                d13 = housing_prefs.get("D13", d13_ref)

                if d11 > d11_ref and accessible:      # above-avg senior pref → accessible
                    base *= 1.0 + min((d11 - d11_ref) / d11_ref, 1.0) * 0.4
                if d12 > d12_ref and not central:      # above-avg affordable pref → peripheral
                    base *= 1.0 + min((d12 - d12_ref) / d12_ref, 1.0) * 0.4
                if d13 > d13_ref and central and accessible:  # above-avg exec pref → central
                    base *= 1.0 + min((d13 - d13_ref) / d13_ref, 1.0) * 0.4

            return base

        weights = np.array([_weight(i) for i in range(len(self.cells))], dtype=float)
        total   = weights.sum()
        if total <= 0:
            weights = np.ones(len(self.cells))
            total   = weights.sum()
        probs = weights / total
        idx   = int(rng.choice(len(self.cells), p=probs))
        return self.cells[idx]["h3"]

    def residential_cells(self, nationality: str, n: int, rng: np.random.Generator) -> list[str]:
        """Backward-compatible batch wrapper. Calls home_cell() with income_bracket='middle'."""
        return [self.home_cell(nationality, "middle", rng) for _ in range(n)]
