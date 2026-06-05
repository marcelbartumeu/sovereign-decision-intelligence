#!/usr/bin/env python3
"""
Snap agent trip paths to an OSM street network and resample back to original point counts.

Usage:
  python snap_agents_to_osm_streets.py \
    --input-dir src/simulation_output \
    --place "Andorra la Vella, Andorra" \
    --network-type walk
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import networkx as nx
import numpy as np
import osmnx as ox

Coord = Tuple[float, float]  # (lon, lat)


def euclidean(a: Coord, b: Coord) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dedupe_consecutive(points: Sequence[Coord]) -> List[Coord]:
    if not points:
        return []
    out = [points[0]]
    for p in points[1:]:
        if p != out[-1]:
            out.append(p)
    return out


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

    sample_d = np.linspace(0, total, target_count)
    out = []
    j = 0
    for d in sample_d:
        while j < len(seg) - 1 and cum[j + 1] < d:
            j += 1
        d0, d1 = cum[j], cum[j + 1]
        if d1 == d0:
            t = 0.0
        else:
            t = (d - d0) / (d1 - d0)
        p = pts[j] + t * (pts[j + 1] - pts[j])
        out.append([float(p[0]), float(p[1])])
    return out


def route_between_nodes(G: nx.MultiDiGraph, nodes: Sequence[int]) -> List[Coord]:
    """Stitch shortest paths between consecutive node anchors."""
    stitched: List[int] = []
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        if a == b:
            if not stitched:
                stitched.append(a)
            continue
        try:
            seg_nodes = nx.shortest_path(G, a, b, weight="length")
        except Exception:
            # Fallback: direct jump between nodes if routing fails
            seg_nodes = [a, b]
        if not stitched:
            stitched.extend(seg_nodes)
        else:
            stitched.extend(seg_nodes[1:])

    if not stitched and nodes:
        stitched = [nodes[0]]

    coords: List[Coord] = []
    for nid in stitched:
        n = G.nodes[nid]
        coords.append((float(n["x"]), float(n["y"])))
    return dedupe_consecutive(coords)


def snap_trip_path(
    G: nx.MultiDiGraph,
    path: Sequence[Sequence[float]],
    max_anchors: int = 20,
) -> List[List[float]]:
    original: List[Coord] = [
        (float(p[0]), float(p[1])) for p in path if isinstance(p, (list, tuple)) and len(p) >= 2
    ]
    if len(original) < 2:
        return [[p[0], p[1]] for p in original]

    # Build anchor points to keep routing cost bounded while preserving shape.
    if len(original) <= max_anchors:
        anchors = original
    else:
        idx = np.linspace(0, len(original) - 1, max_anchors, dtype=int)
        anchors = [original[i] for i in idx]

    # Always keep first/last and remove consecutive duplicates
    anchors = dedupe_consecutive([original[0], *anchors[1:-1], original[-1]])

    anchor_nodes = []
    for lon, lat in anchors:
        try:
            node = ox.distance.nearest_nodes(G, X=lon, Y=lat)
            anchor_nodes.append(int(node))
        except Exception:
            continue

    anchor_nodes = dedupe_consecutive(anchor_nodes)
    if len(anchor_nodes) < 2:
        # fallback: snap each original point to nearest node and use that polyline
        snapped_nodes = []
        for lon, lat in original:
            try:
                snapped_nodes.append(int(ox.distance.nearest_nodes(G, X=lon, Y=lat)))
            except Exception:
                continue
        snapped_nodes = dedupe_consecutive(snapped_nodes)
        if not snapped_nodes:
            return [[p[0], p[1]] for p in original]
        if len(snapped_nodes) == 1:
            n = G.nodes[snapped_nodes[0]]
            return [[float(n["x"]), float(n["y"])] for _ in range(len(original))]
        routed = route_between_nodes(G, snapped_nodes)
        return resample_polyline(routed, len(original))

    routed = route_between_nodes(G, anchor_nodes)
    if len(routed) < 2:
        return [[p[0], p[1]] for p in original]

    return resample_polyline(routed, len(original))


def iter_agent_files(input_dir: Path) -> Iterable[Path]:
    for p in sorted(input_dir.glob("*.json")):
        if p.name.startswith("agent_") or p.name.startswith("updated_agent_"):
            yield p


def main() -> None:
    parser = argparse.ArgumentParser(description="Snap agent paths to OSM streets")
    parser.add_argument("--input-dir", default="src/simulation_output", help="Folder with agent JSON files")
    parser.add_argument("--place", default="Andorra la Vella, Andorra", help="OSM place query")
    parser.add_argument(
        "--network-type",
        default="walk",
        choices=["walk", "drive", "bike", "all", "all_private", "drive_service"],
        help="OSMnx network type",
    )
    parser.add_argument("--max-files", type=int, default=0, help="For testing: process only first N files")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input dir does not exist: {input_dir}")

    print(f"Downloading OSM network for {args.place} ({args.network_type})...")
    G = ox.graph_from_place(args.place, network_type=args.network_type, simplify=True)
    G = ox.project_graph(G)
    G = ox.project_graph(G, to_crs="EPSG:4326")
    print(f"Network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")

    files = list(iter_agent_files(input_dir))
    if args.max_files > 0:
        files = files[: args.max_files]

    changed_files = 0
    changed_trips = 0

    for i, path in enumerate(files, 1):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        file_changed = False
        trips = data.get("trips", []) if isinstance(data, dict) else []
        for trip in trips:
            if not isinstance(trip, dict):
                continue
            old_path = trip.get("path")
            if not isinstance(old_path, list) or len(old_path) < 2:
                continue

            new_path = snap_trip_path(G, old_path)
            if len(new_path) == len(old_path) and new_path != old_path:
                trip["path"] = new_path
                file_changed = True
                changed_trips += 1

        if file_changed:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            changed_files += 1

        if i % 20 == 0:
            print(f"Processed {i}/{len(files)} files...")

    print(f"Done. Changed files: {changed_files}, changed trips: {changed_trips}")


if __name__ == "__main__":
    main()
