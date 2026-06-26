"""
Generate the 4-panel spatial growth figure (Figure `fig:spatial`) for the paper,
plus the spatial-signature metrics reported in Table `tab:spatial`.

Reads the committed per-scenario growth allocations (app/public/growth_*.geojson)
and writes paper/spatial_growth_2049.png. Run: python3 generate_spatial_figure.py
"""
from pathlib import Path
import json
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[3]          # repo root (ANDORRA V2.1)
PUB = ROOT / "app" / "public"
OUT = ROOT / "paper" / "spatial_growth_2049.png"
SCEN = [("continuity", "Continuity"), ("overgrowth", "Overgrowth"),
        ("degrowth", "Degrowth"), ("density", "Density")]

# ---- spatial-signature metrics (Table tab:spatial) ----
print(f"{'scenario':<12}{'grow':>6}{'new':>6}{'shrink':>7}{'infill%':>8}{'top10%':>8}{'slope*':>7}")
for s, _ in SCEN:
    P = [f["properties"] for f in json.load((PUB / f"growth_{s}.geojson").open())["features"]]
    grow = [p for p in P if p["delta"] > 0]
    shrink = [p for p in P if p["delta"] < 0]
    new = [p for p in grow if (p["pop_2024"] or 0) == 0]
    posg = sum(p["delta"] for p in grow) or 1
    infill = sum(p["delta"] for p in grow if (p["pop_2024"] or 0) > 0) / posg * 100
    ds = sorted((p["delta"] for p in grow), reverse=True)
    top10 = sum(ds[:max(1, len(ds) // 10)]) / posg * 100
    ms = sum(p["delta"] * (p.get("slope") or 0) for p in grow) / posg
    print(f"{s:<12}{len(grow):>6}{len(new):>6}{len(shrink):>7}{infill:>8.1f}{top10:>8.1f}{ms:>7.1f}")

# ---- figure ----
gdfs = {s: gpd.read_file(PUB / f"growth_{s}.geojson") for s, _ in SCEN}
allnz = [abs(x) for g in gdfs.values() for x in g["delta"] if x != 0]
vmax = float(np.percentile(allnz, 98))
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
fig, axes = plt.subplots(2, 2, figsize=(11, 9.5))
for ax, (s, title) in zip(axes.ravel(), SCEN):
    gdfs[s].plot(column="delta", cmap="RdBu", norm=norm, ax=ax, linewidth=0)
    ax.set_title(title, fontsize=13)
    ax.axis("off")
fig.suptitle("Spatial allocation of 2024–2049 population change by scenario",
             fontsize=14, y=0.98)
sm = plt.cm.ScalarMappable(cmap="RdBu", norm=norm)
sm.set_array([])
fig.colorbar(sm, ax=axes, shrink=0.55, label="Δ population per H3 cell")
plt.savefig(OUT, dpi=200, bbox_inches="tight")
print(f"saved {OUT}")
