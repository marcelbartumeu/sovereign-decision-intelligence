"""
Bridge: import place-layer constants from the parent profile_generation package.

place_layers.py lives one level above the schedules package in a directory that
has no __init__.py, so relative imports do not reach it.  This module adds the
parent directory to sys.path exactly once, then re-exports what the two schedule
models need, plus a shared affinity-ratio helper.
"""

import sys
from pathlib import Path

_parent = str(Path(__file__).parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from place_layers import ACTIVITY_LAYER_MAP, LAYER_BY_ID  # noqa: E402


def activity_affinity_ratio(place_prefs: dict, activity: str) -> float:
    """
    Affinity ratio: agent_mean_pref / population_mean_ref for an activity type.

    Equals 1 for an average agent by RUM construction (mean-centering guarantee).
    Values > 1 indicate above-average affinity; < 1 below-average.
    Clamped to [0.25, 4.0] to prevent degenerate Poisson rates or flat gravity decay.

    Parameters
    ──────────
    place_prefs : dict mapping layer_id → probability (from RUM, clipped [0.01, 0.99])
    activity    : one of the 8 activity types defined in place_layers.ACTIVITY_LAYER_MAP
    """
    ids = ACTIVITY_LAYER_MAP.get(activity, [])
    prefs = [place_prefs[lid] for lid in ids if lid in place_prefs]
    refs = [LAYER_BY_ID[lid].base_rate() for lid in ids]
    if not prefs or not refs:
        return 1.0
    agent_mean = sum(prefs) / len(prefs)
    ref_mean = sum(refs) / len(refs)
    if ref_mean == 0:
        return 1.0
    return max(0.25, min(4.0, agent_mean / ref_mean))
