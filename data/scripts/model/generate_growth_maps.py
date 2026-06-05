"""
generate_growth_maps.py

Generates spatially realistic growth allocation maps for Andorra using a
multi-factor suitability model grounded in physical geography, existing
population density, and spatial autocorrelation.

Buildability constraints (hexes that CANNOT receive new population):
  1. Protected natural areas  — fetched from OpenStreetMap Overpass API
  2. Slope > 37°              — computed from SRTM 30m elevation data
  3. Altitude > 2400 m        — above sustained habitability threshold

Suitability model (replaces accessibility-class weighting):
  Four additive/multiplicative factors determine where growth is allocated:

  T(i) – Topographic suitability
      T(i) = exp(-slope_i / 15) * alt_score(i)
      where alt_score decays linearly from 1.0 at 800 m to 0.0 at 2400 m.
      Valley floors along the Valira corridor naturally score highest.

  G(i) – Population gravity (local spatial autocorrelation)
      G(i) = sum over k=1..3: ring_pop(i,k) * weight(k)
      ring weights: k=1 → 3, k=2 → 2, k=3 → 1 (inverse-distance)
      Cells adjacent to dense settlements attract proportionally more growth.

  A(i) – Adjacency expansion bonus
      A(i) = 1 if any ring-1 neighbor has pop > 0, else 0.
      Small bonus enabling organic urban fringe expansion.

  D(i) – Existing density (infill)
      D(i) = pop_i (raw head-count; drives densification of existing cores)

Composite suitability score per scenario:
  Overgrowth  — T(i) * (W_d*D(i) + W_g*G(i) + W_a*A(i)*fringe_boost)
                All buildable valley hexes eligible; highest growth at cores.
  Continuity  — T(i) * (W_d*D(i) + W_g*G(i))  restricted to
                already-populated hexes + immediate vacant neighbours.
  Density     — T(i) * D(i)  strict infill of existing settled hexes only.
  Degrowth    — D(i) * peripherality(i) where peripherality = 1 / (1+G(i))
                Peripheral, isolated, steep hexes depopulate first.
"""

import json, math, time, sys
from pathlib import Path
from collections import defaultdict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import h3 as h3lib
    HAS_H3 = True
except ImportError:
    HAS_H3 = False

try:
    import geopandas as gpd
    from shapely.geometry import shape, Point
    HAS_GEO = True
except ImportError:
    HAS_GEO = False

HERE = Path(__file__).resolve().parent
DASHBOARD_PUBLIC = HERE.parent / "dashboard" / "public"

# ── constants ──────────────────────────────────────────────────────────────────

MAX_SLOPE_DEG  = 37.0   # steeper → not buildable
MAX_ALTITUDE_M = 2400.0  # above → not buildable (Pas de la Casa ≈ 2085 m)
ALT_FLOOR_M    = 800.0   # Andorra la Vella valley floor (lowest habitation)

# Suitability weights
W_DENSITY  = 3.0   # existing population density (infill preference)
W_GRAVITY  = 1.0   # neighbourhood gravity
W_FRINGE   = 0.15  # expansion into vacant adjacent hexes (Overgrowth / Continuity)

GRAVITY_RING_WEIGHTS = {1: 3, 2: 2, 3: 1}  # closer rings count more

# ── helpers ────────────────────────────────────────────────────────────────────

def haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def slope_deg(elev_center, elev_neighbor, dist_m):
    if dist_m == 0:
        return 0.0
    return math.degrees(math.atan(abs(elev_center - elev_neighbor) / dist_m))

def topo_score(slope, altitude):
    """
    Combined topographic suitability [0, 1].
    - Exponential decay with slope (flat = best).
    - Linear decay with altitude from ALT_FLOOR_M to MAX_ALTITUDE_M.
    """
    slope_factor = math.exp(-slope / 15.0)
    if altitude is None:
        alt_factor = 0.5  # unknown altitude → neutral
    else:
        alt_factor = max(0.0, (MAX_ALTITUDE_M - altitude) / (MAX_ALTITUDE_M - ALT_FLOOR_M))
    return slope_factor * alt_factor

