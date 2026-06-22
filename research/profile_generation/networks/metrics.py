"""
Network validation metrics for the four-layer social graph.

Computed directly from edge lists (no third-party graph library). Because the
layer degrees are small (max ~30), the local clustering coefficient is computed
EXACTLY over all nodes — no sampling, so the metric is deterministic and carries
no estimator variance.

Per-layer metrics
─────────────────
n_edges, mean_degree, max_degree, isolated_frac, clustering_coeff

Realised-mixing metrics (require agent attributes; computed on the community
layer and the union graph, where homophily is the design target)
────────────────────────────────────────────────────────────────
nationality_assortativity : Newman (2003) categorical assortativity coefficient
age_assortativity         : numeric (Pearson) assortativity across edge endpoints
modularity_nat_parish     : Newman–Girvan modularity Q over (nationality × parish) blocks
giant_component_frac      : largest-connected-component fraction of the union graph
n_components              : number of connected components in the union graph

These directly validate the homophily/bridging parameters that the generator
takes as INPUT: r_nationality should be positive (in-group preference) and track
the configured nationality_homophily, and Q quantifies the realised segregation.

References
──────────
Watts & Strogatz (1998) Nature 393:440 — small-world layers (household,
  workplace, school) target clustering ≫ the equivalent random graph. The
  community layer is intentionally a low-clustering bridging/random layer.
Newman (2003) Phys. Rev. E 67:026126 — mixing patterns / assortativity.
Newman & Girvan (2004) Phys. Rev. E 69:026113 — modularity.
"""

from __future__ import annotations
import numpy as np
from .schema import NetworkLayers


# ── Graph helpers ──────────────────────────────────────────────────────────────

def _build_adj(edges: list, n: int) -> list:
    """Build adjacency list (list of sets) from integer-index edge list."""
    adj: list = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    return adj


def _degree_stats(adj: list) -> dict:
    degrees = [len(nbrs) for nbrs in adj]
    n = len(degrees)
    if n == 0:
        return {"mean": 0.0, "max": 0, "isolated_frac": 1.0}
    return {
        "mean":          round(float(np.mean(degrees)), 3),
        "max":           int(np.max(degrees)),
        "isolated_frac": round(sum(1 for d in degrees if d == 0) / n, 4),
    }


def _clustering_exact(adj: list) -> float:
    """
    Average local clustering coefficient over ALL nodes (degree<2 contribute 0,
    per the standard definition). Exact — no sampling — since layer degrees are
    small. O(N·d²) with d the per-node degree.
    """
    n = len(adj)
    if n == 0:
        return 0.0
    total = 0.0
    for nbrs in adj:
        k = len(nbrs)
        if k < 2:
            continue
        actual = 0
        nbr_list = tuple(nbrs)
        for a in range(k):
            ua = adj[nbr_list[a]]
            for b in range(a + 1, k):
                if nbr_list[b] in ua:
                    actual += 1
        total += actual / (k * (k - 1) / 2)
    return round(total / n, 4)


# ── Realised-mixing metrics ─────────────────────────────────────────────────────

def _assortativity_categorical(edges: list, labels: list) -> float:
    """
    Newman (2003) categorical assortativity coefficient r ∈ [-1, 1].
    r = (Σ e_xx − Σ a_x b_x) / (1 − Σ a_x b_x), computed on the symmetric
    mixing matrix. r>0 ⇒ assortative (in-group) mixing; 0 ⇒ proportionate.
    """
    if not edges:
        return 0.0
    from collections import defaultdict
    e: dict = defaultdict(float)
    a: dict = defaultdict(float)
    trace = 0.0
    m2 = 2.0 * len(edges)
    for u, v in edges:
        lu, lv = labels[u], labels[v]
        e[(lu, lv)] += 1.0
        e[(lv, lu)] += 1.0
    for (x, y), c in e.items():
        a[x] += c / m2
        if x == y:
            trace += c / m2
    sum_ab = sum(av * av for av in a.values())
    denom = 1.0 - sum_ab
    if abs(denom) < 1e-12:
        return 0.0
    return round((trace - sum_ab) / denom, 4)


def _assortativity_numeric(edges: list, values: list) -> float:
    """Pearson assortativity of a scalar attribute across edge endpoints
    (each undirected edge contributes both orientations)."""
    if not edges:
        return 0.0
    xs = np.empty(2 * len(edges)); ys = np.empty(2 * len(edges))
    for i, (u, v) in enumerate(edges):
        xs[2 * i] = values[u];  ys[2 * i] = values[v]
        xs[2 * i + 1] = values[v]; ys[2 * i + 1] = values[u]
    if xs.std() < 1e-12 or ys.std() < 1e-12:
        return 0.0
    return round(float(np.corrcoef(xs, ys)[0, 1]), 4)


def _modularity(edges: list, comm: list) -> float:
    """Newman–Girvan modularity Q for a fixed partition `comm` (label per node)."""
    m = len(edges)
    if m == 0:
        return 0.0
    from collections import defaultdict
    deg: dict = defaultdict(float)
    Lc: dict = defaultdict(float)   # intra-community edges
    for u, v in edges:
        deg[u] += 1.0; deg[v] += 1.0
        if comm[u] == comm[v]:
            Lc[comm[u]] += 1.0
    Dc: dict = defaultdict(float)   # summed degree per community
    for node, d in deg.items():
        Dc[comm[node]] += d
    Q = 0.0
    for c, dc in Dc.items():
        Q += (Lc.get(c, 0.0) / m) - (dc / (2.0 * m)) ** 2
    return round(Q, 4)


