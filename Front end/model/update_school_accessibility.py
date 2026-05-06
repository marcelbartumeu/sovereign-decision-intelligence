"""
update_school_accessibility.py

Propagates the corrected school dataset (Schools_Marcel/schools.gpkg) through
all downstream components:

  1. andorra h3/schools.gpkg              – replace with corrected version
  2. andorra h3/level_of_service_streets.gpkg – upgrade streets near new schools
  3. andorra h3/population.gpkg           – upgrade hex accessibility near new schools
  4. Front end/model/accessibility_schools.geojson  – re-export (28 schools)
  5. Front end/model/accessibility_streets.geojson  – re-export updated streets
  6. Front end/model/accessibility_population.geojson – re-export updated hexes
  7. Front end/dashboard/public/accessibility_streets.geojson   – sync to public
  8. Front end/dashboard/public/accessibility_population.geojson – sync to public

Buffer methodology (reverse-engineered from existing population.gpkg):
  walk threshold : 900 m   (max observed walk-hex → nearest school: 861 m)
  bike threshold : 2200 m  (max observed bike-hex → nearest school: 2240 m)
  Upgrades only (walk ≥ bike ≥ bus/car); never downgrades existing classifications.
"""

import json, shutil
from pathlib import Path

import geopandas as gpd
from shapely.ops import unary_union

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).resolve().parent.parent.parent   # ANDORRA V1.4/
MODEL_DIR      = ROOT / "Front end" / "model"
PUBLIC_DIR     = ROOT / "Front end" / "dashboard" / "public"
H3_DIR         = ROOT / "andorra h3"
NEW_SCHOOLS    = ROOT / "Schools_Marcel" / "schools.gpkg"

WALK_M  = 900.0
BIKE_M  = 2200.0
PRIORITY = {"walk": 3, "bike": 2, "bus/car": 1}   # higher = better

# ── helpers ────────────────────────────────────────────────────────────────────

def best_accessibility(current, candidate):
    """Return whichever accessibility class is higher priority."""
    if PRIORITY.get(candidate, 0) > PRIORITY.get(current, 0):
        return candidate
    return current

# ── 1. Replace schools.gpkg ────────────────────────────────────────────────────

print("Step 1: Updating andorra h3/schools.gpkg from Schools_Marcel")
old_schools = gpd.read_file(H3_DIR / "schools.gpkg")
new_schools = gpd.read_file(NEW_SCHOOLS)

old_n, new_n = len(old_schools), len(new_schools)
print(f"  Old: {old_n} schools  →  New: {new_n} schools  (+{new_n - old_n})")

# Identify added schools for reporting
old_coords = set(zip(old_schools.geometry.x.round(1), old_schools.geometry.y.round(1)))
added = []
for _, row in new_schools.iterrows():
    key = (round(row.geometry.x, 1), round(row.geometry.y, 1))
    if key not in old_coords:
        wgs = new_schools.to_crs("EPSG:4326").iloc[row.name]
        added.append({"name": row["name"], "lat": wgs.geometry.y, "lng": wgs.geometry.x})
        print(f"  + {row['name']}  lat={wgs.geometry.y:.5f} lng={wgs.geometry.x:.5f}")

shutil.copy2(NEW_SCHOOLS, H3_DIR / "schools.gpkg")
print("  Copied to andorra h3/schools.gpkg")

# ── 2. Compute buffers around NEW schools only ─────────────────────────────────

print("\nStep 2: Computing walk/bike buffers around new schools")
# Work in EPSG:32631 (metric, same CRS as all source files)
new_schools_proj = new_schools.to_crs("EPSG:32631")
old_schools_proj = old_schools.to_crs("EPSG:32631")

# Only buffer the genuinely new schools
new_geoms = []
for _, row in new_schools_proj.iterrows():
    key = (round(row.geometry.x, 1), round(row.geometry.y, 1))
    if key not in old_coords:
        new_geoms.append(row.geometry)

if not new_geoms:
    print("  No new schools detected — nothing to update.")
    exit(0)

