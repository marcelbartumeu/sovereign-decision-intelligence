"""
Convert the generated Andorran population into the viz app's TripsLayer format.

Input:
  results/andorra_population/population.json  — 90K agent profiles
  results/andorra_population/schedules_routed.json (preferred) or schedules.json
  Front end/dashboard/public/model/accessibility_population.geojson — H3 centroids

Output:
  Front end/dashboard/public/model/andorra_trips.json — compact TripsLayer dataset

Format per agent:
  {
    "id":       "POP-00000",
    "nat":      "Andorran",         // nationality (for filter)
    "inc":      "middle",           // income_bracket (for filter)
    "emotion":  "ENJOYMENT",        // dominant emotion from profile
    "color":    [52, 211, 153],     // RGB for trail + dot
    "path":     [[lon,lat], ...],   // full day trajectory (all trips concatenated)
    "ts":       [minutes, ...]      // one timestamp per path point (0–1440 min)
  }

schedules_routed.json can be large — loaded with ijson streaming (one agent at a time)
to avoid out-of-memory. Output is written incrementally.
"""

import json
import math
from pathlib import Path

import ijson
import numpy as np
from scipy.spatial import KDTree

ROOT          = Path(__file__).parents[2]
POP_DIR       = Path(__file__).parent / "results" / "andorra_population"
# V2.2: the Vercel root dir was renamed "Front end/dashboard" → "app".
MODEL_DIR     = ROOT / "app" / "public" / "model"
GEOJSON_PATH  = MODEL_DIR / "accessibility_population.geojson"
STREETS_PATH  = MODEL_DIR / "accessibility_streets.geojson"
OUT_PATH      = MODEL_DIR / "andorra_trips.json"
# The viz fetches CHUNKS chunked files (andorra_trips_{i}.json); keep in sync with
# SharedStateContext.tsx CHUNKS.
CHUNKS        = 6

MAX_PTS_PER_TRIP = 40   # subsample routed paths to keep JSON browser-friendly
MAX_SNAP_KM      = 1.5  # same threshold used by route_trips.py


# ── Emotion derivation ────────────────────────────────────────────────────────

EMOTION_NAMES = ["ANGER", "CONTEMPT", "DISGUST", "ENJOYMENT", "FEAR", "SADNESS", "SURPRISE"]

EMOTION_COLORS: dict[str, list[int]] = {
    "ANGER":    [248, 113, 113],
    "CONTEMPT": [192, 132, 252],
    "DISGUST":  [251, 191, 36 ],
    "ENJOYMENT":[52,  211, 153],
    "FEAR":     [251, 146, 60 ],
    "SADNESS":  [96,  165, 250],
    "SURPRISE": [34,  211, 238],
}


def _get(d: dict, *keys, default: float = 0.5) -> float:
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return float(d)


def profile_to_emotion(profile: dict) -> tuple[str, list[int]]:
    n  = _get(profile, "personality", "neuroticism")
    e  = _get(profile, "personality", "extraversion")
    a  = _get(profile, "personality", "agreeableness")
    o  = _get(profile, "personality", "openness")
    fs = _get(profile, "economic", "financial_stress")
    la = (_get(profile, "behavioral_economics", "loss_aversion", default=2.25) - 1.0) / 3.5

    raw = [
        0.30 * n + 0.40 * fs + 0.20 * (1 - a),
        0.40 * (1 - a) + 0.20 * (1 - o),
        0.30 * (1 - o) + 0.20 * n,
        0.40 * e + 0.30 * (1 - fs) + 0.20 * a,
        0.40 * n + 0.30 * la + 0.20 * fs,
        0.30 * n + 0.30 * fs + 0.20 * (1 - e),
        0.30 * e + 0.20 * o,
    ]
    total = sum(raw) or 1.0
    mv    = [v / total for v in raw]
    dominant = EMOTION_NAMES[int(np.argmax(mv))]
    return dominant, EMOTION_COLORS[dominant]


# ── Road node snap for stay-at-home agents ────────────────────────────────────

def build_road_kd(streets_path: Path):
    """Return (node_list, KDTree) for all bus/car road endpoints."""
    with open(streets_path) as f:
        streets = json.load(f)["features"]
    SNAP = 4
    nodes: set[tuple[float, float]] = set()
    for feat in streets:
        if feat["properties"].get("accessibility") != "bus/car":
            continue
        coords = feat["geometry"]["coordinates"]
        nodes.add((round(coords[0][0], SNAP), round(coords[0][1], SNAP)))
        nodes.add((round(coords[-1][0], SNAP), round(coords[-1][1], SNAP)))
    node_list = list(nodes)
    return node_list, KDTree(np.array(node_list))


