"""
Mode choice model: multinomial logit over {car, bus, walk}.

Theoretical basis: Random Utility Maximisation (McFadden 1974). Each alternative
has a systematic utility V_k; the agent chooses the mode that maximises V_k + ε_k
where ε_k is i.i.d. Gumbel(0,1). This gives the standard softmax choice probability.

Calibration target: Andorra modal split — car 80%, bus 12%, walk 8%
(Govern d'Andorra, Pla de Mobilitat Sostenible 2019).
ASC values in config.py are set to reproduce this split at population-mean
profile values (transit_willingness=0.5, price_sensitivity=0.5, income=middle).

Walk is only available if the destination is within the agent's walking radius.
Car is only available if the agent's income bracket allows car ownership
(stochastic gate per agent, seeded at schedule generation time).
"""

import numpy as np
from .config import (
    ASC,
    TRANSIT_COEFF,
    PRICE_SENSITIVITY_COEFF,
    CAR_OWNERSHIP_PROB,
    WALK_MAX_KM,
)


def _softmax(utils: dict[str, float]) -> dict[str, float]:
    keys = list(utils.keys())
    vals = np.array([utils[k] for k in keys])
    vals -= vals.max()   # numerical stability
    exp  = np.exp(vals)
    probs = exp / exp.sum()
    return {k: float(p) for k, p in zip(keys, probs)}


def choose_mode(
    profile: dict,
    dist_km: float,
    transit_coverage: bool,
    has_car: bool,
    rng: np.random.Generator,
) -> str:
    """
    Sample a mode given agent profile, trip distance, and infrastructure context.

    Parameters
    ──────────
    profile          : agent profile dict
    dist_km          : straight-line distance origin → destination
    transit_coverage : True if origin H3 cell has bus/car accessibility type
    has_car          : whether this agent owns a car (pre-sampled from income bracket)
    rng              : seeded numpy Generator

    Returns
    ───────
    One of: "car", "bus", "walk"
    """
    transit_will = float(profile.get("mobility", {}).get("transit_willingness", 0.5))
    price_sens   = float(profile.get("economic",  {}).get("price_sensitivity",   0.5))
    walk_radius  = float(profile.get("mobility",  {}).get("walking_radius_km",   1.5))

    # ── Availability constraints ───────────────────────────────────────────────
    available: dict[str, bool] = {
        "car":  has_car,
        "bus":  transit_coverage,
        "walk": dist_km <= min(walk_radius, WALK_MAX_KM.value),
    }

    # If nothing is available (no car, no bus coverage, too far to walk),
    # fall back to car regardless — agent finds a way (taxi, carpool).
    # This is a known limitation; flagged for future treatment with rideshare mode.
    if not any(available.values()):
        return "car"

    # ── Utility computation ────────────────────────────────────────────────────
    utils: dict[str, float] = {}

    if available["car"]:
        utils["car"] = ASC["car"].value
        # No additional profile covariates for car beyond ASC and ownership.
        # Price sensitivity reduces car utility slightly (car costs more than bus).
        utils["car"] -= PRICE_SENSITIVITY_COEFF.value * price_sens * 0.3

    if available["bus"]:
        utils["bus"] = ASC["bus"].value
        # Transit willingness: positive utility bonus for willing transit users.
        utils["bus"] += TRANSIT_COEFF.value * (transit_will - 0.5)
        # Price sensitivity: bus is cheaper, so sensitive agents prefer it.
        utils["bus"] += PRICE_SENSITIVITY_COEFF.value * price_sens * 0.5

    if available["walk"]:
        utils["walk"] = ASC["walk"].value
        # Distance penalty: walking utility decreases linearly with distance.
        # Coefficient: at 1 km, penalty = 0.5 utils; at 3 km, = 1.5 utils.
        utils["walk"] -= 0.5 * dist_km

    if not utils:
        return "car"

    probs = _softmax(utils)
    modes = list(probs.keys())
    weights = [probs[m] for m in modes]
    return str(rng.choice(modes, p=weights))


def sample_car_ownership(income_bracket: str, rng: np.random.Generator) -> bool:
    """
    Pre-sample whether this agent owns a car based on income bracket.
    Called once per agent at schedule generation, not per trip — an agent either
    has a car for the day or they don't.
    """
    prob = CAR_OWNERSHIP_PROB.get(income_bracket, CAR_OWNERSHIP_PROB["middle"]).value
    return bool(rng.random() < prob)
