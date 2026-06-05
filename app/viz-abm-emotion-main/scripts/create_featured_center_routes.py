#!/usr/bin/env python3
"""Create cleaner, compelling center-city routes for Carlos and Elena in Andorra la Vella."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Sequence, Tuple

import networkx as nx
import numpy as np
import osmnx as ox

Coord = Tuple[float, float]  # (lon, lat)


def stitch_route(graph: nx.MultiDiGraph, waypoints: Sequence[Coord]) -> List[Coord]:
    nodes = [int(ox.distance.nearest_nodes(graph, X=lon, Y=lat)) for lon, lat in waypoints]
    out_nodes: List[int] = []

    for a, b in zip(nodes[:-1], nodes[1:]):
        if a == b:
            if not out_nodes:
                out_nodes.append(a)
            continue
        try:
            seg = nx.shortest_path(graph, a, b, weight="length")
        except Exception:
            seg = [a, b]

        if not out_nodes:
            out_nodes.extend(seg)
        else:
            out_nodes.extend(seg[1:])

    if not out_nodes and nodes:
        out_nodes = [nodes[0]]

    # Convert to lon/lat and remove consecutive duplicates
    coords: List[Coord] = []
    for n in out_nodes:
        pt = (float(graph.nodes[n]["x"]), float(graph.nodes[n]["y"]))
        if not coords or pt != coords[-1]:
            coords.append(pt)
    return coords


def resample_polyline(points: Sequence[Coord], target_count: int) -> List[List[float]]:
    if target_count <= 0:
        return []
    if len(points) == 0:
        return []
    if len(points) == 1:
        return [[points[0][0], points[0][1]] for _ in range(target_count)]

    pts = np.array(points, dtype=float)
    seg = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
    cum = np.concatenate(([0.0], np.cumsum(seg)))
    total = cum[-1]

    if total == 0:
        return [[float(points[0][0]), float(points[0][1])] for _ in range(target_count)]

    dists = np.linspace(0, total, target_count)
    out: List[List[float]] = []
    j = 0

    for d in dists:
        while j < len(seg) - 1 and cum[j + 1] < d:
            j += 1
        d0, d1 = cum[j], cum[j + 1]
        t = 0.0 if d1 == d0 else (d - d0) / (d1 - d0)
        p = pts[j] + t * (pts[j + 1] - pts[j])
        out.append([float(p[0]), float(p[1])])

    return out


def resize_series(series: List[Any], target: int, fallback: Any) -> List[Any]:
    if target <= 0:
        return []
    if not series:
        return [fallback for _ in range(target)]
    if len(series) >= target:
        return series[:target]
    fill = series[-1]
    return series + [fill for _ in range(target - len(series))]


def apply_trip_route(
    trip: dict,
    coords: Sequence[Coord],
) -> None:
    n = len(trip.get("path", []))
    if n <= 0:
        return

    trip["path"] = resample_polyline(coords, n)

    # Keep emotional semantics but ensure length matches path.
    trip["emotions"] = resize_series(trip.get("emotions", []), n, "green")

    # Mood vectors should align too.
    mood = trip.get("mood_vectors", [])
    if mood and isinstance(mood[0], list):
        fallback = mood[-1]
    else:
        fallback = [0.2, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1]
    trip["mood_vectors"] = resize_series(mood, n, fallback)


def rewrite_agent(agent_path: Path, graphs: dict[str, nx.MultiDiGraph], plan: dict) -> None:
    data = json.loads(agent_path.read_text(encoding="utf-8"))
    trips = data.get("trips", [])

    for trip_cfg in plan["trips"]:
        idx = trip_cfg["trip_id"]
        if idx >= len(trips):
            continue
        trip = trips[idx]
        network = trip_cfg["network"]
        graph = graphs[network]
        route = stitch_route(graph, trip_cfg["waypoints"])
        apply_trip_route(trip, route)

    # Rebuild clean, monotonic timestamps and aligned start_time.
    t = 0
    for trip in trips:
        n = len(trip.get("path", []))
        trip["timestamps"] = list(range(t, t + n))
        trip["start_time"] = t
        t += n

    data["trips"] = trips
    agent_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    base = Path("src/simulation_output")

    print("Loading Andorra la Vella street networks...")
    graphs = {
        "walk": ox.graph_from_place("Andorra la Vella, Andorra", network_type="walk", simplify=True),
        "bike": ox.graph_from_place("Andorra la Vella, Andorra", network_type="bike", simplify=True),
        "drive": ox.graph_from_place("Andorra la Vella, Andorra", network_type="drive", simplify=True),
    }

    # Simple point-to-point movements.
    # Narrative: both meet in the center, then share one segment, then split.
    meet_point = (1.5251, 42.5072)
    shared_point = (1.5276, 42.5089)

    plans = {
        "updated_agent_carlos_.json": {
            "trips": [
                {
                    "trip_id": 0,
                    "network": "walk",
                    "waypoints": [
                        (1.5217, 42.5059),
                        meet_point,
                    ],
                },
                {
                    "trip_id": 1,
                    "network": "bike",
                    "waypoints": [
                        meet_point,
                        shared_point,
                    ],
                },
                {
                    "trip_id": 2,
                    "network": "drive",
                    "waypoints": [
                        shared_point,
                        (1.5271, 42.5075),
                    ],
                },
            ]
        },
        "updated_agent_elena_.json": {
            "trips": [
                {
                    "trip_id": 0,
                    "network": "walk",
                    "waypoints": [
                        (1.5277, 42.5058),
                        meet_point,
                    ],
                },
                {
                    "trip_id": 1,
                    "network": "bike",
                    "waypoints": [
                        meet_point,
                        shared_point,
                    ],
                },
                {
                    "trip_id": 2,
                    "network": "drive",
                    "waypoints": [
                        shared_point,
                        (1.5239, 42.5070),
                    ],
                },
            ]
        },
    }

    for filename, plan in plans.items():
        agent_file = base / filename
        rewrite_agent(agent_file, graphs, plan)
        print(f"Updated {filename}")

    print("Done.")


if __name__ == "__main__":
    main()