new_union    = unary_union(new_geoms)
walk_buffer  = new_union.buffer(WALK_M)
bike_buffer  = new_union.buffer(BIKE_M)
print(f"  {len(new_geoms)} new school(s)  →  walk buffer {WALK_M:.0f}m, bike buffer {BIKE_M:.0f}m")

# ── 3. Upgrade level_of_service_streets.gpkg ──────────────────────────────────

print("\nStep 3: Upgrading street accessibility in level_of_service_streets.gpkg")
streets = gpd.read_file(H3_DIR / "level_of_service_streets.gpkg")
before_walk = (streets["accessibility"] == "walk").sum()
before_bike = (streets["accessibility"] == "bike").sum()

# Upgrade streets whose centroid falls within the new buffers
street_centroids = streets.geometry.centroid

in_walk = street_centroids.within(walk_buffer)
in_bike = street_centroids.within(bike_buffer) & ~in_walk

upgraded_walk = (in_walk & (streets["accessibility"] != "walk")).sum()
upgraded_bike = (in_bike & (streets["accessibility"] == "bus/car")).sum()

streets.loc[in_walk, "accessibility"] = streets.loc[in_walk, "accessibility"].apply(
    lambda x: best_accessibility(x, "walk")
)
streets.loc[in_bike, "accessibility"] = streets.loc[in_bike, "accessibility"].apply(
    lambda x: best_accessibility(x, "bike")
)

after_walk = (streets["accessibility"] == "walk").sum()
after_bike = (streets["accessibility"] == "bike").sum()
print(f"  Walk streets:  {before_walk} → {after_walk}  (+{after_walk - before_walk})")
print(f"  Bike streets:  {before_bike} → {after_bike}  (+{after_bike - before_bike})")

streets.to_file(H3_DIR / "level_of_service_streets.gpkg", driver="GPKG")
print("  Saved level_of_service_streets.gpkg")

# ── 4. Upgrade population.gpkg hex accessibility ──────────────────────────────

print("\nStep 4: Upgrading H3 hex accessibility in population.gpkg")
pop = gpd.read_file(H3_DIR / "population.gpkg")
before_walk_h = (pop["accessibility"] == "walk").sum()
before_bike_h = (pop["accessibility"] == "bike").sum()

hex_centroids = pop.geometry.centroid
in_walk_h = hex_centroids.within(walk_buffer)
in_bike_h = hex_centroids.within(bike_buffer) & ~in_walk_h

pop.loc[in_walk_h, "accessibility"] = pop.loc[in_walk_h, "accessibility"].apply(
    lambda x: best_accessibility(x, "walk")
)
pop.loc[in_bike_h, "accessibility"] = pop.loc[in_bike_h, "accessibility"].apply(
    lambda x: best_accessibility(x, "bike")
)

after_walk_h = (pop["accessibility"] == "walk").sum()
after_bike_h = (pop["accessibility"] == "bike").sum()
print(f"  Walk hexes:  {before_walk_h} → {after_walk_h}  (+{after_walk_h - before_walk_h})")
print(f"  Bike hexes:  {before_bike_h} → {after_bike_h}  (+{after_bike_h - before_bike_h})")

pop.to_file(H3_DIR / "population.gpkg", driver="GPKG")
print("  Saved population.gpkg")

# Recompute population stats
total_pop  = pop["population"].sum()
walk_pop   = pop.loc[pop["accessibility"] == "walk",    "population"].sum()
bike_pop   = pop.loc[pop["accessibility"] == "bike",    "population"].sum()
buscar_pop = pop.loc[pop["accessibility"] == "bus/car", "population"].sum()
print(f"\n  Updated accessibility stats (population):")
print(f"    walk:    {walk_pop:,.0f}  ({walk_pop/total_pop*100:.2f}%)")
print(f"    bike:    {bike_pop:,.0f}  ({bike_pop/total_pop*100:.2f}%)")
print(f"    bus/car: {buscar_pop:,.0f}  ({buscar_pop/total_pop*100:.2f}%)")
print(f"    total:   {total_pop:,.0f}")

# ── 5. Re-export accessibility_schools.geojson ────────────────────────────────

