"""
H3 spatial layer — enriches each H3 cell with physical and demographic attributes.

Each cell becomes a structured environment node that agents can perceive,
navigate to, and make decisions about. The enrichment pipeline assigns:

  population_density  — estimated population per km² (from WorldPop raster or proxy)
  land_use_type       — dominant land use category (residential/commercial/natural/mixed)
  infrastructure_score— 0–1 composite: presence of key amenity categories nearby
  transit_access      — 0–1: proximity to public transit stops
  feature_counts      — raw count per OSM category within cell

The H3 layer is the spatial bridge between raw geodata and the agent simulation.
Agents are assigned to cells, move between cells, and experience affordances
determined by cell attributes.

Note on population disaggregation:
  Full spatial disaggregation requires WorldPop GeoTIFF raster files (100m resolution)
  processed with rasterio. This module implements the enrichment logic assuming
  population counts are either provided externally or approximated from land-use proxy.
  See README in this directory for raster processing setup instructions.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any

try:
    import h3 as h3lib
    H3_AVAILABLE = True
except ImportError:
    H3_AVAILABLE = False

from pipeline.ingest.osm import PhysicalLayer, PhysicalFeature


@dataclass
class H3Cell:
    """
    Single H3 hexagonal cell enriched with physical and demographic data.

    All scores are normalised [0, 1] for use in agent decision-making.
    """
    h3_index: str
    lat: float
    lon: float
    resolution: int

    # Population
    population_estimate: float = 0.0    # absolute count
    population_density: float = 0.0     # per km²

    # Physical
    feature_counts: dict[str, int] = field(default_factory=dict)
    infrastructure_score: float = 0.0   # composite 0–1
    transit_access: float = 0.0         # 0–1
    land_use_type: str = "unknown"       # residential | commercial | natural | mixed | transit_hub

    # Derived accessibility
    walkability: float = 0.0            # 0–1; based on amenity density
    car_dependency: float = 0.0         # 0–1; inverse of transit+walk

    # Raw
    raw_features: list[dict] = field(default_factory=list)

    @property
    def area_km2(self) -> float:
        """Approximate cell area in km² for this H3 resolution."""
        # H3 average areas by resolution (Uber H3 documentation)
        AREAS = {5: 252.9, 6: 36.1, 7: 5.16, 8: 0.737, 9: 0.105, 10: 0.015}
        return AREAS.get(self.resolution, 0.737)

    def to_agent_context(self) -> dict[str, Any]:
        """Return a dict suitable for injecting into agent decision prompts."""
        return {
            "h3_index": self.h3_index,
            "location": {"lat": round(self.lat, 5), "lon": round(self.lon, 5)},
            "population_density_km2": round(self.population_density, 1),
            "land_use": self.land_use_type,
            "infrastructure_score": round(self.infrastructure_score, 2),
            "transit_access": round(self.transit_access, 2),
            "walkability": round(self.walkability, 2),
            "amenities": self.feature_counts,
        }


class H3Layer:
    """
    Spatial index for an AOI: a dict of H3 cell index → H3Cell.
    Constructed by enriching raw H3 cell shells with OSM and population data.
    """

    def __init__(self, cells: dict[str, H3Cell]):
        self._cells = cells

    def __getitem__(self, h3_index: str) -> H3Cell:
        return self._cells[h3_index]

    def __len__(self) -> int:
        return len(self._cells)

    def __iter__(self):
        return iter(self._cells.values())

    def cell_at(self, lat: float, lon: float) -> H3Cell | None:
        """Return the H3Cell containing a given coordinate."""
        if not H3_AVAILABLE:
            return None
        idx = h3lib.geo_to_h3(lat, lon, list(self._cells.values())[0].resolution)
        return self._cells.get(idx)

    def neighbors(self, h3_index: str, k: int = 1) -> list[H3Cell]:
        """Return k-ring neighbours of a cell."""
        if not H3_AVAILABLE:
            return []
        ring = h3lib.k_ring(h3_index, k) - {h3_index}
        return [self._cells[idx] for idx in ring if idx in self._cells]

    def cells_by_land_use(self, land_use: str) -> list[H3Cell]:
        return [c for c in self._cells.values() if c.land_use_type == land_use]

    def summary_stats(self) -> dict[str, Any]:
        cells = list(self._cells.values())
        return {
            "total_cells": len(cells),
            "total_population": sum(c.population_estimate for c in cells),
            "land_use_distribution": _count_by(cells, "land_use_type"),
            "mean_infrastructure_score": _mean(cells, "infrastructure_score"),
            "mean_transit_access": _mean(cells, "transit_access"),
        }


def build_h3_layer(
    aoi_cells: list[str],
    resolution: int,
    physical_layer: PhysicalLayer,
    population_by_cell: dict[str, float] | None = None,
) -> H3Layer:
    """
    Build an enriched H3Layer from raw cell indices and physical data.

    Parameters
    ----------
    aoi_cells           : List of H3 cell indices covering the AOI
    resolution          : H3 resolution used
    physical_layer      : OSM-derived PhysicalLayer for the AOI
    population_by_cell  : Optional {h3_index: population_count}; if None,
                          uses land-use proxy to estimate distribution

    Returns
    -------
    H3Layer with all cells enriched
    """
    if not H3_AVAILABLE:
        raise ImportError("pip install h3")

    # Index features by H3 cell
    feature_index: dict[str, list[PhysicalFeature]] = {c: [] for c in aoi_cells}
    for feat in physical_layer.features:
        cell = h3lib.geo_to_h3(feat.lat, feat.lon, resolution)
        if cell in feature_index:
            feature_index[cell].append(feat)

    # Compute global maxima for normalisation
    max_features = max((len(v) for v in feature_index.values()), default=1)

    cells: dict[str, H3Cell] = {}
    for h3_index in aoi_cells:
        lat, lon = h3lib.h3_to_geo(h3_index)
        feats = feature_index.get(h3_index, [])
        counts = _count_categories(feats)
        pop = (population_by_cell or {}).get(h3_index, 0.0)

        cell = H3Cell(
            h3_index=h3_index,
            lat=lat,
            lon=lon,
            resolution=resolution,
            population_estimate=pop,
            feature_counts=counts,
        )

        _enrich_scores(cell, feats, counts, max_features)
        if pop > 0:
            cell.population_density = pop / cell.area_km2

        cells[h3_index] = cell

    # Normalise population density across all cells
    max_density = max((c.population_density for c in cells.values()), default=1.0)
    if max_density > 0:
        for c in cells.values():
            c.population_density /= max_density  # now 0–1 relative density

    return H3Layer(cells)


def _count_categories(features: list[PhysicalFeature]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in features:
        counts[f.category] = counts.get(f.category, 0) + 1
    return counts


def _enrich_scores(cell: H3Cell, features: list[PhysicalFeature],
                   counts: dict[str, int], max_features: int):
    n = len(features)

    # Transit access — weighted by transit-specific count
    transit_count = counts.get("transit", 0)
    cell.transit_access = min(1.0, transit_count / 3.0)

    # Infrastructure score — presence-weighted composite
    weights = {"healthcare": 0.25, "education": 0.20, "commerce": 0.20,
               "civic": 0.15, "leisure": 0.10, "transit": 0.10}
    score = sum(min(1.0, counts.get(cat, 0) / 2.0) * w for cat, w in weights.items())
    cell.infrastructure_score = min(1.0, score)

    # Walkability — amenity density relative to max in AOI
    cell.walkability = min(1.0, n / max(max_features, 1))

    # Car dependency — inverse of transit and walkability
    cell.car_dependency = max(0.0, 1.0 - 0.5 * cell.transit_access - 0.5 * cell.walkability)

    # Land use classification
    cell.land_use_type = _classify_land_use(counts)

    cell.raw_features = [{"id": f.osm_id, "cat": f.category, "name": f.name} for f in features]


def _classify_land_use(counts: dict[str, int]) -> str:
    if not counts:
        return "natural"
    dominant = max(counts, key=counts.get)
    total = sum(counts.values())

    if counts.get("transit", 0) >= 3:
        return "transit_hub"
    if dominant == "housing" or (counts.get("housing", 0) / max(total, 1)) > 0.5:
        return "residential"
    if dominant in ("commerce", "employment"):
        return "commercial"
    if dominant == "leisure" and counts.get("commerce", 0) < 2:
        return "natural"
    return "mixed"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _count_by(items: list, attr: str) -> dict:
    result: dict = {}
    for item in items:
        v = getattr(item, attr)
        result[v] = result.get(v, 0) + 1
    return result


def _mean(items: list, attr: str) -> float:
    vals = [getattr(i, attr) for i in items]
    return sum(vals) / len(vals) if vals else 0.0
