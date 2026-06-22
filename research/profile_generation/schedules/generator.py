"""
Schedule generator (V2.2): builds a DailySchedule per agent from REALIZED
households and persistent anchors. Network and households already exist when this
runs (schedules are the LAST phase), so the schedule consumes structure rather
than inventing it.

Per-agent pipeline
──────────────────
ADULTS
  1. Home = the household's shared home_h3 (assigned in households.py).
  2. Work trip → the agent's persistent work_h3 anchor (NOT a fresh gravity draw).
     Cross-border workers (work_h3="BORDER") commute to the southern border cell.
  3. Escort trip → guardians of school-age children do a morning school drop-off.
  4. Discretionary trips (education/grocery/shopping/leisure/healthcare/civic) → gravity model,
     with a parenthood β multiplier (Macedo 2026: parents have a tighter radius).
CHILDREN (0–14)
  1. School trip → the child's school_h3 anchor (age ≥ 3), escorted in mode.
  2. One optional outdoor/park trip.

Dwell times (min, mean ± sd) — HETUS 2010 proxy; school/escort added for V2.2.
"""

import numpy as np
from .schema import Trip, DailySchedule
from .activity_model import generate_activity_counts
from .mode_model import choose_mode, sample_car_ownership
from .destination_model import H3Grid
from .temporal_model import sample_departure
from .osm_poi import PoiLookup
from .config import SPEED_KMH

_DWELL: dict[str, tuple[float, float]] = {
    "work":            (480.0, 60.0),
    "grocery":         ( 30.0, 10.0),
    "shopping":        ( 60.0, 20.0),
    "education":       (240.0, 60.0),
    "leisure_indoor":  ( 90.0, 30.0),
    "leisure_outdoor": (120.0, 45.0),
    "healthcare":      ( 45.0, 15.0),
    "civic":           ( 60.0, 20.0),
    "school":          (375.0, 45.0),   # child school day (~6 h)
    "escort":          (  8.0,  4.0),   # drop-off then leave
}
_MINUTES_PER_DAY = 1440.0

_ADULT_EMPLOYED = ("employed_full_time", "employed_part_time", "self_employed",
                   "full_time", "part_time")


def _travel_duration(dist_km: float, mode: str) -> float:
    speed = SPEED_KMH[mode].value
    return max((dist_km / speed) * 60.0, 1.0)


# Idle gap (minutes) above which the agent returns home between two activities,
# starting a new home-based tour instead of chaining directly.
_TOUR_GAP_MIN = 60.0


def _build_chain(agent_id, home, intents, grid, pick_mode):
    """Build a COHERENT trip chain from time-ordered activity intents.

    Each intent: {type, dest, dwell, dep_pref, poi}. Trips chain location→location
    (origin = where the previous activity left the agent), never depart before the
    previous activity finishes (no time overlap), and a return-home is inserted when
    there is a long idle gap (a new home-based tour). The agent ends the day at home.
    This replaces the old hub-and-spoke design where every trip started from home and
    independent departure times produced overlapping, teleporting trips.
    """
    intents = sorted(intents, key=lambda a: a["dep_pref"])
    trips: list[Trip] = []
    history: list[tuple[str, float, int]] = []
    loc  = home
    free = 0.0   # minute the agent becomes free at its current location

    def add(origin, activity, dest, dep, poi=None, state_before=None):
        """Append a trip and return its arrival minute, or None if it cannot fit in
        the day (so the caller skips it rather than clamping into the prior trip)."""
        dist = grid.distance_km(origin, dest)
        mode = pick_mode(origin, dest, dist)
        dur  = _travel_duration(dist, mode)
        dep  = max(dep, 0.0)
        if dep > _MINUTES_PER_DAY - dur - 1.0:
            return None
        if state_before is not None:
            history.append((state_before[0], state_before[1], len(trips)))
        trips.append(Trip(
            agent_id=agent_id, activity_type=activity, origin_h3=origin, dest_h3=dest,
            mode=mode, departure_min=dep, duration_min=dur,
            poi_name=poi.get("name", "") if poi else "",
            poi_lat=poi.get("lat") if poi else None,
            poi_lon=poi.get("lon") if poi else None,
        ))
        return dep + dur   # arrival minute

    for act in intents:
        # Return home first if a long idle gap precedes this activity (new tour).
        if loc != home and act["dep_pref"] - free > _TOUR_GAP_MIN:
            arr = add(loc, "home", home, free, state_before=(loc, free))
            if arr is not None:
                loc, free = home, arr
        arr = add(
            loc, act["type"], act["dest"], max(free, act["dep_pref"]),
            act.get("poi"), state_before=(loc, free)
        )
        if arr is None:
            continue   # doesn't fit; stay put and try later intents (day is filling up)
        free = arr + max(act["dwell"], 5.0)
        loc  = act["dest"]

    # The day should end at home. If the final return leg does not fit, remove the
    # latest accepted activity/tour leg and try again rather than leaving the agent
    # stranded away from home.
    while loc != home:
        arr = add(loc, "home", home, free, state_before=(loc, free))
        if arr is not None:
            break
        if not history:
            break
        prev_loc, prev_free, trip_len = history.pop()
        del trips[trip_len:]
        loc, free = prev_loc, prev_free
    return trips


