"""
Schedule generator: orchestrates the four sub-models into a DailySchedule per agent.

Pipeline per agent
──────────────────
1. Assign home H3 cell (residential distribution prior by nationality).
2. Sample car ownership (income bracket → probability gate).
3. Generate activity counts (profile → n trips per type).
4. For each activity instance:
   a. Sample destination H3 (gravity model).
   b. Choose mode (multinomial logit).
   c. Sample departure time (truncated Normal).
   d. Estimate travel duration (distance / mode speed).
   e. Append outbound Trip.
   f. Append return-home Trip (same mode, reversed, departure = arrival + dwell time).
5. Sort all trips by departure time.

Dwell times (minutes spent at destination before returning home)
────────────────────────────────────────────────────────────────
Fixed by activity type, with Gaussian noise. Source: HETUS 2010 European average.
  work:     480 min (8h) ± 60 min
  shopping:  45 min      ± 15 min
  leisure:   90 min      ± 30 min
  civic:     60 min      ± 20 min

These are proxies — no Andorra-specific activity duration data available.
"""

import numpy as np
from .schema import Trip, DailySchedule
from .activity_model import generate_activity_counts
from .mode_model import choose_mode, sample_car_ownership
from .destination_model import H3Grid
from .temporal_model import sample_departure
from .config import SPEED_KMH

# Dwell time parameters (mean, sigma) in minutes. Source: HETUS 2010 (proxy).
_DWELL: dict[str, tuple[float, float]] = {
    "work":     (480.0, 60.0),
    "shopping": ( 45.0, 15.0),
    "leisure":  ( 90.0, 30.0),
    "civic":    ( 60.0, 20.0),
}

_MINUTES_PER_DAY = 1440.0


def _travel_duration(dist_km: float, mode: str) -> float:
    """Estimate one-way travel time in minutes."""
    speed = SPEED_KMH[mode].value
    return max((dist_km / speed) * 60.0, 1.0)


def generate_schedules(
    population: list[dict],
    rng_seed: int = 42,
) -> list[DailySchedule]:
    """
    Generate one representative weekday DailySchedule per agent.

    Parameters
    ──────────
    population : list of expanded agent profile dicts (output of expand.expand())
    rng_seed   : integer seed for full reproducibility

    Returns
    ───────
    list[DailySchedule], one per agent, in the same order as population.
    """
    rng  = np.random.default_rng(rng_seed)
    grid = H3Grid()

    # Pre-assign home cells grouped by nationality for efficiency.
    # We collect all agents per nationality, sample their home cells in one
    # vectorised call, then distribute back.
    nat_groups: dict[str, list[int]] = {}
    for i, agent in enumerate(population):
        nat = agent.get("nationality", "Other")
        nat_groups.setdefault(nat, []).append(i)

    home_h3: list[str] = [""] * len(population)
    for nat, idxs in nat_groups.items():
        cells = grid.residential_cells(nat, len(idxs), rng)
        for i, cell in zip(idxs, cells):
            home_h3[i] = cell

    schedules: list[DailySchedule] = []

    for i, agent in enumerate(population):
        agent_id = agent.get("agent_id", f"POP-{i:05d}")
        h_home   = home_h3[i]
        income   = agent.get("income_bracket", "middle")
        nat      = agent.get("nationality", "Other")

        has_car    = sample_car_ownership(income, rng)
        act_counts = generate_activity_counts(agent, rng)

        bridging = float(
            agent.get("social", {}).get("bridging_capital", 0.5)
        )

        trips: list[Trip] = []

        for activity, n in act_counts.items():
            for _ in range(n):
                # Destination
                dest_h3 = grid.choose_destination(h_home, activity, bridging, rng)
                dist    = grid.distance_km(h_home, dest_h3)

                # Mode
                tc   = grid.transit_coverage(h_home)
                mode = choose_mode(agent, dist, tc, has_car, rng)

                # Departure time (outbound)
                dep_out = sample_departure(activity, outbound=True, profile=agent, rng=rng)

                # Travel duration
                dur = _travel_duration(dist, mode)

                trips.append(Trip(
                    agent_id      = agent_id,
                    activity_type = activity,
                    origin_h3     = h_home,
                    dest_h3       = dest_h3,
                    mode          = mode,
                    departure_min = dep_out,
                    duration_min  = dur,
                ))

                # Return-home trip
                dwell_mean, dwell_sigma = _DWELL[activity]
                dwell = float(rng.normal(dwell_mean, dwell_sigma))
                dwell = max(dwell, 5.0)

                arr_out  = dep_out + dur
                dep_ret  = arr_out + dwell
                dep_ret  = min(dep_ret, _MINUTES_PER_DAY - dur)   # must arrive before midnight

                trips.append(Trip(
                    agent_id      = agent_id,
                    activity_type = "home",
                    origin_h3     = dest_h3,
                    dest_h3       = h_home,
                    mode          = mode,
                    departure_min = dep_ret,
                    duration_min  = dur,
                ))

        # Sort by departure time
        trips.sort(key=lambda t: t.departure_min)

        schedules.append(DailySchedule(
            agent_id = agent_id,
            home_h3  = h_home,
            trips    = trips,
        ))

    return schedules