def snap_to_road(lon: float, lat: float, node_list: list, kd: KDTree) -> tuple[float, float] | None:
    """Return nearest road node if within MAX_SNAP_KM, else None."""
    d_deg, idx = kd.query([lon, lat])
    if d_deg * 111 > MAX_SNAP_KM:
        return None
    return node_list[idx]


# ── H3 grid centroid lookup ───────────────────────────────────────────────────

def load_h3_centroids(geojson_path: Path) -> dict[str, tuple[float, float]]:
    with open(geojson_path) as f:
        data = json.load(f)
    centroids: dict[str, tuple[float, float]] = {}
    for feat in data["features"]:
        p = feat["properties"]
        if not p.get("population"):
            continue
        coords = feat["geometry"]["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        centroids[p["h3_cell"]] = (sum(lons) / len(lons), sum(lats) / len(lats))
    return centroids


# ── Path helpers ──────────────────────────────────────────────────────────────

def interpolate_path(
    origin: tuple[float, float],
    dest: tuple[float, float],
    n_points: int,
    rng: np.random.Generator,
) -> list[tuple[float, float]]:
    if n_points < 2:
        return [origin, dest]
    dx   = dest[0] - origin[0]
    dy   = dest[1] - origin[1]
    dist = math.sqrt(dx * dx + dy * dy)
    perp_x = -dy / (dist + 1e-9)
    perp_y =  dx / (dist + 1e-9)
    offset  = rng.uniform(-0.08, 0.08) * dist
    pts = []
    for i in range(n_points):
        t   = i / (n_points - 1)
        bx  = origin[0] + t * dx
        by  = origin[1] + t * dy
        bow = 4 * t * (1 - t)
        pts.append((bx + perp_x * offset * bow, by + perp_y * offset * bow))
    return pts


def subsample(pts: list, max_pts: int) -> list:
    """Uniformly subsample a list to at most max_pts items, always keeping endpoints."""
    n = len(pts)
    if n <= max_pts:
        return pts
    indices = [round(i * (n - 1) / (max_pts - 1)) for i in range(max_pts)]
    return [pts[i] for i in indices]


# ── Main conversion ───────────────────────────────────────────────────────────

def convert(rng_seed: int = 42) -> None:
    rng = np.random.default_rng(rng_seed)

    print("Loading H3 centroids...", end=" ", flush=True)
    h3_centroids = load_h3_centroids(GEOJSON_PATH)
    print(f"{len(h3_centroids):,} cells")

    print("Building road snap index...", end=" ", flush=True)
    road_nodes, road_kd = build_road_kd(STREETS_PATH)
    print(f"{len(road_nodes):,} nodes")

    print("Loading population...", end=" ", flush=True)
    with open(POP_DIR / "population.json") as f:
        population: list[dict] = json.load(f)
    profile_by_id = {p["agent_id"]: p for p in population}
    del population
    print(f"{len(profile_by_id):,} agents")

    routed_file = POP_DIR / "schedules_routed.json"
    sched_file  = routed_file if routed_file.exists() else POP_DIR / "schedules.json"
    using_routed = routed_file.exists()
    print(f"Streaming {sched_file.name} [routed={using_routed}]...")

    converted = 0
    skipped   = 0

    with open(OUT_PATH, "w") as out_f:
        out_f.write("[")
        first_written = True

        with open(sched_file, "rb") as sched_f:
            for i, sched in enumerate(ijson.items(sched_f, "item", use_float=True)):
                agent_id = sched.get("agent_id", "")
                profile  = profile_by_id.get(agent_id)
                if not profile:
                    skipped += 1
                    continue

                trips        = sched.get("trips", [])
                routed_paths = sched.get("routed_paths", [])
                emotion, color = profile_to_emotion(profile)

                if not trips:
                    home_h3  = sched.get("home_h3", "")
                    home_pos = h3_centroids.get(home_h3)
                    if not home_pos:
                        skipped += 1
                        continue
                    # Snap to nearest road node — raw H3 centroid may be on a mountain
                    snapped = snap_to_road(home_pos[0], home_pos[1], road_nodes, road_kd)
                    if snapped is None:
                        skipped += 1
                        continue
                    lon, lat = snapped
                    record = {
                        "id":      agent_id,
                        "nat":     profile.get("nationality", "Other"),
                        "inc":     profile.get("income_bracket", "middle"),
                        "emotion": emotion,
                        "color":   color,
                        "path":    [[round(lon, 5), round(lat, 5)], [round(lon, 5), round(lat, 5)]],
                        "ts":      [0.0, 1439.0],
                    }
                    if not first_written:
                        out_f.write(",")
                    out_f.write(json.dumps(record, separators=(",", ":")))
                    first_written = False
                    converted += 1
                    continue

                full_path: list[list[float]] = []
                full_ts:   list[float]       = []
                bounds:    list[int]         = []   # start index of each trip in full_path

                # Trips do NOT always chain (dest_i != origin_{i+1}) and can overlap
                # in time, so they cannot be flattened into one continuous path.
                # Sort by departure and keep each trip as its OWN segment (recorded
                # in `bounds`); the viz renders/animates each trip separately rather
                # than drawing straight teleport lines between them.
                rps    = list(routed_paths) + [None] * max(0, len(trips) - len(routed_paths))
                paired = sorted(zip(trips, rps), key=lambda tr: tr[0].get("departure_min", 0.0))

                for trip, routed in paired:
                    o_h3 = trip.get("origin_h3",  "")
                    d_h3 = trip.get("dest_h3",    "")
                    dep  = trip.get("departure_min", 0.0)
                    dur  = trip.get("duration_min",  5.0)

                    if routed and len(routed) >= 2:
                        raw_pts = [tuple(c) for c in routed]
                        pts = subsample(raw_pts, MAX_PTS_PER_TRIP)
                    else:
                        origin = h3_centroids.get(o_h3)
                        dest   = h3_centroids.get(d_h3)
                        if not origin or not dest:
                            continue
                        n_pts = max(3, int(dur / 2))
                        pts   = interpolate_path(origin, dest, n_pts, rng)

                    ts = np.linspace(dep, dep + dur, len(pts)).tolist()
                    bounds.append(len(full_path))
                    full_path.extend([list(p) for p in pts])
                    full_ts.extend(ts)

                if len(full_path) < 2:
                    skipped += 1
                    continue

                full_path = [[round(p[0], 5), round(p[1], 5)] for p in full_path]
                full_ts   = [round(t, 1) for t in full_ts]

                record = {
                    "id":      agent_id,
                    "nat":     profile.get("nationality", "Other"),
                    "inc":     profile.get("income_bracket", "middle"),
                    "emotion": emotion,
                    "color":   color,
                    "path":    full_path,
                    "ts":      full_ts,
                    "bounds":  bounds,
                }
                if not first_written:
                    out_f.write(",")
                out_f.write(json.dumps(record, separators=(",", ":")))
                first_written = False
                converted += 1

                if (i + 1) % 10000 == 0:
                    print(f"  {i+1:,} / 90,000  converted={converted:,}", end="\r", flush=True)

        out_f.write("]")

    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"\n  Converted: {converted:,}  Skipped: {skipped}")
    print(f"Wrote {OUT_PATH.name}  {size_mb:.1f} MB")
    print("Done.")


