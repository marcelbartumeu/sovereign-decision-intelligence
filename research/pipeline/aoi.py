"""
Area of Interest (AOI) definition and H3 spatial grid generation.

An AOI is defined by a GeoJSON polygon. The pipeline converts it into a set
of H3 hexagonal cells at a chosen resolution, forming the spatial substrate
for all downstream data aggregation and agent placement.

H3 resolution reference (Uber H3 v3):
  Res 6 → avg area  ~36.1 km²  — country/regional overview
  Res 7 → avg area  ~  5.2 km²  — neighbourhood level
  Res 8 → avg area  ~  0.74 km² — block level (recommended default)
  Res 9 → avg area  ~  0.11 km² — building cluster level

For Andorra (467 km²) at res 8: ~630 cells covering the territory.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any

try:
    import h3
except ImportError:
    h3 = None  # pipeline degrades gracefully without h3 installed


@dataclass
class AOI:
    """
    Immutable AOI definition.

    Attributes
    ----------
    name        : Human-readable place name (used in LLM world context)
    iso3        : ISO 3166-1 alpha-3 country code (drives WorldPop / World Bank queries)
    geojson     : GeoJSON Feature or FeatureCollection dict with Polygon geometry
    h3_resolution: H3 resolution for grid generation (default 8)
    metadata    : Arbitrary country/region metadata injected into context layers
    """
    name: str
    iso3: str
    geojson: dict
    h3_resolution: int = 8
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str, name: str, iso3: str, resolution: int = 8) -> "AOI":
        with open(path) as f:
            geojson = json.load(f)
        return cls(name=name, iso3=iso3, geojson=geojson, h3_resolution=resolution)

    @property
    def polygon_coords(self) -> list[list[float]]:
        """Return the outer ring coordinates as [[lng, lat], ...] (GeoJSON order)."""
        geom = self.geojson
        if geom.get("type") == "Feature":
            geom = geom["geometry"]
        if geom.get("type") == "FeatureCollection":
            geom = geom["features"][0]["geometry"]
        if geom["type"] == "Polygon":
            return geom["coordinates"][0]
        if geom["type"] == "MultiPolygon":
            return geom["coordinates"][0][0]
        raise ValueError(f"Unsupported geometry type: {geom['type']}")

    def h3_cells(self) -> list[str]:
        """Return all H3 cell indices covering the AOI polygon."""
        if h3 is None:
            raise ImportError("pip install h3")
        coords = self.polygon_coords
        # h3.polyfill expects {type, coordinates} GeoJSON
        geo = {"type": "Polygon", "coordinates": [coords]}
        return list(h3.polyfill_geojson(geo, self.h3_resolution))

    def cell_center(self, cell: str) -> tuple[float, float]:
        """Return (lat, lng) center of an H3 cell."""
        if h3 is None:
            raise ImportError("pip install h3")
        return h3.h3_to_geo(cell)

    def cell_boundary(self, cell: str) -> list[tuple[float, float]]:
        """Return boundary vertices of an H3 cell as [(lat, lng), ...]."""
        if h3 is None:
            raise ImportError("pip install h3")
        return h3.h3_to_geo_boundary(cell)

    def cell_neighbors(self, cell: str, k: int = 1) -> list[str]:
        """Return k-ring neighbours of a cell."""
        if h3 is None:
            raise ImportError("pip install h3")
        return list(h3.k_ring(cell, k) - {cell})


# ── Pre-defined AOIs ──────────────────────────────────────────────────────────

def andorra_aoi(resolution: int = 8) -> AOI:
    """
    Andorra AOI using a simplified administrative boundary polygon.
    Coordinates approximate the national boundary (WGS84).
    For production use, load the official boundary from Natural Earth or GADM.
    """
    # Simplified 12-vertex approximation of Andorra's border
    andorra_boundary = {
        "type": "Polygon",
        "coordinates": [[
            [1.4078, 42.4344],
            [1.4451, 42.3953],
            [1.5012, 42.3740],
            [1.5687, 42.3760],
            [1.6312, 42.4020],
            [1.7012, 42.4198],
            [1.7862, 42.4590],
            [1.8012, 42.5120],
            [1.7540, 42.6320],
            [1.6612, 42.6890],
            [1.5312, 42.6560],
            [1.4312, 42.5590],
            [1.4078, 42.4344],
        ]]
    }
    return AOI(
        name="Andorra",
        iso3="AND",
        geojson={"type": "Feature", "geometry": andorra_boundary, "properties": {}},
        h3_resolution=resolution,
        metadata={
            "area_km2": 467.6,
            "population": 90000,
            "capital": "Andorra la Vella",
            "languages": ["Catalan", "Spanish", "French", "Portuguese"],
            "currency": "EUR",
        }
    )
