"""
OSM POI lookup — Stage 2 facility instantiation.

Two-stage destination architecture (Ben-Akiva & Lerman 1985; eqasim, Hörl & Balac 2021):
  Stage 1 (destination_model.py): H3 hex zone selection via gravity model.
  Stage 2 (this module):          Specific facility (POI) sampling within the chosen hex.

This module builds and queries a POI index keyed by (h3_cell, activity_type).
Data source: OpenStreetMap via Overpass API.

Usage
─────
Build the index once (requires internet access):
    from schedules.osm_poi import build_poi_index
    build_poi_index(output_path="poi_index.json")

Load at runtime:
    lookup = PoiLookup.load("poi_index.json")
    poi = lookup.sample("8928308280fffff", "grocery", rng)
    # poi is a dict: {name, lat, lon, h3, osm_id, osm_type, activity_type}

Without an index file, PoiLookup.sample() falls back to the H3 cell centroid,
which preserves the Stage 1 spatial choice without crashing the pipeline.

OSM tag → activity type mapping
────────────────────────────────
Tags are drawn from place_layers.LAYER_REGISTRY (osm_tag field) and extended
here with more specific sub-tags for realistic facility sampling.
Validation: Klinkhardt et al. (2021) confirm OSM provides ≥85% coverage for
commercial, educational, and healthcare facilities in European urban areas.

Overpass API endpoint: https://overpass-api.de/api/interpreter
Andorra bounding box: 42.43, 1.41, 42.66, 1.79
H3 resolution 9 (≈ 0.1 km²) used for indexing — matches destination_model.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import h3 as _h3
    _H3_AVAILABLE = True
except ImportError:
    _H3_AVAILABLE = False

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


# ── OSM tag → activity type mapping ───────────────────────────────────────────
# Each activity type maps to a list of Overpass filter strings.
# Uses extended tag set beyond place_layers.LAYER_REGISTRY osm_tag for coverage.

OSM_FILTERS: dict[str, list[str]] = {
    "work": [
        'node["landuse"="commercial"]',
        'node["office"]',
        'node["amenity"="coworking_space"]',
        'way["landuse"="commercial"]',
        'way["office"]',
    ],
    "grocery": [
        'node["shop"="supermarket"]',
        'node["shop"="convenience"]',
        'node["shop"="greengrocer"]',
        'node["shop"="butcher"]',
        'node["shop"="bakery"]',
        'node["amenity"="marketplace"]',
    ],
    "shopping": [
        'node["shop"="clothes"]',
        'node["shop"="electronics"]',
        'node["shop"="sports"]',
        'node["shop"="shoes"]',
        'node["shop"="mall"]',
        'node["shop"="department_store"]',
        'node["shop"="gift"]',
        'node["shop"="jewelry"]',
    ],
    "education": [
        'node["amenity"="school"]',
        'node["amenity"="university"]',
        'node["amenity"="college"]',
        'node["amenity"="childcare"]',
        'node["amenity"="library"]',
        'way["amenity"="school"]',
        'way["amenity"="university"]',
    ],
    "leisure_indoor": [
        'node["leisure"="sports_centre"]',
        'node["leisure"="fitness_centre"]',
        'node["amenity"="restaurant"]',
        'node["amenity"="fast_food"]',
        'node["amenity"="cafe"]',
        'node["amenity"="bar"]',
        'node["amenity"="pub"]',
        'node["amenity"="cinema"]',
        'node["amenity"="theatre"]',
        'node["tourism"="museum"]',
    ],
    "leisure_outdoor": [
        'node["leisure"="park"]',
        'node["leisure"="pitch"]',
        'node["leisure"="playground"]',
        'node["tourism"="ski_resort"]',
        'node["leisure"="sports_hall"]',
        'way["leisure"="park"]',
        'way["natural"="peak"]',
    ],
    "healthcare": [
        'node["amenity"="hospital"]',
        'node["amenity"="clinic"]',
        'node["amenity"="doctors"]',
        'node["amenity"="pharmacy"]',
        'node["amenity"="dentist"]',
        'way["amenity"="hospital"]',
    ],
    "civic": [
        'node["amenity"="place_of_worship"]',
        'node["amenity"="townhall"]',
        'node["amenity"="post_office"]',
        'node["amenity"="bank"]',
        'node["office"="government"]',
        'node["amenity"="community_centre"]',
    ],
}

# Andorra bounding box: (south, west, north, east)
ANDORRA_BBOX = (42.43, 1.41, 42.66, 1.79)

# H3 resolution for POI indexing (matches destination_model.py grid)
POI_H3_RES = 9

# Overpass API endpoint
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Default index path relative to this file
_DEFAULT_INDEX_PATH = Path(__file__).parent / "poi_index.json"


# ── Tag-to-activity classifier ─────────────────────────────────────────────────
# Maps (tag_key, tag_value_prefix) → activity_type.
# Used client-side after downloading all POIs in one query.

_TAG_CLASSIFIER: list[tuple[str, str, str]] = [
    # (tag_key, value_starts_with, activity_type)
    ("amenity",  "hospital",         "healthcare"),
    ("amenity",  "clinic",           "healthcare"),
    ("amenity",  "doctors",          "healthcare"),
    ("amenity",  "pharmacy",         "healthcare"),
    ("amenity",  "dentist",          "healthcare"),
    ("amenity",  "school",           "education"),
    ("amenity",  "university",       "education"),
    ("amenity",  "college",          "education"),
    ("amenity",  "childcare",        "education"),
    ("amenity",  "library",          "education"),
    ("amenity",  "restaurant",       "leisure_indoor"),
    ("amenity",  "fast_food",        "leisure_indoor"),
    ("amenity",  "cafe",             "leisure_indoor"),
    ("amenity",  "bar",              "leisure_indoor"),
    ("amenity",  "pub",              "leisure_indoor"),
    ("amenity",  "cinema",           "leisure_indoor"),
    ("amenity",  "theatre",          "leisure_indoor"),
    ("amenity",  "place_of_worship", "civic"),
    ("amenity",  "townhall",         "civic"),
    ("amenity",  "post_office",      "civic"),
    ("amenity",  "bank",             "civic"),
    ("amenity",  "community_centre", "civic"),
    ("amenity",  "marketplace",      "grocery"),
    ("amenity",  "coworking_space",  "work"),
    ("shop",     "supermarket",      "grocery"),
    ("shop",     "convenience",      "grocery"),
    ("shop",     "greengrocer",      "grocery"),
    ("shop",     "butcher",          "grocery"),
    ("shop",     "bakery",           "grocery"),
    ("shop",     "clothes",          "shopping"),
    ("shop",     "electronics",      "shopping"),
    ("shop",     "sports",           "shopping"),
    ("shop",     "shoes",            "shopping"),
    ("shop",     "mall",             "shopping"),
    ("shop",     "department_store", "shopping"),
    ("shop",     "gift",             "shopping"),
    ("shop",     "jewelry",          "shopping"),
    ("leisure",  "sports_centre",    "leisure_indoor"),
    ("leisure",  "fitness_centre",   "leisure_indoor"),
    ("leisure",  "park",             "leisure_outdoor"),
    ("leisure",  "pitch",            "leisure_outdoor"),
    ("leisure",  "playground",       "leisure_outdoor"),
    ("leisure",  "ski_resort",       "leisure_outdoor"),
    ("tourism",  "museum",           "leisure_indoor"),
    ("tourism",  "ski_resort",       "leisure_outdoor"),
    ("natural",  "peak",             "leisure_outdoor"),
    ("office",   "",                 "work"),
    ("landuse",  "commercial",       "work"),
]


def _classify(tags: dict) -> str | None:
    """Return the activity_type for a POI's tag dict, or None if unclassified."""
    for key, prefix, activity in _TAG_CLASSIFIER:
        val = tags.get(key, "")
        if val and val.startswith(prefix):
            return activity
    return None


