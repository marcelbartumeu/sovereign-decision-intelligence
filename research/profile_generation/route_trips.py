"""
Route all agent trips through Andorra's road network.

Uses the local accessibility_streets.geojson (7655 road segments already in the
project) to build a routing graph — no external API calls required.

Graph construction
──────────────────
Each LineString feature becomes one directed edge (both directions added).
Endpoints are rounded to 4 decimal places (~11m) to snap nearby nodes together.
Edge weight = total length in degrees (proxy for distance — sufficient for
shortest-path routing within a small country).

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

# Round coordinates to this many decimal places for node identity (~11m at 4dp)
SNAP_PRECISION = 4

MODE_ACCESS = {
    "car":  {"bus/car"},
    "bus":  {"bus/car"},
    "walk": {"bus/car", "walk", "bike"},
}


def snap(coord: list[float]) -> tuple[float, float]:
    return (round(coord[0], SNAP_PRECISION), round(coord[1], SNAP_PRECISION))


def seg_length(coords: list) -> float:
    """Sum of Euclidean distances along a coordinate sequence (degrees)."""
    total = 0.0
    for i in range(len(coords) - 1):
        dx = coords[i+1][0] - coords[i][0]
        dy = coords[i+1][1] - coords[i][1]
        total += math.sqrt(dx*dx + dy*dy)
    return total


def build_graph(streets: list[dict], allowed_access: set[str]) -> nx.Graph:
    G = nx.Graph()
    for feat in streets:
        acc = feat["properties"].get("accessibility")
        if acc not in allowed_access:
            continue
        coords = feat["geometry"]["coordinates"]
        if len(coords) < 2:
            continue
        u = snap(coords[0])
        v = snap(coords[-1])
        length = seg_length(coords)
        # Store full geometry on the edge (needed to reconstruct the path)
        if G.has_edge(u, v):
            if length < G[u][v]["length"]:
                G[u][v].update({"length": length, "geometry": coords})
        else:
            G.add_edge(u, v, length=length, geometry=coords)
    return G


MAX_PTS_PER_ROUTE = 40  # cap road geometry to keep schedules_routed.json small


def _subsample(pts: list, n: int) -> list:
    """Uniformly subsample a list to n items, always keeping endpoints."""
    total = len(pts)
    if total <= n:
        return pts
    indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]
    return [pts[i] for i in indices]


def reconstruct_path(G: nx.Graph, node_path: list) -> list[list[float]]:
    """Concatenate edge geometries into a full [lon, lat] list, capped at MAX_PTS_PER_ROUTE."""
    if len(node_path) < 2:
        return [list(node_path[0])]
    coords: list[list[float]] = []
    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i+1]
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


def nearest_node(nodes, kd, lon: float, lat: float):
    _, idx = kd.query([lon, lat])
    return nodes[idx]


def main():
    # Load street network
    print("Loading street network...", end=" ", flush=True)
    with open(STREETS_FILE) as f:
        streets_geo = json.load(f)
    streets = streets_geo["features"]
    print(f"{len(streets)} segments")

    # Build one graph per mode (car uses bus/car roads; walk uses all)
    print("Building routing graphs...", end=" ", flush=True)
    graphs = {
        "car":  build_graph(streets, MODE_ACCESS["car"]),
        "bus":  build_graph(streets, MODE_ACCESS["bus"]),
        "walk": build_graph(streets, MODE_ACCESS["walk"]),
    }
    for mode, G in graphs.items():
        print(f"\n  {mode}: {len(G.nodes):,} nodes, {len(G.edges):,} edges", end="")

    # Largest connected component per graph (routing only works within one component)
    for mode in graphs:
        G     = graphs[mode]
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        main_comp = G.subgraph(comps[0]).copy()
        graphs[mode] = main_comp

    print(f"\n  (trimmed to largest connected component)")

    # KD-trees for nearest-node snapping
    kds = {mode: make_kd(G) for mode, G in graphs.items()}

    # Load H3 centroids for snapping trip origins/destinations
    print("Loading H3 centroids...", end=" ", flush=True)
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from export_to_viz import load_h3_centroids, GEOJSON_PATH
    h3_centroids = load_h3_centroids(GEOJSON_PATH)
    print(f"{len(h3_centroids):,} cells")

    # Load schedules
    print("Loading schedules...", end=" ", flush=True)
    with open(POP_DIR / "schedules.json") as f:
        schedules: list[dict] = json.load(f)
    print(f"{len(schedules):,} agents")

    # Routing with caching — many trips share the same H3 origin/dest
    snap_cache:  dict[tuple[str, str], tuple | None] = {}   # (h3, mode) → graph_node
    route_cache: dict[tuple, list | None]             = {}   # (o_node, d_node, mode) → coords

    def get_snap(h3: str, mode: str):
        key = (h3, mode)
        if key in snap_cache:
            return snap_cache[key]
        pos = h3_centroids.get(h3)
        if pos is None:
            snap_cache[key] = None
            return None
        G = graphs[mode]
        nodes, kd = kds[mode]
        node = nearest_node(nodes, kd, pos[0], pos[1])
        if node not in G:
            snap_cache[key] = None
            return None
        snap_cache[key] = node
        return node

    def get_route(o_h3: str, d_h3: str, mode: str) -> list | None:
        o_node = get_snap(o_h3, mode)
        d_node = get_snap(d_h3, mode)
        if o_node is None or d_node is None:
            return None
        cache_key = (o_node, d_node, mode)
        if cache_key in route_cache:
            return route_cache[cache_key]

        if o_node == d_node:
            route_cache[cache_key] = [list(o_node), list(o_node)]
            return route_cache[cache_key]

        G = graphs[mode]
        try:
            path = nx.shortest_path(G, o_node, d_node, weight="length")
            coords = reconstruct_path(G, path)
            route_cache[cache_key] = coords
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            route_cache[cache_key] = None
        return route_cache[cache_key]

    # Process all agents
    print(f"\nRouting {len(schedules):,} agents' trips...")
    t0 = time.time()
    n_routed = 0
    n_failed = 0

    for i, sched in enumerate(schedules):
        trips = sched.get("trips", [])
        sched["routed_paths"] = []
        for trip in trips:
            mode  = trip.get("mode",       "car")
            o_h3  = trip.get("origin_h3",  "")
            d_h3  = trip.get("dest_h3",    "")
            # Normalise mode key
            if mode not in graphs:
                mode = "car"
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
