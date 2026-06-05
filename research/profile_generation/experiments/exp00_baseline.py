"""
EXP00 — Baseline archetype generation.

No world context, no sociological constraints — bare demographic seed → profile.
Establishes the floor: how much central-category compression exists without grounding?

Phase 1: one LLM call per seed → N archetypes.
Phase 2: expand archetypes to population_size agents (shared, no LLM calls).
"""

from models.base import ModelClient
from .base import generate_profile, demo_to_str, GENERATION_INSTRUCTION
from .seeds import generate_seeds
from .expand import expand

SYSTEM = "You generate behavioral preference profiles for synthetic individuals as JSON." + GENERATION_INSTRUCTION


def run(
    n_archetypes: int,
    population_size: int,
    client: ModelClient,
) -> tuple[list[dict], list[dict], list]:
    """
    Returns: (archetypes, population, usages)
      archetypes  — N LLM-generated profiles (one per seed)
      population  — population_size expanded profiles
      usages      — GenerationResult list (one per archetype)
    """
    seeds = generate_seeds(n_archetypes)

    archetypes, usages = [], []
    for i, seed in enumerate(seeds):
        profile, usage = generate_profile(
            system=SYSTEM,
            user_msg=f"Generate a preference profile for a person with these demographics:\n{demo_to_str(seed)}",
            agent_id=f"EXP00-ARCH-{i:03d}",
            client=client,
            use_cache=False,
        )
        profile["nationality"]    = seed["nationality"]
        profile["income_bracket"] = seed["income_bracket"]
        profile["age"]            = seed["age"]
        archetypes.append(profile)
        usages.append(usage)
        print(f"  EXP00 archetype [{i+1:02d}/{n_archetypes}]", end="\r")
    print()

    population = expand(archetypes, seeds, population_size)
    return archetypes, population, usages
