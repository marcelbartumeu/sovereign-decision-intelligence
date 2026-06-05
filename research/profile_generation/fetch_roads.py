"""
Fetch paved road network for any country from OpenStreetMap via Overpass API.

Uses the same highway-type whitelist as OSRM / Valhalla / GraphHopper:
  motorway, trunk, primary, secondary, tertiary, unclassified,
  residential, living_street, pedestrian, road
  (plus their *_link variants for on/off-ramps and connectors)

Excludes: track, path, footway, cycleway, bridleway, steps, service
          — these are unpaved or non-vehicular and cause cross-terrain routes.

Output: accessibility_streets.geojson (replaces existing file)
  Each feature is a LineString with property {"accessibility": "bus/car"}.
  The "bus/car" label keeps backward-compatibility with route_trips.py.

Usage (reproducible for any country — just change BBOX):
    cd research/profile_generation
    python fetch_roads.py

    # Override bounding box for a different region:
    python fetch_roads.py --bbox "42.42,1.40,42.66,1.79"
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Universally recognised paved/driveable OSM highway types.
# This list is reproduced verbatim from OSRM's car profile and is therefore
# reproducible for any region worldwide.
PAVED_HIGHWAY_TYPES = [
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "pedestrian",
    "road",
]

# Andorra bounding box (south, west, north, east)
DEFAULT_BBOX = "42.42,1.40,42.66,1.79"

ROOT     = Path(__file__).parents[2]
OUT_PATH = ROOT / "Front end" / "dashboard" / "public" / "model" / "accessibility_streets.geojson"


def build_query(bbox: str) -> str:
    hw_regex = "|".join(PAVED_HIGHWAY_TYPES)
    return f"""[out:json][timeout:120];
(
  way["highway"~"^({hw_regex})$"]({bbox});
);
out geom;"""


def fetch_overpass(query: str) -> dict:
    session = requests.Session()
    session.headers["User-Agent"] = "AndorraABM-RoadFetch/1.0"
    for attempt in range(3):
        try:
            resp = session.post(OVERPASS_URL, data={"data": query}, timeout=150)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            print(f"  Retry {attempt + 1}/3: {exc}")
            time.sleep(10)
    return {}


def to_geojson(elements: list[dict]) -> dict:
    features = []
    for el in elements:
        if el.get("type") != "way":
            continue
        geom = el.get("geometry")
        if not geom or len(geom) < 2:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in geom]
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "accessibility": "bus/car",
                "highway": el.get("tags", {}).get("highway", ""),
                "name": el.get("tags", {}).get("name", ""),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", default=DEFAULT_BBOX,
                        help="Bounding box: south,west,north,east")
    args = parser.parse_args()

    print(f"Querying Overpass for paved roads in bbox {args.bbox}...")
    query = build_query(args.bbox)
    data  = fetch_overpass(query)

    elements = data.get("elements", [])
    print(f"  Received {len(elements):,} way elements")

    geojson = to_geojson(elements)
    n = len(geojson["features"])
    print(f"  Built {n:,} LineString features")

    with open(OUT_PATH, "w") as f:
        json.dump(geojson, f, separators=(",", ":"))

    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"  Written → {OUT_PATH}  ({size_mb:.1f} MB)")
    print("Done. Run: python route_trips.py && python export_to_viz.py")


if __name__ == "__main__":
    main()