def _giant_component(adj: list) -> tuple:
    """(largest_component_fraction, n_components) over all nodes; isolated nodes
    count as singleton components. Iterative DFS."""
    n = len(adj)
    if n == 0:
        return 0.0, 0
    seen = bytearray(n)
    largest = 0
    ncomp = 0
    for s in range(n):
        if seen[s]:
            continue
        ncomp += 1
        stack = [s]; seen[s] = 1; size = 0
        while stack:
            x = stack.pop(); size += 1
            for y in adj[x]:
                if not seen[y]:
                    seen[y] = 1; stack.append(y)
        if size > largest:
            largest = size
    return round(largest / n, 4), ncomp


# ── Public API ──────────────────────────────────────────────────────────────────

def compute_network_metrics(
    layers: NetworkLayers,
    population: list | None = None,
    rng_seed: int = 42,   # retained for call-site compatibility; metrics are exact
) -> dict:
    """
    Compute validation metrics for all four network layers.

    population : optional list of agent dicts (index-aligned to layers.agent_ids).
                 When provided, realised-mixing metrics (nationality/age
                 assortativity, modularity, giant component) are added — these
                 validate the homophily/bridging parameters the generator uses
                 as input. Returns a dict suitable for run_meta.json.
    """
    n = len(layers.agent_ids)
    layer_edge_map = {
        "household":  layers.household_edges,
        "workplace":  layers.workplace_edges,
        "school":     layers.school_edges,
        "community":  layers.community_edges,
    }

    results: dict = {}
    for name, edges in layer_edge_map.items():
        adj = _build_adj(edges, n)
        deg = _degree_stats(adj)
        results[name] = {
            "n_edges":          len(edges),
            "mean_degree":      deg["mean"],
            "max_degree":       deg["max"],
            "isolated_frac":    deg["isolated_frac"],
            "clustering_coeff": _clustering_exact(adj),
        }

    results["total_edges"] = sum(len(e) for e in layer_edge_map.values())
    results["n_agents"]    = n

    # ── Realised mixing / connectivity (validates homophily & bridging) ────────
    if population is not None and n > 0:
        attr = {a["agent_id"]: a for a in population}
        nat   = [attr[aid].get("nationality", "Other") for aid in layers.agent_ids]
        age   = [int(attr[aid].get("age", 35) or 35) for aid in layers.agent_ids]
        block = [f"{attr[aid].get('nationality','Other')}|{attr[aid].get('parish','NA')}"
                 for aid in layers.agent_ids]

        # Headline social claim lives in the community layer.
        results["community"]["nationality_assortativity"] = \
            _assortativity_categorical(layers.community_edges, nat)
        results["community"]["age_assortativity"] = \
            _assortativity_numeric(layers.community_edges, age)
        results["community"]["modularity_nat_parish"] = \
            _modularity(layers.community_edges, block)

        # Union graph connectivity (epidemic reachability / coverage).
        union_edges = (layers.household_edges + layers.workplace_edges
                       + layers.school_edges + layers.community_edges)
        union_adj = _build_adj(union_edges, n)
        giant_frac, ncomp = _giant_component(union_adj)
        results["union"] = {
            "n_edges":                  len(union_edges),
            "mean_degree":              _degree_stats(union_adj)["mean"],
            "nationality_assortativity": _assortativity_categorical(union_edges, nat),
            "age_assortativity":         _assortativity_numeric(union_edges, age),
            "giant_component_frac":      giant_frac,
            "n_components":              ncomp,
        }

    return results


def print_summary(metrics: dict) -> None:
    print(f"\n  {'Layer':<12} {'Edges':>8}  {'Mean deg':>9}  {'Max deg':>8}  "
          f"{'Isolated':>9}  {'Clustering':>11}")
    print(f"  {'-'*68}")
    for layer in ("household", "workplace", "school", "community"):
        m = metrics[layer]
        print(f"  {layer:<12} {m['n_edges']:>8,}  {m['mean_degree']:>9.2f}  "
              f"{m['max_degree']:>8}  {m['isolated_frac']:>8.1%}  "
              f"{m['clustering_coeff']:>11.4f}")
    print(f"  {'Total edges':>30}: {metrics['total_edges']:,}")
    c = metrics.get("community", {})
    if "nationality_assortativity" in c:
        print(f"\n  Realised mixing (community layer):")
        print(f"    nationality assortativity r = {c['nationality_assortativity']:+.4f}  "
              f"(in-group preference; tracks nationality_homophily)")
        print(f"    age assortativity         r = {c['age_assortativity']:+.4f}")
        print(f"    modularity (nat×parish)   Q = {c['modularity_nat_parish']:.4f}")
    u = metrics.get("union", {})
    if u:
        print(f"  Union graph: giant component {u['giant_component_frac']:.1%} of agents, "
              f"{u['n_components']:,} components, nat. assortativity "
              f"r = {u['nationality_assortativity']:+.4f}")
