"""
Route all agent trips through Andorra's road network.

Edge weight: travel time (hours) = segment_length_km / speed_kmh
  Speed limits follow OSRM's car profile defaults by highway type.
  This makes Dijkstra choose the fastest route (like Google Maps) rather than
  the shortest geometric distance, so agents use highways through valleys
  instead of short mountain-pass residential roads.

Graph construction
──────────────────
Each LineString feature becomes one undirected edge.
Endpoints are rounded to 4 decimal places (~11 m) to snap nearby nodes.
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

ROOT         = Path(__file__).parents[2]
STREETS_FILE = ROOT / "Front end" / "dashboard" / "public" / "model" / "accessibility_streets.geojson"
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
}

# Speed limits (km/h) by OSM highway type — matches OSRM car profile defaults.
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


def seg_travel_time(coords: list, highway: str) -> float:
    """Travel time in hours along a coordinate sequence."""
    dist_km = sum(
        haversine_km(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
        for i in range(len(coords) - 1)
    )
    speed = HIGHWAY_SPEEDS.get(highway, _DEFAULT_SPEED)
    return dist_km / speed


def seg_length_km(coords: list) -> float:
    """Total length in km (stored on edge for reference, not used as weight)."""
    return sum(
        haversine_km(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
        for i in range(len(coords) - 1)
    )


def build_graph(streets: list[dict], allowed_access: set[str]) -> nx.Graph:
    G = nx.Graph()
    for feat in streets:
        if feat["properties"].get("accessibility") not in allowed_access:
            continue
        coords = feat["geometry"]["coordinates"]
        if len(coords) < 2:
            continue
        highway  = feat["properties"].get("highway", "")
        u        = snap(coords[0])
        v        = snap(coords[-1])
        travel_t = seg_travel_time(coords, highway)
        length   = seg_length_km(coords)
        if G.has_edge(u, v):
            if travel_t < G[u][v]["time"]:
                G[u][v].update({"time": travel_t, "length": length,
                                "geometry": coords, "highway": highway})
        else:
            G.add_edge(u, v, time=travel_t, length=length,
                       geometry=coords, highway=highway)
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
    }
    for mode, G in graphs.items():
        print(f"\n  {mode}: {len(G.nodes):,} nodes, {len(G.edges):,} edges", end="")

    # Trim to largest connected component — all routing stays within one component
    for mode in graphs:
        G     = graphs[mode]
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        graphs[mode] = G.subgraph(comps[0]).copy()
    print(f"\n  (trimmed to largest connected component)")

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
    print(f"\n  Done in {elapsed:.1f}s")
    print(f"  Routed: {n_routed:,}  Failed (fallback to linear): {n_failed:,}")
    print(f"  Unique routes cached: {len(route_cache):,}")

    print(f"Saving {OUT_FILE}...", end=" ", flush=True)
    with open(OUT_FILE, "w") as f:
        json.dump(schedules, f, separators=(",", ":"))
    print(f"{OUT_FILE.stat().st_size / 1e6:.1f} MB")
    print("Done. Run: python export_to_viz.py")


if __name__ == "__main__":
    main()
