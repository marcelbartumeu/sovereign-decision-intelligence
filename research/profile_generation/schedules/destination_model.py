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

  work     → pop × 1.0  (employment follows population in a small, integrated economy)
  shopping → pop × 1.2 if bus/car accessible (commercial zones are transit-served)
  leisure  → pop × 0.8  (leisure disperses away from dense cores toward parks/nature)
  civic    → pop × 1.0  (civic facilities track population)

This is an explicit proxy assumption, flagged for replacement when commercial-zone
or employment-zone GeoJSON becomes available.
"""

import json
import math
from pathlib import Path
import numpy as np

from .config import DIST_DECAY, BRIDGING_DECAY_COEFF

# Path to the H3 grid file relative to this module's location.
# The file lives in the main app's public/model/ directory.
_GEOJSON_PATH = (
    Path(__file__).parents[3]
    / "Front end" / "dashboard" / "public" / "model"
    / "accessibility_population.geojson"
)

# Attractiveness multipliers per activity × accessibility type.
# See module docstring for rationale.
_ATTRACT_MULT: dict[str, dict[str, float]] = {
    "work":     {"bus/car": 1.0, "walk": 0.8, "bike": 0.9, None: 0.6},
    "shopping": {"bus/car": 1.2, "walk": 1.0, "bike": 0.9, None: 0.4},
    "leisure":  {"bus/car": 0.7, "walk": 1.0, "bike": 1.1, None: 0.9},
    "civic":    {"bus/car": 1.0, "walk": 0.9, "bike": 0.9, None: 0.6},
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
    ) -> str:
        """
        Sample a destination H3 cell for the given activity.

        For efficiency, we pre-filter to n_candidates cells with non-zero
        attractiveness, compute gravity weights, and sample from those.
        Pre-filtering uses attractiveness alone (no distance); the distance
        decay is applied in the weight computation.

        Parameters
        ──────────
        origin_h3        : H3 cell of the agent's current location
        activity         : "work" | "shopping" | "leisure" | "civic"
        bridging_capital : from profile — modifies distance decay β
        rng              : seeded numpy Generator
        n_candidates     : candidate pool size before gravity weighting
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

    def residential_cells(self, nationality: str, n: int, rng: np.random.Generator) -> list[str]:
        """
        Sample n residential H3 cells for agents of a given nationality.

        Residential distribution prior by nationality
        ─────────────────────────────────────────────
        Andorran   → centre parishes (Andorra la Vella, Escaldes): lat 42.48–42.52
        Portuguese → outer parishes (Sant Julià, Encamp): lat outside centre band
        Spanish    → mixed, slight outer bias (many are cross-border, but residents
                     concentrate in lower-cost outer parishes)
        French     → no strong spatial prior; use population density only
        Other      → population density only

        Source: Govern d'Andorra census 2023 (qualitative residential pattern).
        No H3-level residential microdata available — proxy assumption flagged.
        """
        def _weight(c: dict) -> float:
            base = c["pop_norm"]
            lat  = c["lat"]
            if nationality == "Andorran":
                # Central parishes: 42.48–42.52 lat band
                return base * (2.0 if 42.48 <= lat <= 42.52 else 0.8)
            elif nationality == "Portuguese":
                return base * (0.6 if 42.48 <= lat <= 42.52 else 1.4)
            elif nationality == "Spanish":
                return base * (0.8 if 42.48 <= lat <= 42.52 else 1.2)
            else:
                return base

        weights = np.array([_weight(c) for c in self.cells])
        total = weights.sum()
        if total <= 0:
            weights = np.ones(len(self.cells))
            total   = weights.sum()
        probs = weights / total
        idxs  = rng.choice(len(self.cells), size=n, replace=True, p=probs)
        return [self.cells[i]["h3"] for i in idxs]
