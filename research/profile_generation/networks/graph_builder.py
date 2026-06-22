"""
Stage 3 graph construction (V2.2): four-layer social network from REALIZED
households, stable employers, school anchors, and geography.

Four layers (Jiang, Crooks, Kavak et al. 2022 — extended with a school layer):
  Household  — members of the same realized household (complete graph). Uses the
               household entity, NOT res-10 co-location. home_contacts adds a few
               extra-household kin/neighbour ties.
  Workplace  — adults sharing the same employer_id form an NWS graph parameterised
               by workplace_k / workplace_p; sized by work_contacts. Cross-border
               (BORDER) employers are excluded (they work in different foreign cities).
  School     — children sharing the same school_h3 form an NWS graph; their
               guardians are linked too (school-gate parent network).
  Community  — within each (nationality × parish) cluster, degree-targeted random
               edges sized by community_contacts, weighted by nationality_homophily
               and age_homophily, with cross-nationality bridging via bridging_weight.

All EIGHT SocialProfile parameters are now used. Each agent's profile is looked up
DIRECTLY via its archetype_id (lineage recorded in expand.py) — no lossy demographic
re-match. Children use a fixed child social profile.

No networkx dependency — pure numpy + standard library.
"""

from __future__ import annotations
import numpy as np
from .schema import SocialProfile, NetworkLayers

# Child social profile: low work, school-centred, family-bonded.
_CHILD_PROFILE = SocialProfile(
    home_contacts=4.0, work_contacts=0.0, community_contacts=2.5,
    workplace_k=4, workplace_p=0.30,
    nationality_homophily=0.6, age_homophily=0.7, bridging_weight=0.3,
)

# Age-band cut points for community age-homophily. Kept identical to
# contact_priors.age_band (child<15, young<30, adult<65, senior) so the module
# uses one consistent age binning throughout.
_AGE_BAND_EDGES = (15, 30, 65)

# Extra-household kin/neighbour ties added per agent are capped to keep the
# household layer realistic ("a few" kin ties, per home_contacts).
_MAX_KIN_TIES = 3


def _age_band(age: int) -> int:
    for i, b in enumerate(_AGE_BAND_EDGES):
        if age < b:
            return i
    return len(_AGE_BAND_EDGES)


# ── Graph primitives ──────────────────────────────────────────────────────────

def _complete_graph(indices: list) -> list:
    n = len(indices)
    return [(indices[i], indices[j]) for i in range(n) for j in range(i + 1, n)]