def split_into_chunks(n_chunks: int = CHUNKS) -> None:
    """Stream the single andorra_trips.json into n_chunks round-robin chunk files
    (andorra_trips_{i}.json) — the format the viz actually fetches
    (SharedStateContext.tsx, CHUNKS). Uses ijson so memory stays flat."""
    print(f"\nSplitting {OUT_PATH.name} → {n_chunks} chunks...")
    chunk_paths = [MODEL_DIR / f"andorra_trips_{c}.json" for c in range(n_chunks)]
    files = [open(p, "w") for p in chunk_paths]
    first = [True] * n_chunks
    for cf in files:
        cf.write("[")
    n = 0
    try:
        with open(OUT_PATH, "rb") as f:
            for rec in ijson.items(f, "item", use_float=True):
                c = n % n_chunks
                if not first[c]:
                    files[c].write(",")
                files[c].write(json.dumps(rec, separators=(",", ":")))
                first[c] = False
                n += 1
    finally:
        for cf in files:
            cf.write("]")
            cf.close()
    total_mb = sum(p.stat().st_size for p in chunk_paths) / 1e6
    print(f"  {n:,} agents → {n_chunks} chunks ({total_mb:.1f} MB) in {MODEL_DIR}")


if __name__ == "__main__":
    convert()
    split_into_chunks()