# ── 1. Load data ───────────────────────────────────────────────────────────────

def load_hex_grid():
    path = HERE / "accessibility_population.geojson"
    with path.open() as f:
        return json.load(f)

def load_scenario_populations():
    path = HERE / "Scenario_Rollup.json"
    with path.open() as f:
        rollup = json.load(f)
    return {name: data["final"]["Pop"] for name, data in rollup.items()}

# ── 2. Protected areas ─────────────────────────────────────────────────────────

OVERPASS_URL   = "https://overpass-api.de/api/interpreter"
PROTECTED_CACHE = HERE / "andorra_protected_areas.geojson"

OVERPASS_QUERY = """
[out:json][timeout:60];
area["ISO3166-1"="AD"]->.andorra;
(
  way(area.andorra)["leisure"="nature_reserve"];
  way(area.andorra)["boundary"="national_park"];
  way(area.andorra)["boundary"="protected_area"];
  way(area.andorra)["landuse"="nature_reserve"];
  way(area.andorra)["landuse"="protected_area"];
  relation(area.andorra)["leisure"="nature_reserve"];
  relation(area.andorra)["boundary"="national_park"];
  relation(area.andorra)["boundary"="protected_area"];
  relation(area.andorra)["landuse"="nature_reserve"];
);
out geom;
"""

def fetch_protected_areas():
    if not HAS_GEO:
        print("  [protected] geopandas/shapely not available — skipping")
        return []

    if PROTECTED_CACHE.exists():
        age_days = (time.time() - PROTECTED_CACHE.stat().st_mtime) / 86400
        if age_days < 7:
            print(f"  [protected] Using cached data ({age_days:.1f} days old)")
            with PROTECTED_CACHE.open() as f:
                data = json.load(f)
            polys = []
            for feat in data.get("features", []):
                try:
                    polys.append(shape(feat["geometry"]))
                except Exception:
                    pass
            return polys

    print("  [protected] Fetching from Overpass API...")
    try:
        resp = requests.get(
            OVERPASS_URL,
            params={"data": OVERPASS_QUERY},
            headers={"User-Agent": "AndorraResearchDashboard/1.0"},
            timeout=90,
        )
        resp.raise_for_status()
        osm = resp.json()
    except Exception as e:
        print(f"  [protected] Overpass fetch failed: {e} — using fallback polygons")
        return _fallback_protected_polygons()

    features = []
    for elem in osm.get("elements", []):
        if elem["type"] == "way" and "geometry" in elem:
            coords = [[n["lon"], n["lat"]] for n in elem["geometry"]]
            if len(coords) >= 4 and coords[0] != coords[-1]:
                coords.append(coords[0])
            if len(coords) >= 4:
                features.append({
                    "type": "Feature",
                    "properties": {"name": elem.get("tags", {}).get("name", "")},
                    "geometry": {"type": "Polygon", "coordinates": [coords]}
                })
        elif elem["type"] == "relation":
            for member in elem.get("members", []):
                if member.get("role") == "outer" and "geometry" in member:
                    coords = [[n["lon"], n["lat"]] for n in member["geometry"]]
                    if len(coords) >= 4:
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                        features.append({
                            "type": "Feature",
                            "properties": {"name": elem.get("tags", {}).get("name", "")},
                            "geometry": {"type": "Polygon", "coordinates": [coords]}
                        })

    print(f"  [protected] Got {len(features)} protected area polygons")
    geojson = {"type": "FeatureCollection", "features": features}
    with PROTECTED_CACHE.open("w") as f:
        json.dump(geojson, f)

    polys = []
    for feat in features:
        try:
            polys.append(shape(feat["geometry"]))
        except Exception:
            pass
    return polys

