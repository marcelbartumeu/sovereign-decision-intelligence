"""
Stage 3 (V2.2): Four-layer social network generation, built from realized
households + stable employers + school anchors + geography.

Pipeline
────────
1. EXP04 (LLM) generates one SocialProfile per archetype, bounded by Prem 2021
   Spain contact-matrix priors. (Reused from social_profiles.json when present.)
2. graph_builder constructs four layers (household, workplace, school, community)
   parameterised by the archetype social profiles, looked up via archetype_id.
3. metrics validates the resulting topology.

Public API
──────────
    from networks import build_network_from_profiles, profiles_to_archetype_map
"""

from .schema import SocialProfile, NetworkLayers
from .exp04_social import run as run_exp04
from .graph_builder import build_network
from .metrics import compute_network_metrics, print_summary


def profiles_to_archetype_map(archetypes: list, social_profiles: list) -> dict:
    """{archetype_id: SocialProfile} keyed by each archetype's agent_id."""
    return {
        a.get("agent_id", f"ARCH-{i:03d}"): p
        for i, (a, p) in enumerate(zip(archetypes, social_profiles))
    }


def build_network_from_profiles(
    archetypes:      list,
    population:      list,
    households:      list,
    social_profiles: list,
    rng_seed:        int = 42,
) -> tuple:
    """
    Build the four-layer network from already-generated social profiles.

    Returns (layers, net_metrics).
    """
    sp_by_arch = profiles_to_archetype_map(archetypes, social_profiles)
    print("  Building network layers...")
    layers = build_network(population, households, sp_by_arch, rng_seed=rng_seed)
    print("  Computing network metrics (incl. realized assortativity)...")
    net_metrics = compute_network_metrics(layers, population=population, rng_seed=rng_seed)
    return layers, net_metrics


__all__ = [
    "SocialProfile",
    "NetworkLayers",
    "run_exp04",
    "build_network",
    "build_network_from_profiles",
    "profiles_to_archetype_map",
    "compute_network_metrics",
    "print_summary",
]
