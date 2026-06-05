"""
EXP01 — GRAVITY-style archetype generation.

Based on: "GRAVITY: Profile-Grounded Synthetic Preferences" (Oct 2025).
The full world context is cached in the system prompt (one cache hit per archetype call).
Each seed is grounded in the real social, economic, and political conditions of the country.

Phase 1: one LLM call per seed (world context cached) → N archetypes.
Phase 2: expand archetypes to population_size agents (shared, no LLM calls).
"""

from models.base import ModelClient
from .base import generate_profile, demo_to_str, GENERATION_INSTRUCTION
from .seeds import generate_seeds
from .expand import expand
from config import ANDORRA_WORLD_CONTEXT

SYSTEM = f"""You generate behavioral preference profiles for synthetic residents.
Use the following world context to ground each profile in the real social, economic,
and political conditions the person actually lives in.

{ANDORRA_WORLD_CONTEXT}

{GENERATION_INSTRUCTION}"""


def run(
    n_archetypes: int,
    population_size: int,
    client: ModelClient,
) -> tuple[list[dict], list[dict], list]:
    """
    Returns: (archetypes, population, usages)
    """
    seeds = generate_seeds(n_archetypes)

    archetypes, usages = [], []
    for i, seed in enumerate(seeds):
        profile, usage = generate_profile(
            system=SYSTEM,
            user_msg=(
                f"Generate a preference profile for this resident:\n{demo_to_str(seed)}\n\n"
                "Ground the profile in their likely lived experience given the world context above."
            ),
            agent_id=f"EXP01-ARCH-{i:03d}",
            client=client,
            use_cache=True,  # world context cached across all archetype calls
        )
        profile["nationality"]    = seed["nationality"]
        profile["income_bracket"] = seed["income_bracket"]
        profile["age"]            = seed["age"]
        archetypes.append(profile)
        usages.append(usage)
        print(f"  EXP01 archetype [{i+1:02d}/{n_archetypes}]", end="\r")
    print()

    population = expand(archetypes, seeds, population_size)
    return archetypes, population, usages
