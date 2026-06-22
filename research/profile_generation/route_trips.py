"""
Route all agent trips through Andorra's road network.

Edge weight: travel time (hours) = segment_length_km / speed_kmh
  Speeds are approximate legal limits by OSM highway class (NOT exact OSRM
  profile values; they are of the right order and monotonic in road class).
  This makes Dijkstra choose the fastest route (like Google Maps) rather than
  the shortest geometric distance, so agents use highways through valleys
  instead of short mountain-pass residential roads.

Graph construction
──────────────────
Each LineString is split into one undirected edge PER CONSECUTIVE VERTEX PAIR,
so interior vertices and mid-segment intersections become graph nodes. (Edging
only the two endpoints would leave roads that meet at an interior vertex
disconnected, fragmenting the network into hundreds of components.)
Vertices are rounded to 4 decimal places (~11 m) to snap nearby/shared nodes.
When two parallel edges exist between the same nodes, keep the faster one.

Output: results/andorra_population/schedules_routed.json
  Same as schedules.json with an added "routed_paths" list per agent —
  one entry per trip: [[lon, lat], ...] or null (fallback to linear interpolation).

Usage:
    cd research/profile_generation
    python route_trips.py
    python export_to_viz.py   # regenerates andorra_trips.json with road paths
"""

import json
import math
import time
from pathlib import Path

import numpy as np
import networkx as nx
from scipy.spatial import KDTree

from artifact_metadata import refresh_run_meta

ROOT         = Path(__file__).parents[2]
# V2.2: Vercel root dir renamed "Front end/dashboard" → "app".
STREETS_FILE = ROOT / "app" / "public" / "model" / "accessibility_streets.geojson"
POP_DIR      = Path(__file__).parent / "results" / "andorra_population"
OUT_FILE     = POP_DIR / "schedules_routed.json"

SNAP_PRECISION = 4  # decimal places for node identity (~11 m)

# H3 centroids farther than this from any road node are skipped — they are
# mountain terrain / census noise with no real road access.
MAX_SNAP_KM = 1.5

MODE_ACCESS = {
    "car":  {"bus/car"},
    "bus":  {"bus/car"},
    "walk": {"bus/car"},
    "taxi": {"bus/car"},
}

# Approximate legal speed limits (km/h) by OSM highway class — NOT exact OSRM
# car-profile values, but of the right magnitude and monotonic in road class.
# Higher-class roads get higher speeds → Dijkstra on travel time naturally
# prefers highways through valleys over short mountain residential roads.
HIGHWAY_SPEEDS: dict[str, float] = {
    "motorway":       110,
    "motorway_link":   60,
    "trunk":           90,
    "trunk_link":      60,
    "primary":         70,
    "primary_link":    60,
    "secondary":       60,
    "secondary_link":  50,
    "tertiary":        50,
    "tertiary_link":   40,
    "unclassified":    40,
    "residential":     30,
    "living_street":   15,
    "pedestrian":      10,
    "road":            40,
}
_DEFAULT_SPEED = 40.0  # km/h fallback for unknown highway types


def snap(coord) -> tuple[float, float]:
    return (round(coord[0], SNAP_PRECISION), round(coord[1], SNAP_PRECISION))


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometres between two lon/lat points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def build_graph(streets: list[dict], allowed_access: set[str]) -> nx.Graph:
    """Build a routable graph by splitting every LineString into per-vertex
    segments, so interior vertices and mid-segment intersections become nodes."""
    G = nx.Graph()
    for feat in streets:
        if feat["properties"].get("accessibility") not in allowed_access:
            continue
        coords = feat["geometry"]["coordinates"]
        if len(coords) < 2:
            continue
        highway = feat["properties"].get("highway", "")
        speed   = HIGHWAY_SPEEDS.get(highway, _DEFAULT_SPEED)
        for a, b in zip(coords[:-1], coords[1:]):
            u = snap(a)
            v = snap(b)
            if u == v:                       # zero-length after snapping
                continue
            length   = haversine_km(a[0], a[1], b[0], b[1])
            travel_t = length / speed
            if G.has_edge(u, v):
                if travel_t < G[u][v]["time"]:
                    G[u][v].update({"time": travel_t, "length": length,
                                    "geometry": [list(a), list(b)], "highway": highway})
            else:
                G.add_edge(u, v, time=travel_t, length=length,
                           geometry=[list(a), list(b)], highway=highway)
    return G


MAX_PTS_PER_ROUTE = 60  # waypoints per routed trip (raised for smoother curves)


def _subsample(pts: list, n: int) -> list:
    total = len(pts)
    if total <= n:
        return pts
    indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]
    return [pts[i] for i in indices]


def reconstruct_path(G: nx.Graph, node_path: list) -> list[list[float]]:
    if len(node_path) < 2:
        return [list(node_path[0])]
    coords: list[list[float]] = []
    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i + 1]
        geom = G[u][v]["geometry"]
        if snap(geom[0]) != u:
            geom = list(reversed(geom))
        seg = [[round(c[0], 5), round(c[1], 5)] for c in geom]
        if coords:
            seg = seg[1:]
        coords.extend(seg)
    return _subsample(coords, MAX_PTS_PER_ROUTE)


def make_kd(G: nx.Graph):
    nodes = list(G.nodes)
    arr   = np.array(nodes)
    return nodes, KDTree(arr)


def nearest_nodes(nodes, kd, lon: float, lat: float, k: int = 3):
    """Return k nearest graph nodes to the given coordinate."""
    k = min(k, len(nodes))
    _, idxs = kd.query([lon, lat], k=k)
    if k == 1:
        return [nodes[idxs]]
    return [nodes[i] for i in idxs]


