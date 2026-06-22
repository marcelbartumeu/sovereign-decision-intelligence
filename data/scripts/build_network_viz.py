"""Precompute the social-network visualization layout for the Network tab.

Reads the population + network edge lists from research/profile_generation/results/
andorra_population/ and writes compact binary files consumed by the front end
(app/src/components/NetworkView.jsx):

  app/public/network/positions.bin        Float32 [x, y] * n_agents (DrL layout)
  app/public/network/edges_household.bin  Uint32 [src, dst] * n_household_edges
  app/public/network/edges_workplace.bin  Uint32 [src, dst] * n_workplace_edges
  app/public/network/edges_school.bin     Uint32 [src, dst] * n_school_edges
  app/public/network/edges_community.bin  Uint32 [src, dst] * n_community_edges
  app/public/network/attrs.bin            Uint8 planes: age, nationality, income,
                                          employment, household (n_agents each)
  app/public/network/meta.json            counts + category label tables

Run:  .venv/bin/python3 data/scripts/build_network_viz.py
"""

import csv
import json
import time
from pathlib import Path

import igraph as ig
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "research" / "profile_generation" / "results" / "andorra_population"
OUT = ROOT / "app" / "public" / "network"

N_AGENTS = 90_000

# DrL edge weights: households pull tightest, community ties loosest
LAYERS = [
    ("household", 3.0),
    ("workplace", 2.0),
    ("school",    2.0),
    ("community", 1.0),
]

NATIONALITIES = ["Andorran", "Spanish", "Portuguese", "French", "Other"]
INCOMES = ["precarious", "low", "lower_middle", "middle", "upper_middle", "comfortable", "wealthy"]
# "minor" is the fallback for under-15s, who carry no employment_status field.
EMPLOYMENTS = ["employed_full_time", "employed_part_time", "self_employed", "student", "retired", "minor"]
HOUSEHOLDS = ["single", "couple_no_children", "couple_with_children", "shared_accommodation", "multi_generational"]


def read_edges(layer: str, idx: dict) -> np.ndarray:
    """Edge CSV (src,dst agent_id pairs) -> (n, 2) uint32 array of array indices.

    Maps each agent_id through the population index, NOT the numeric id suffix:
    children (CH-xxxxx) are interleaved with adults (POP-xxxxx), so the suffix is
    not the array index.
    """
    path = SRC / f"network_{layer}.csv"
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)  # header
        edges = [(idx[src], idx[dst]) for src, dst in reader
                 if src in idx and dst in idx]
    return np.asarray(edges, dtype=np.uint32)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    print("Loading population...")
    with open(SRC / "population.json") as f:
        population = json.load(f)
    assert len(population) == N_AGENTS
    idx = {a["agent_id"]: i for i, a in enumerate(population)}

    print("Reading edge lists...")
    layer_edges = {name: read_edges(name, idx) for name, _ in LAYERS}
    for name, arr in layer_edges.items():
        print(f"  {name}: {len(arr):,} edges")

    all_edges = np.vstack([layer_edges[name] for name, _ in LAYERS])
    weights = np.concatenate(
        [np.full(len(layer_edges[name]), w, dtype=np.float64) for name, w in LAYERS]
    )

    print("Building graph...")
    g = ig.Graph(n=N_AGENTS, edges=all_edges.tolist(), directed=False)

    print("Computing DrL layout (this takes a few minutes)...")
    t0 = time.time()
    layout = g.layout_drl(weights=weights.tolist(), seed=None)
    print(f"  done in {time.time() - t0:.0f}s")

    pos = np.asarray(layout.coords, dtype=np.float64)
    # Center and scale into a [-1000, 1000] world box
    pos -= pos.mean(axis=0)
    pos *= 1000.0 / np.abs(pos).max()
    pos.astype(np.float32).tofile(OUT / "positions.bin")

    for name, _ in LAYERS:
        layer_edges[name].tofile(OUT / f"edges_{name}.bin")

    print("Packing agent attributes...")
    nat_idx = {v: i for i, v in enumerate(NATIONALITIES)}
    inc_idx = {v: i for i, v in enumerate(INCOMES)}
    emp_idx = {v: i for i, v in enumerate(EMPLOYMENTS)}
    hh_idx = {v: i for i, v in enumerate(HOUSEHOLDS)}

    age = np.array([min(a.get("age", 0), 255) for a in population], dtype=np.uint8)
    nat = np.array([nat_idx.get(a.get("nationality"), 0) for a in population], dtype=np.uint8)
    inc = np.array([inc_idx.get(a.get("income_bracket"), 0) for a in population], dtype=np.uint8)
    emp = np.array([emp_idx.get(a.get("employment_status"), emp_idx["minor"]) for a in population], dtype=np.uint8)
    hh = np.array([hh_idx.get(a.get("household_composition"), 0) for a in population], dtype=np.uint8)
    np.concatenate([age, nat, inc, emp, hh]).tofile(OUT / "attrs.bin")

    meta = {
        "n_agents": N_AGENTS,
        "edges": {name: int(len(layer_edges[name])) for name, _ in LAYERS},
        "attr_planes": ["age", "nationality", "income", "employment", "household"],
        "nationalities": NATIONALITIES,
        "incomes": INCOMES,
        "employments": EMPLOYMENTS,
        "households": HOUSEHOLDS,
    }
    with open(OUT / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    total = sum(p.stat().st_size for p in OUT.iterdir())
    print(f"Wrote {OUT} ({total / 1e6:.1f} MB total)")


if __name__ == "__main__":
    main()