def _fallback_protected_polygons():
    from shapely.geometry import Polygon
    parks = [
        Polygon([(1.408,42.579),(1.430,42.580),(1.448,42.605),(1.465,42.628),
                 (1.450,42.650),(1.415,42.657),(1.390,42.640),(1.390,42.610),(1.408,42.579)]),
        Polygon([(1.526,42.580),(1.548,42.578),(1.568,42.598),(1.572,42.620),
                 (1.555,42.635),(1.530,42.630),(1.515,42.612),(1.516,42.592),(1.526,42.580)]),
        Polygon([(1.490,42.610),(1.510,42.612),(1.515,42.628),(1.500,42.638),
                 (1.480,42.632),(1.476,42.618),(1.490,42.610)]),
        Polygon([(1.491,42.437),(1.510,42.438),(1.520,42.455),(1.508,42.468),
                 (1.490,42.466),(1.480,42.452),(1.491,42.437)]),
    ]
    print(f"  [protected] Using {len(parks)} fallback park polygons")
    return parks

# ── 3. Elevation (SRTM) ────────────────────────────────────────────────────────

ELEV_CACHE         = HERE / "andorra_elevations.json"
OPENTOPODATA_URL   = "https://api.opentopodata.org/v1/srtm30m"
BATCH_SIZE         = 100
REQUEST_DELAY      = 1.1