# ── Index builder ──────────────────────────────────────────────────────────────

def build_poi_index(
    output_path: str | Path = _DEFAULT_INDEX_PATH,
    bbox: tuple[float, float, float, float] = ANDORRA_BBOX,
    h3_resolution: int = POI_H3_RES,
    timeout: int = 60,
    retries: int = 3,
    delay_s: float = 5.0,
) -> dict:
    """
    Download ALL POI-relevant nodes from Overpass in a single query, classify
    them client-side, and build a spatial index keyed by (h3_cell, activity_type).
    Saves JSON to output_path.

    Single-query approach avoids rate-limit issues from multiple sequential
    requests and is significantly faster for small regions like Andorra.

    Parameters
    ──────────
    output_path  : path for the resulting JSON index file
    bbox         : (south, west, north, east) bounding box
    h3_resolution: H3 resolution for cell assignment (match destination_model)
    timeout      : Overpass query timeout in seconds
    retries      : number of retry attempts on server error
    delay_s      : delay between retries

    Returns
    ───────
    dict: {h3_cell: {activity_type: [{name, lat, lon, osm_id, osm_type}]}}
    """
    if not _REQUESTS_AVAILABLE:
        raise ImportError("requests library required: pip install requests")
    if not _H3_AVAILABLE:
        raise ImportError("h3 library required: pip install h3")

    import time

    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    # Single comprehensive query: all nodes with any of the relevant tag keys.
    # Using `nwr` would include ways/relations but is much slower; node-only
    # is sufficient for POI facility sampling in Andorra.
    query = f"""
[out:json][timeout:{timeout}];
(
  node["amenity"]({bbox_str});
  node["shop"]({bbox_str});
  node["leisure"]({bbox_str});
  node["office"]({bbox_str});
  node["tourism"]({bbox_str});
  node["natural"="peak"]({bbox_str});
  node["landuse"="commercial"]({bbox_str});
);
out;
"""

    headers = {
        "User-Agent": "AndorraABM/2.1 (research; profile_generation)",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    elements = None
    for attempt in range(retries):
        try:
            print(f"  Querying Overpass API (attempt {attempt+1}/{retries})...", end=" ", flush=True)
            resp = _requests.post(
                _OVERPASS_URL,
                data={"data": query},
                headers=headers,
                timeout=timeout + 30,
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            print(f"{len(elements)} nodes received")
            break
        except Exception as exc:
            print(f"FAILED ({exc})")
            if attempt < retries - 1:
                print(f"  Retrying in {delay_s}s...")
                time.sleep(delay_s)

    if elements is None:
        print("All attempts failed — returning empty index.")
        return {}

    index: dict[str, dict[str, list]] = {}
    classified = 0
    skipped = 0

    for el in elements:
        lat, lon = el.get("lat"), el.get("lon")
        if lat is None or lon is None:
            skipped += 1
            continue

        tags = el.get("tags", {})
        activity = _classify(tags)
        if activity is None:
            skipped += 1
            continue

        cell = _h3.latlng_to_cell(lat, lon, h3_resolution)
        poi  = {
            "name":     tags.get("name", ""),
            "lat":      round(lat, 6),
            "lon":      round(lon, 6),
            "osm_id":   el.get("id"),
            "osm_type": "node",
        }
        index.setdefault(cell, {}).setdefault(activity, []).append(poi)
        classified += 1

    print(f"Classified: {classified} POIs, skipped: {skipped}")
    counts = {act: sum(len(v.get(act, [])) for v in index.values()) for act in OSM_FILTERS}
    for act, n in counts.items():
        print(f"  {act:<20}: {n}")
    print(f"H3 cells with ≥1 POI: {len(index)}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(index, f, separators=(",", ":"))
    print(f"Index saved → {output_path}")
    return index


# ── Runtime lookup ─────────────────────────────────────────────────────────────

class PoiLookup:
    """
    Stage 2 POI sampler. Loads a pre-built index and samples specific facilities
    within an H3 cell for a given activity type.

    Falls back to the H3 centroid (as a synthetic POI) when:
    - No index file was loaded
    - The queried cell has no POIs for the given activity type
    - Adjacent cells are also empty (after one ring of expansion)
    """

    def __init__(self, index: dict[str, dict[str, list]] | None = None):
        self._index = index or {}
        # Detect the H3 resolution used when building this index.
        # Callers may pass cells at a finer resolution (e.g. res 10 from the
        # destination model); we convert up to the index resolution automatically.
        first_key = next(iter(self._index), None)
        if first_key and _H3_AVAILABLE:
            import h3 as _h3_mod
            self._index_res: int | None = _h3_mod.get_resolution(first_key)
        else:
            self._index_res = None

    @classmethod
    def load(cls, path: str | Path = _DEFAULT_INDEX_PATH) -> "PoiLookup":
        """Load an index built by build_poi_index()."""
        path = Path(path)
        if not path.exists():
            return cls(None)
        with open(path) as f:
            return cls(json.load(f))

    @property
    def loaded(self) -> bool:
        return bool(self._index)

    def _normalize_cell(self, h3_cell: str) -> str:
        """Convert cell to index resolution if it is finer than the index."""
        if not (_H3_AVAILABLE and self._index_res is not None):
            return h3_cell
        import h3 as _h3_mod
        cell_res = _h3_mod.get_resolution(h3_cell)
        if cell_res > self._index_res:
            return _h3_mod.cell_to_parent(h3_cell, self._index_res)
        return h3_cell

    def sample(
        self,
        h3_cell: str,
        activity_type: str,
        rng: np.random.Generator,
        expand_rings: int = 1,
    ) -> dict:
        """
        Sample a specific POI for the given H3 cell and activity type.

        Automatically normalises the queried cell to the index resolution —
        so res-10 destination cells work against a res-9 index.

        If the cell has no matching POIs, expand to adjacent cells (up to
        expand_rings rings). If still empty, return an H3-centroid fallback.

        Returns
        ───────
        dict with keys: name, lat, lon, h3, osm_id (None for fallback), osm_type
        """
        h3_cell = self._normalize_cell(h3_cell)

        # Direct cell lookup
        poi = self._sample_from_cell(h3_cell, activity_type, rng)
        if poi:
            poi["h3"] = h3_cell
            return poi

        # Expand to adjacent rings
        if _H3_AVAILABLE and self._index and expand_rings > 0:
            for ring in range(1, expand_rings + 1):
                neighbors = _h3.grid_disk(h3_cell, ring)
                candidates = []
                for nbr in neighbors:
                    pois = self._index.get(nbr, {}).get(activity_type, [])
                    candidates.extend(pois)
                if candidates:
                    chosen = candidates[int(rng.integers(len(candidates)))]
                    return {**chosen, "h3": h3_cell}

        # Fallback: H3 centroid
        return self._centroid_fallback(h3_cell, activity_type)

    def _sample_from_cell(
        self, h3_cell: str, activity_type: str, rng: np.random.Generator
    ) -> dict | None:
        pois = self._index.get(h3_cell, {}).get(activity_type, [])
        if not pois:
            return None
        return dict(pois[int(rng.integers(len(pois)))])

    @staticmethod
    def _centroid_fallback(h3_cell: str, activity_type: str) -> dict:
        if _H3_AVAILABLE:
            lat, lon = _h3.cell_to_latlng(h3_cell)
        else:
            lat, lon = 0.0, 0.0
        return {
            "name":      "",
            "lat":       round(lat, 6),
            "lon":       round(lon, 6),
            "h3":        h3_cell,
            "osm_id":    None,
            "osm_type":  "fallback",
        }

    def coverage_report(self) -> dict:
        """Summary of POI counts per activity type across all indexed cells."""
        report: dict[str, int] = {act: 0 for act in OSM_FILTERS}
        for cell_data in self._index.values():
            for act, pois in cell_data.items():
                if act in report:
                    report[act] += len(pois)
        report["total_cells"] = len(self._index)
        return report