def _nws_edges(indices: list, k: int, p: float, rng) -> list:
    """Newman-Watts-Strogatz: shortcuts ADDED to a ring lattice (not rewired)."""
    n = len(indices)
    half_k = max(1, int(k) // 2)
    if n <= half_k * 2 + 1:
        return _complete_graph(indices)
    edges: set = set()
    for i in range(n):
        for step in range(1, half_k + 1):
            u, v = indices[i], indices[(i + step) % n]
            edges.add((min(u, v), max(u, v)))
    for i in range(n):
        for step in range(1, half_k + 1):
            if rng.random() < p:
                j = int(rng.integers(0, n))
                if j != i:
                    u, v = indices[i], indices[j]
                    edges.add((min(u, v), max(u, v)))
    return list(edges)


# ── Social profile assignment via archetype lineage ───────────────────────────

def _assign_profiles(population: list, sp_by_arch: dict) -> list:
    """One SocialProfile per agent, looked up by archetype_id (adults) or the
    fixed child profile (minors). No demographic re-match."""
    out = []
    default = next(iter(sp_by_arch.values())) if sp_by_arch else _CHILD_PROFILE
    for a in population:
        if a.get("is_minor"):
            out.append(_CHILD_PROFILE)
        else:
            out.append(sp_by_arch.get(a.get("archetype_id"), default))
    return out


# ── Main builder ──────────────────────────────────────────────────────────────

def build_network(
    population: list,
    households: list,
    social_profiles_by_archetype: dict,
    rng_seed: int = 42,
) -> NetworkLayers:
    """
    Build the four-layer social network.

    population : agent dicts with home_h3/work_h3/school_h3/employer_id/parish/
                 household_id/archetype_id (output of households phase)
    households : household dicts with member_ids (output of households phase)
    social_profiles_by_archetype : {archetype_id: SocialProfile}
    """
    # Independent per-layer RNG streams (seeded deterministically from rng_seed)
    # so each layer is reproducible in isolation — editing one layer's sampling
    # cannot shift another layer's output.
    rng_kin, rng_wp, rng_school, rng_comm = np.random.default_rng(rng_seed).spawn(4)
    agent_ids = [a["agent_id"] for a in population]
    idx = {aid: i for i, aid in enumerate(agent_ids)}
    profiles = _assign_profiles(population, social_profiles_by_archetype)

    # ── Layer 1: Household (realized households → complete graph + kin ties) ───
    # The realized-household complete graph gives each agent a degree of
    # (household_size − 1). home_contacts then tops this up with a few
    # extra-household kin/neighbour ties (same parish, different household) so
    # each agent's home-layer degree approaches its Prem-bounded home_contacts
    # target. This is the only place home_contacts is consumed.
    print("  Building household layer (realized households + kin ties)...")
    household_edge_set: set = set()
    hh_size: dict = {}
    for h in households:
        members = [idx[m] for m in h["member_ids"] if m in idx]
        for m in members:
            hh_size[m] = len(members)
        if len(members) >= 2:
            for u, v in _complete_graph(members):
                household_edge_set.add((u, v))

    hh_of = [a.get("household_id") for a in population]
    parish_members: dict = {}
    for i, a in enumerate(population):
        parish_members.setdefault(a.get("parish", "NA"), []).append(i)
    parish_arr = {p: np.array(v) for p, v in parish_members.items()}

    for i, a in enumerate(population):
        target = int(round(profiles[i].home_contacts))
        deficit = target - (hh_size.get(i, 1) - 1)
        # Each agent initiates ~half its deficit because kin ties are mutual
        # (an agent also RECEIVES ties initiated by others), so realized
        # home-layer degree calibrates to home_contacts rather than ~2×.
        extra = min(_MAX_KIN_TIES, (deficit + 1) // 2) if deficit > 0 else 0
        if extra <= 0:
            continue
        pool = parish_arr.get(a.get("parish", "NA"))
        if pool is None or len(pool) <= 1:
            continue
        added = tries = 0
        while added < extra and tries < extra * 4:
            j = int(rng_kin.choice(pool))
            tries += 1
            if j == i or hh_of[i] == hh_of[j]:
                continue
            e = (min(i, j), max(i, j))
            if e in household_edge_set:
                continue
            household_edge_set.add(e)
            added += 1
    household_edges = list(household_edge_set)

    # ── Layer 2: Workplace (stable employer_id → NWS) ──────────────────────────
    print("  Building workplace layer (stable employers)...")
    workplace_edges: list = []
    emp_groups: dict = {}
    for i, a in enumerate(population):
        eid = a.get("employer_id")
        if not eid or eid.endswith("BORDER"):
            continue
        emp_groups.setdefault(eid, []).append(i)
    for eid, members in emp_groups.items():
        if len(members) < 2:
            continue
        prof = profiles[members[0]]
        k = min(prof.workplace_k, len(members) - 1)
        # work_contacts caps the NWS neighbour count (but never below 2, so a
        # connected worker keeps at least a minimal pair of workplace ties).
        if prof.work_contacts > 0:
            k = min(k, max(2, int(round(prof.work_contacts))))
        workplace_edges.extend(_nws_edges(members, k, prof.workplace_p, rng_wp))

    # ── Layer 3: School (shared school_h3 → NWS; + guardians) ──────────────────
    print("  Building school layer...")
    school_edges_set: set = set()
    school_groups: dict = {}
    for i, a in enumerate(population):
        sh = a.get("school_h3")
        if a.get("is_minor") and sh:
            school_groups.setdefault(sh, []).append(i)
    for sh, kids in school_groups.items():
        if len(kids) >= 2:
            for u, v in _nws_edges(kids, 4, 0.30, rng_school):
                school_edges_set.add((min(u, v), max(u, v)))
        # parent–parent ties: link one guardian per child to one guardian of the
        # next child (school-gate network), same school
        guardians = []
        for ci in kids:
            gids = population[ci].get("guardian_ids") or []
            if gids and gids[0] in idx:
                guardians.append(idx[gids[0]])
        guardians = list(dict.fromkeys(guardians))
        if len(guardians) >= 2:
            for u, v in _nws_edges(guardians, 3, 0.20, rng_school):
                school_edges_set.add((min(u, v), max(u, v)))
    school_edges = list(school_edges_set)

    # ── Layer 4: Community (nationality × parish, degree-targeted) ─────────────
    print("  Building community layer (nationality × parish)...")
    community_edge_set: set = set()
    groups: dict = {}
    for i, a in enumerate(population):
        nat = a.get("nationality", "Other")
        par = a.get("parish", "NA")
        groups.setdefault((nat, par), []).append(i)

    # within-group edges (homophily by age), degree = community_contacts × 0.7
    for (nat, par), members in groups.items():
        n_grp = len(members)
        if n_grp < 2:
            continue
        arr = np.array(members)
        ages = np.array([population[m].get("age", 35) for m in members])
        bands = np.array([_age_band(int(x)) for x in ages])
        for li in range(n_grp):
            prof = profiles[int(arr[li])]
            k_within = max(1, int(round(prof.community_contacts * 0.7)))
            k_within = min(k_within, n_grp - 1)
            # age-homophily: bias candidate sampling toward same age band
            same = np.where((bands == bands[li]) & (arr != arr[li]))[0]
            diff = np.where((bands != bands[li]))[0]
            n_same = int(round(k_within * prof.age_homophily))
            picks = []
            if len(same) and n_same:
                picks += list(rng_comm.choice(same, size=min(n_same, len(same)), replace=False))
            n_rest = k_within - len(picks)
            if len(diff) and n_rest > 0:
                picks += list(rng_comm.choice(diff, size=min(n_rest, len(diff)), replace=False))
            for pj in picks:
                u, v = int(arr[li]), int(arr[pj])
                community_edge_set.add((min(u, v), max(u, v)))

    # cross-nationality bridging within the same parish
    by_parish: dict = {}
    for (nat, par), members in groups.items():
        by_parish.setdefault(par, {})[nat] = np.array(members)
    for par, nat_map in by_parish.items():
        nats = list(nat_map.keys())
        if len(nats) < 2:
            continue
        for nat_a in nats:
            group_a = nat_map[nat_a]
            other = np.concatenate([nat_map[nb] for nb in nats if nb != nat_a])
            if len(other) == 0:
                continue
            for ai in group_a:
                prof = profiles[int(ai)]
                # cross ties scaled by (1 - nationality_homophily) and bridging_weight
                k_bridge = int(round(prof.community_contacts * 0.3
                                     * prof.bridging_weight * (1.0 - prof.nationality_homophily)))
                k_bridge = min(k_bridge, len(other))
                if k_bridge < 1:
                    continue
                nbrs = rng_comm.choice(other, size=k_bridge, replace=False)
                for nb in nbrs:
                    u, v = int(ai), int(nb)
                    community_edge_set.add((min(u, v), max(u, v)))
    community_edges = list(community_edge_set)

    return NetworkLayers(
        agent_ids       = agent_ids,
        household_edges = household_edges,
        workplace_edges = workplace_edges,
        school_edges    = school_edges,
        community_edges = community_edges,
    )