def main():
    print("Loading street network...", end=" ", flush=True)
    with open(STREETS_FILE) as f:
        streets_geo = json.load(f)
    streets = streets_geo["features"]
    print(f"{len(streets)} segments")

    print("Building routing graphs...", end=" ", flush=True)
    graphs = {
        "car":  build_graph(streets, MODE_ACCESS["car"]),
        "bus":  build_graph(streets, MODE_ACCESS["bus"]),
        "walk": build_graph(streets, MODE_ACCESS["walk"]),
        "taxi": build_graph(streets, MODE_ACCESS["taxi"]),
    }
    for mode, G in graphs.items():
        print(f"\n  {mode}: {len(G.nodes):,} nodes, {len(G.edges):,} edges", end="")

    # Trim to largest connected component — all routing stays within one component.
    # Report how much is dropped so coverage loss is explicit, not silent.
    for mode in graphs:
        G     = graphs[mode]
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        n_before = G.number_of_nodes()
        graphs[mode] = G.subgraph(comps[0]).copy()
        n_after = graphs[mode].number_of_nodes()
        print(f"\n  {mode}: {len(comps)} components; kept largest "
              f"({n_after:,}/{n_before:,} nodes = {n_after/n_before:.1%}, "
              f"dropped {n_before - n_after:,})", end="")
    print()

    kds = {mode: make_kd(G) for mode, G in graphs.items()}

    print("Loading H3 centroids...", end=" ", flush=True)
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from export_to_viz import load_h3_centroids, GEOJSON_PATH
    h3_centroids = load_h3_centroids(GEOJSON_PATH)
    print(f"{len(h3_centroids):,} cells")

    print("Loading schedules...", end=" ", flush=True)
    with open(POP_DIR / "schedules.json") as f:
        schedules: list[dict] = json.load(f)
    print(f"{len(schedules):,} agents")

    snap_cache:  dict[tuple, tuple | None] = {}
    route_cache: dict[tuple, list | None]  = {}

    def get_snap(h3: str, mode: str, exclude: tuple | None = None):
        """Snap an H3 centroid to its nearest road node, skipping `exclude`.
        Returns None if the centroid is more than MAX_SNAP_KM from any road node."""
        pos = h3_centroids.get(h3)
        if pos is None:
            return None
        nodes, kd = kds[mode]
        d_deg, _ = kd.query([pos[0], pos[1]])
        if d_deg * 111 > MAX_SNAP_KM:
            return None  # too far from any road — mountain terrain / census noise
        candidates = nearest_nodes(nodes, kd, pos[0], pos[1], k=5)
        G = graphs[mode]
        for node in candidates:
            if node == exclude:
                continue
            if node in G:
                return node
        return None

    def get_route(o_h3: str, d_h3: str, mode: str) -> list | None:
        if mode not in graphs:
            mode = "car"
        o_node = get_snap(o_h3, mode)
        if o_node is None:
            return None
        # If origin and destination snap to the same node, pick a different
        # destination node so the agent has a real path rather than a zero-length
        # segment that looks like a straight line in the visualisation.
        d_node = get_snap(d_h3, mode, exclude=o_node)
        if d_node is None:
            d_node = get_snap(d_h3, mode)
        if d_node is None:
            return None

        cache_key = (o_node, d_node, mode)
        if cache_key in route_cache:
            return route_cache[cache_key]

        if o_node == d_node:
            # Truly same location — store a minimal two-point path
            route_cache[cache_key] = [list(o_node), list(o_node)]
            return route_cache[cache_key]

        G = graphs[mode]
        try:
            node_path = nx.shortest_path(G, o_node, d_node, weight="time")
            route_cache[cache_key] = reconstruct_path(G, node_path)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            route_cache[cache_key] = None
        return route_cache[cache_key]

    print(f"\nRouting {len(schedules):,} agents' trips...")
    t0 = time.time()
    n_routed = 0
    n_failed = 0

    for i, sched in enumerate(schedules):
        trips = sched.get("trips", [])
        sched["routed_paths"] = []
        for trip in trips:
            mode  = trip.get("mode", "car")
            o_h3  = trip.get("origin_h3", "")
            d_h3  = trip.get("dest_h3",   "")
            coords = get_route(o_h3, d_h3, mode)
            if coords:
                n_routed += 1
                sched["routed_paths"].append(coords)
            else:
                n_failed += 1
                sched["routed_paths"].append(None)

        if (i + 1) % 10000 == 0:
            elapsed = time.time() - t0
            eta     = (len(schedules) - i - 1) / ((i + 1) / elapsed)
            print(f"  {i+1:,}/{len(schedules):,}  "
                  f"cache={len(route_cache):,}  eta={eta:.0f}s", end="\r")

    elapsed = time.time() - t0
    total_trips = n_routed + n_failed
    pct = 100.0 * n_routed / total_trips if total_trips else 0.0
    print(f"\n  Done in {elapsed:.1f}s")
    print(f"  Trips on real road network: {n_routed:,}/{total_trips:,} = {pct:.1f}%")
    print(f"  Fallback to straight-line interpolation: {n_failed:,} "
          f"({100.0 - pct:.1f}%)  — these are NOT real-network routes")
    print(f"  Unique routes cached: {len(route_cache):,}")

    print(f"Saving {OUT_FILE}...", end=" ", flush=True)
    with open(OUT_FILE, "w") as f:
        json.dump(schedules, f, separators=(",", ":"))
    print(f"{OUT_FILE.stat().st_size / 1e6:.1f} MB")
    refresh_run_meta(POP_DIR)
    print("Updated run_meta.json with routing metrics.")
    print("Done. Run: python export_to_viz.py")


if __name__ == "__main__":
    main()