def fetch_elevations(cells_latlng):
    cache = {}
    if ELEV_CACHE.exists():
        with ELEV_CACHE.open() as f:
            cache = json.load(f)

    missing = [(cell, lat, lng) for cell, lat, lng in cells_latlng if cell not in cache]
    if not missing:
        print(f"  [elevation] All {len(cells_latlng)} cells cached")
        return cache

    print(f"  [elevation] Fetching {len(missing)} cells from OpenTopoData SRTM30...")
    if not HAS_REQUESTS:
        print("  [elevation] requests not available — using cache only")
        return cache

    batches = [missing[i:i+BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
    for i, batch in enumerate(batches):
        locs = "|".join(f"{lat},{lng}" for _, lat, lng in batch)
        try:
            resp = requests.get(OPENTOPODATA_URL, params={"locations": locs}, timeout=30)
            resp.raise_for_status()
            for (cell, lat, lng), result in zip(batch, resp.json().get("results", [])):
                elev = result.get("elevation")
                if elev is not None:
                    cache[cell] = elev
        except Exception as e:
            print(f"    Batch {i+1}/{len(batches)} failed: {e}")
        if i < len(batches) - 1:
            time.sleep(REQUEST_DELAY)
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(batches)} batches done ({len(cache)} cells cached)")

    with ELEV_CACHE.open("w") as f:
        json.dump(cache, f)
    print(f"  [elevation] Done. {len(cache)} cells with elevation data.")
    return cache

# ── 4. Constraint mask ─────────────────────────────────────────────────────────

def build_constraint_mask(features, protected_polys, elev_map):
    if not HAS_H3:
        print("  [constraints] h3 not available — no slope mask")
        return {}

    mask = {}
    for feat in features:
        cell     = feat["properties"]["h3_cell"]
        lat, lng = h3lib.cell_to_latlng(cell)
        altitude = elev_map.get(cell)

        max_slope = 0.0
        if altitude is not None:
            for nb in h3lib.grid_disk(cell, 1):
                if nb == cell:
                    continue
                nb_elev = elev_map.get(nb)
                if nb_elev is None:
                    continue
                nb_lat, nb_lng = h3lib.cell_to_latlng(nb)
                s = slope_deg(altitude, nb_elev, haversine_m(lat, lng, nb_lat, nb_lng))
                if s > max_slope:
                    max_slope = s

        in_protected = False
        if HAS_GEO and protected_polys:
            pt = Point(lng, lat)
            in_protected = any(p.contains(pt) for p in protected_polys)

        existing_pop = feat["properties"].get("population") or 0.0
        already_built = existing_pop > 0
        too_steep     = (altitude is not None and max_slope >= MAX_SLOPE_DEG)
        too_high      = (altitude is not None and altitude  >= MAX_ALTITUDE_M)

        if already_built:
            buildable = True
            reason    = ""
        else:
            buildable = not (in_protected or too_steep or too_high)
            reason = ""
            if in_protected: reason = "protected"
            elif too_steep:  reason = f"slope {max_slope:.0f}°"
            elif too_high:   reason = f"altitude {altitude:.0f}m"

        mask[cell] = {
            "protected":         in_protected,
            "slope":             round(max_slope, 1),
            "altitude":          round(altitude, 0) if altitude is not None else None,
            "buildable":         buildable,
            "constraint_reason": reason,
        }

    return mask

# ── 5. Neighbourhood pre-computation ──────────────────────────────────────────

def compute_neighbourhood_stats(features, elev_map):
    """
    For every hex cell, pre-compute:
      - topo:        topographic suitability score [0, 1]
      - gravity:     distance-weighted population in rings 1–3
      - adjacent:    True if any ring-1 neighbor is populated
      - ring1_cells: set of ring-1 neighbor cell IDs

    Returns dict keyed by h3_cell.
    """
    if not HAS_H3:
        return {}

    pop_map = {
        f["properties"]["h3_cell"]: (f["properties"]["population"] or 0.0)
        for f in features
    }

    stats = {}
    for feat in features:
        cell  = feat["properties"]["h3_cell"]
        slope = 0.0
        alt   = elev_map.get(cell)

        # Slope: already computed in mask; recompute here for clarity
        if alt is not None:
            lat, lng = h3lib.cell_to_latlng(cell)
            for nb in h3lib.grid_disk(cell, 1):
                if nb == cell:
                    continue
                nb_elev = elev_map.get(nb)
                if nb_elev is None:
                    continue
                nb_lat, nb_lng = h3lib.cell_to_latlng(nb)
                s = slope_deg(alt, nb_elev, haversine_m(lat, lng, nb_lat, nb_lng))
                if s > slope:
                    slope = s

        t_score = topo_score(slope, alt)

        # Gravity: weighted population in rings 1–3
        gravity = 0.0
        ring1_cells = set()
        for k, w in GRAVITY_RING_WEIGHTS.items():
            ring = h3lib.grid_ring(cell, k)
            if k == 1:
                ring1_cells = set(ring)
            gravity += sum(pop_map.get(c, 0.0) for c in ring) * w

        adjacent = any(pop_map.get(c, 0.0) > 0 for c in ring1_cells)

        stats[cell] = {
            "topo":        t_score,
            "gravity":     gravity,
            "adjacent":    adjacent,
            "ring1_cells": ring1_cells,
            "pop":         pop_map[cell],
            "slope":       slope,
            "altitude":    alt,
        }

    return stats

# ── 6. Suitability scores ──────────────────────────────────────────────────────

def compute_scores(features, mask, nbr):
    """
    Returns a dict of per-scenario score arrays.

    For each scenario, scores[i] is the suitability of feature i
    to receive (or lose) population.  Non-buildable cells always get 0.
    """
    n = len(features)
    scores = {sc: [0.0] * n for sc in ("Overgrowth", "Continuity", "Density", "Degrowth")}

    for i, feat in enumerate(features):
        cell     = feat["properties"]["h3_cell"]
        pop      = (feat["properties"]["population"] or 0.0)
        bld      = mask.get(cell, {}).get("buildable", True)
        nb       = nbr.get(cell, {})
        t        = nb.get("topo", 0.5)
        grav     = nb.get("gravity", 0.0)
        adjacent = nb.get("adjacent", False)

        # ── Overgrowth ─────────────────────────────────────────────────────────
        # Growth spreads across all buildable valley hexes.
        # Existing density + neighbourhood gravity drive allocation;
        # a fringe bonus enables organic expansion into adjacent vacant land.
        if bld:
            if pop > 0:
                s = t * (W_DENSITY * pop + W_GRAVITY * grav)
            elif adjacent:
                s = t * W_FRINGE * (1.0 + W_GRAVITY * grav)
            else:
                s = 0.0  # isolated vacant land: no speculative growth
            scores["Overgrowth"][i] = max(0.0, s)

        # ── Continuity ─────────────────────────────────────────────────────────
        # Infill of existing settlement plus modest expansion into
        # immediately adjacent vacant buildable hexes.
        # Isolated greenfield is excluded.
        if bld:
            if pop > 0:
                s = t * (W_DENSITY * pop + W_GRAVITY * grav)
            elif adjacent:
                # Weaker expansion than Overgrowth
                s = t * (W_FRINGE * 0.4) * (1.0 + W_GRAVITY * grav * 0.5)
            else:
                s = 0.0
            scores["Continuity"][i] = max(0.0, s)

        # ── Density ────────────────────────────────────────────────────────────
        # Strict infill only: already-populated cells, proportional
        # to existing density and topographic quality.
        # No footprint expansion.
        if bld and pop > 0:
            scores["Density"][i] = max(0.0, t * W_DENSITY * pop)

        # ── Degrowth ───────────────────────────────────────────────────────────
        # Population contracts preferentially from:
        #   - peripheral cells (low gravity)
        #   - topographically difficult cells (steep or high)
        #   - isolated settlements
        # Score here is the CONTRACTION weight (higher → loses more population).
        if pop > 0:
            peripherality = 1.0 / (1.0 + grav / 100.0)  # normalise gravity
            difficulty    = 1.0 - t                        # steep/high → high difficulty
            scores["Degrowth"][i] = max(0.0, pop * (0.5 * peripherality + 0.5 * difficulty))

    return scores

# ── 7. Allocate population delta ───────────────────────────────────────────────

def allocate(features, scores, delta_total, scenario):
    sc_scores = scores[scenario]
    total = sum(sc_scores) or 1.0
    return [s / total * delta_total for s in sc_scores]

# ── 8. Main ────────────────────────────────────────────────────────────────────

def main():
    grid            = load_hex_grid()
    scenario_pops   = load_scenario_populations()
    features        = grid["features"]
    total_pop_2024  = sum(f["properties"]["population"] or 0.0 for f in features)
    print(f"H3 grid: {len(features)} hexes, total pop 2024 = {total_pop_2024:,.0f}")

    # --- Step 1: Protected areas ---
    print("Step 1: Protected natural areas")
    protected_polys = fetch_protected_areas()

    # --- Step 2: Elevations ---
    print("Step 2: Elevation data (SRTM 30m)")
    if HAS_H3:
        cells_latlng = [
            (f["properties"]["h3_cell"], *h3lib.cell_to_latlng(f["properties"]["h3_cell"]))
            for f in features
        ]
        elev_map = fetch_elevations(cells_latlng)
    else:
        print("  h3 not available — skipping elevation")
        elev_map = {}

    # --- Step 3: Constraint mask ---
    print("Step 3: Building constraint mask (slope + altitude + protected)")
    mask = build_constraint_mask(features, protected_polys, elev_map)
    n_protected   = sum(1 for v in mask.values() if v["protected"])
    n_steep       = sum(1 for v in mask.values() if v["slope"] >= MAX_SLOPE_DEG)
    n_high        = sum(1 for v in mask.values() if v.get("altitude") and v["altitude"] >= MAX_ALTITUDE_M)
    n_unbuildable = sum(1 for v in mask.values() if not v["buildable"])
    print(f"  Protected: {n_protected}  Steep (>{MAX_SLOPE_DEG:.0f}°): {n_steep}"
          f"  High (>{MAX_ALTITUDE_M:.0f}m): {n_high}  Total unbuildable: {n_unbuildable}/{len(mask)}")

    # Write constraint layer for the frontend
    constraint_features = []
    for feat in features:
        cell = feat["properties"]["h3_cell"]
        c    = mask.get(cell, {})
        if not c.get("buildable", True) and not (feat["properties"]["population"] or 0):
            constraint_features.append({
                "type": "Feature",
                "geometry": feat["geometry"],
                "properties": {
                    "h3_cell":   cell,
                    "reason":    c.get("constraint_reason", "unknown"),
                    "slope":     c.get("slope", 0),
                    "altitude":  c.get("altitude"),
                    "protected": c.get("protected", False),
                }
            })
    (DASHBOARD_PUBLIC / "growth_constraints.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": constraint_features}, separators=(",", ":"))
    )
    print(f"  Wrote {len(constraint_features)} constraint hexes to growth_constraints.geojson")

    # --- Step 4: Neighbourhood stats (gravity, topo, adjacency) ---
    print("Step 4: Computing neighbourhood suitability stats")
    nbr = compute_neighbourhood_stats(features, elev_map)
    topo_vals   = [nbr[f["properties"]["h3_cell"]]["topo"] for f in features if f["properties"]["h3_cell"] in nbr]
    grav_vals   = [nbr[f["properties"]["h3_cell"]]["gravity"] for f in features if f["properties"]["h3_cell"] in nbr]
    n_adjacent  = sum(1 for v in nbr.values() if v["adjacent"] and v["pop"] == 0)
    print(f"  Topo score range: {min(topo_vals):.3f} – {max(topo_vals):.3f}  mean={sum(topo_vals)/len(topo_vals):.3f}")
    print(f"  Gravity range: {min(grav_vals):.0f} – {max(grav_vals):.0f}")
    print(f"  Vacant hexes adjacent to settlement: {n_adjacent}")

    # --- Step 5: Suitability scores ---
    print("Step 5: Computing multi-factor suitability scores")
    scores = compute_scores(features, mask, nbr)
    for sc in ("Overgrowth", "Continuity", "Density", "Degrowth"):
        eligible = sum(1 for s in scores[sc] if s > 0)
        print(f"  {sc}: {eligible} eligible hexes")

    # --- Step 6: Allocate per scenario ---
    print("Step 6: Allocating growth per scenario")
    for scenario, pop_2049 in scenario_pops.items():
        delta_total = pop_2049 - total_pop_2024
        deltas      = allocate(features, scores, delta_total, scenario)

        out_features = []
        for feat, d in zip(features, deltas):
            props   = feat["properties"]
            pop_now = props["population"] or 0.0
            pop_fut = max(0.0, pop_now + d)
            cell    = props["h3_cell"]
            c       = mask.get(cell, {})
            nb      = nbr.get(cell, {})

            out_features.append({
                "type": "Feature",
                "geometry": feat["geometry"],
                "properties": {
                    "h3_cell":    cell,
                    "pop_2024":   round(pop_now, 2),
                    "pop_2049":   round(pop_fut, 2),
                    "delta":      round(d, 2),
                    "buildable":  c.get("buildable", True),
                    "slope":      c.get("slope", 0),
                    "altitude":   c.get("altitude"),
                    "protected":  c.get("protected", False),
                    "constraint": c.get("constraint_reason", ""),
                    "topo_score": round(nb.get("topo", 0), 3),
                    "gravity":    round(nb.get("gravity", 0), 1),
                },
            })

        out_path = DASHBOARD_PUBLIC / f"growth_{scenario.lower()}.geojson"
        out_path.write_text(json.dumps({"type": "FeatureCollection", "features": out_features}, separators=(",", ":")))

        pop_check = sum(f["properties"]["pop_2049"] for f in out_features)
        print(f"  {scenario}: pop 2049 = {pop_check:,.0f}  (target {pop_2049:,.0f})  delta = {delta_total:+,.0f}")

    print("Done.")

if __name__ == "__main__":
    main()