print("\nStep 5: Exporting accessibility_schools.geojson (28 schools)")
schools_wgs = new_schools.to_crs("EPSG:4326")
school_features = []
for _, row in schools_wgs.iterrows():
    school_features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [round(row.geometry.x, 6), round(row.geometry.y, 6)]
        },
        "properties": {
            "name":   row.get("name") or "School",
            "amenity": row.get("amenity") or "school",
        }
    })

schools_geojson = {"type": "FeatureCollection", "features": school_features}
(MODEL_DIR / "accessibility_schools.geojson").write_text(
    json.dumps(schools_geojson, separators=(",", ":"))
)
print(f"  Wrote {len(school_features)} schools to model/accessibility_schools.geojson")

# ── 6. Re-export accessibility_streets.geojson ────────────────────────────────

print("\nStep 6: Exporting accessibility_streets.geojson")
streets_wgs = streets.to_crs("EPSG:4326")
street_features = []
for _, row in streets_wgs.iterrows():
    try:
        geom = row.geometry.__geo_interface__
    except Exception:
        continue
    # Round coordinates to 5dp to keep file size manageable
    street_features.append({
        "type": "Feature",
        "geometry": geom,
        "properties": {"accessibility": row["accessibility"]}
    })

streets_out = {"type": "FeatureCollection", "features": street_features}
model_streets = MODEL_DIR / "accessibility_streets.geojson"
model_streets.write_text(json.dumps(streets_out, separators=(",", ":")))
print(f"  Wrote {len(street_features)} streets to model/accessibility_streets.geojson")

# ── 7. Re-export accessibility_population.geojson ─────────────────────────────

print("\nStep 7: Exporting accessibility_population.geojson")
pop_wgs = pop.to_crs("EPSG:4326")
pop_features = []
for _, row in pop_wgs.iterrows():
    try:
        geom = row.geometry.__geo_interface__
    except Exception:
        continue
    pop_val = None if (row["population"] != row["population"]) else row["population"]
    pop_features.append({
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "h3_cell":       row["h3_cell"],
            "accessibility": row["accessibility"],
            "population":    pop_val,
        }
    })

pop_out = {"type": "FeatureCollection", "features": pop_features}
model_pop = MODEL_DIR / "accessibility_population.geojson"
model_pop.write_text(json.dumps(pop_out, separators=(",", ":")))
print(f"  Wrote {len(pop_features)} hexes to model/accessibility_population.geojson")

# ── 8. Sync to dashboard/public ───────────────────────────────────────────────

print("\nStep 8: Syncing to dashboard/public")

shutil.copy2(model_streets, PUBLIC_DIR / "accessibility_streets.geojson")
print("  Copied accessibility_streets.geojson")

shutil.copy2(model_pop,     PUBLIC_DIR / "accessibility_population.geojson")
print("  Copied accessibility_population.geojson")

# No schools geojson in public (not served to frontend), but export anyway for completeness
shutil.copy2(MODEL_DIR / "accessibility_schools.geojson",
             PUBLIC_DIR / "accessibility_schools.geojson")
print("  Copied accessibility_schools.geojson")

# ── Summary ────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("Update complete.")
print(f"  Schools: {old_n} → {new_n} (+{new_n - old_n} added)")
print(f"  Walk hexes: {before_walk_h} → {after_walk_h}")
print(f"  Bike hexes: {before_bike_h} → {after_bike_h}")
print()
print("Files updated:")
for f in [
    "andorra h3/schools.gpkg",
    "andorra h3/level_of_service_streets.gpkg",
    "andorra h3/population.gpkg",
    "Front end/model/accessibility_schools.geojson",
    "Front end/model/accessibility_streets.geojson",
    "Front end/model/accessibility_population.geojson",
    "Front end/dashboard/public/accessibility_streets.geojson",
    "Front end/dashboard/public/accessibility_population.geojson",
    "Front end/dashboard/public/accessibility_schools.geojson",
]:
    print(f"  ✓ {f}")
print()
print("Next: rebuild the dashboard with `npm run build`")