def generate_schedules(
    population: list[dict],
    rng_seed: int = 42,
    households: list[dict] | None = None,
) -> list[DailySchedule]:
    rng    = np.random.default_rng(rng_seed)
    grid   = H3Grid()
    lookup = PoiLookup.load()
    if lookup.loaded:
        n_fac = sum(sum(len(v) for v in c.values()) for c in lookup._index.values())
        print(f"  POI index loaded ({n_fac} facilities)")
    else:
        print("  POI index not found — trips will use H3 centroid fallback")

    # Southern border cell proxy for cross-border commutes (toward La Seu d'Urgell).
    border_cell = min(grid.cells, key=lambda c: c["lat"])["h3"]

    # Guardian → child school anchor map (for escort trips). One drop-off per guardian.
    escort_target: dict[str, str] = {}
    for a in population:
        if a.get("is_minor") and a.get("school_h3") and a.get("school_stage") != "nursery":
            for g in (a.get("guardian_ids") or [])[:1]:   # primary guardian
                escort_target.setdefault(g, a["school_h3"])

    household_vehicles = {
        h.get("household_id"): int(h.get("num_vehicles", 0))
        for h in (households or [])
        if h.get("household_id")
    }

    schedules: list[DailySchedule] = []

    for i, agent in enumerate(population):
        agent_id = agent.get("agent_id", f"AG-{i:05d}")
        home     = agent.get("home_h3") or grid.home_cell(
            agent.get("nationality", "Other"), agent.get("income_bracket", "middle"), rng)
        trips: list[Trip] = []

        # ── Children ──────────────────────────────────────────────────────────
        if agent.get("is_minor"):
            school = agent.get("school_h3")
            stage  = agent.get("school_stage", "primary")
            intents: list[dict] = []
            if school and stage != "nursery":
                dm, ds = _DWELL["school"]
                intents.append({"type": "education", "dest": school,
                                "dwell": float(rng.normal(dm, ds)),
                                "dep_pref": float(np.clip(rng.normal(495, 20), 420, 540)),
                                "poi": lookup.sample(school, "education", rng)})
            elif school:   # nursery / daycare
                intents.append({"type": "education", "dest": school, "dwell": 300.0,
                                "dep_pref": float(np.clip(rng.normal(540, 30), 420, 600)),
                                "poi": lookup.sample(school, "education", rng)})
            if rng.random() < 0.35:   # optional afternoon park/outdoor trip
                dest = grid.choose_destination(home, "leisure_outdoor", 0.5, rng, beta_mult=1.3)
                dm, ds = _DWELL["leisure_outdoor"]
                intents.append({"type": "leisure_outdoor", "dest": dest,
                                "dwell": float(rng.normal(dm * 0.6, ds)),
                                "dep_pref": float(np.clip(rng.normal(960, 60), 780, 1140)),
                                "poi": lookup.sample(dest, "leisure_outdoor", rng)})
            child_mode = lambda o, d, dist: "walk" if dist < 1.0 else "bus"
            trips = _build_chain(agent_id, home, intents, grid, child_mode)
            schedules.append(DailySchedule(agent_id=agent_id, home_h3=home, trips=trips))
            continue

        # ── Adults ──────────────────────────────────────────────────────────────
        income   = agent.get("income_bracket", "middle")
        if household_vehicles:
            has_car = bool(agent.get("has_license") and
                           household_vehicles.get(agent.get("household_id"), 0) > 0)
        else:
            # Backward-compatible fallback for ad-hoc use before households exist.
            has_car = bool(agent.get("has_license") and sample_car_ownership(income, rng))
        prefs    = agent.get("place_preferences") or None
        counts   = generate_activity_counts(agent, rng, place_preferences=prefs)
        bridging = float(agent.get("social", {}).get("bridging_capital", 0.5))

        # parenthood β multiplier: tighter radius for parents of young children
        beta_mult = 1.35 if (agent.get("household_role") in ("head", "partner")
                             and agent.get("household_has_young_children")) else 1.0

        # mode is chosen per leg from the ACTUAL origin (transit coverage is local)
        adult_mode = lambda o, d, dist: choose_mode(
            agent, dist, grid.transit_coverage(o), has_car, rng)

        intents = []

        # Work → persistent anchor
        work_dep = None
        is_worker = agent.get("employment_status") in _ADULT_EMPLOYED and agent.get("work_h3")
        if is_worker:
            wdest = border_cell if agent.get("work_h3") == "BORDER" else agent["work_h3"]
            dm, ds = _DWELL["work"]
            work_dep = sample_departure("work", outbound=True, profile=agent, rng=rng)
            intents.append({"type": "work", "dest": wdest, "dwell": float(rng.normal(dm, ds)),
                            "dep_pref": work_dep, "poi": lookup.sample(wdest, "work", rng)})

        # Escort → school drop-off; scheduled just before the work commute so the
        # chain runs home → school (drop) → work rather than a separate round trip.
        if agent_id in escort_target:
            dm, ds = _DWELL["escort"]
            edep = float(np.clip(rng.normal(485, 15), 420, 540))
            if work_dep is not None:
                edep = min(edep, work_dep - 15.0)
            intents.append({"type": "escort", "dest": escort_target[agent_id],
                            "dwell": float(rng.normal(dm, ds)), "dep_pref": edep, "poi": None})

        # Discretionary activities (gravity from home, parenthood β)
        for activity in ("education", "grocery", "shopping", "leisure_indoor", "leisure_outdoor",
                         "healthcare", "civic"):
            for _ in range(counts.get(activity, 0)):
                dest = grid.choose_destination(home, activity, bridging, rng,
                                               place_preferences=prefs, beta_mult=beta_mult)
                dm, ds = _DWELL[activity]
                intents.append({"type": activity, "dest": dest,
                                "dwell": float(rng.normal(dm, ds)),
                                "dep_pref": sample_departure(activity, outbound=True,
                                                             profile=agent, rng=rng),
                                "poi": lookup.sample(dest, activity, rng)})

        trips = _build_chain(agent_id, home, intents, grid, adult_mode)
        schedules.append(DailySchedule(agent_id=agent_id, home_h3=home, trips=trips))

    return schedules
