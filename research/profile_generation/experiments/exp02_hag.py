"""
EXP02 — HAG-style archetype generation.

Based on: "HAG: Hierarchical Demographic tree-based Agent Generation" (Jan 2026).
Each seed is mapped to a branch in Andorra's demographic tree before the LLM call.
Branch constraints enforce distributional coherence at generation time.
World context is cached; branch constraints are per-seed (not cached).

Phase 1: one LLM call per seed (world context cached, branch constraints per call) → N archetypes.
Phase 2: expand archetypes to population_size agents (shared, no LLM calls).
"""

from models.base import ModelClient
from .base import generate_profile, demo_to_str, GENERATION_INSTRUCTION
from .seeds import generate_seeds
from .expand import expand
from config import ANDORRA_WORLD_CONTEXT
from graph.andorra import ANDORRA_GRAPH
from graph import get_constraints

SYSTEM = f"""You generate behavioral preference profiles for synthetic residents of Andorra.
Use the world context and the demographic branch constraints below to produce
a profile that is internally coherent with the sociological position of this person.

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
        branch = get_constraints(ANDORRA_GRAPH, seed)
        profile, usage = generate_profile(
            system=SYSTEM,
            user_msg=(
                f"Generate a preference profile for this resident.\n\n"
                f"Demographics: {demo_to_str(seed)}\n\n"
                f"{branch}\n\n"
                "Generate values within the constraint ranges above. "
                "Correlations must be internally consistent "
                "(e.g. high financial_stress → higher loss_aversion, lower savings_orientation)."
            ),
            agent_id=f"EXP02-ARCH-{i:03d}",
            client=client,
            use_cache=True,
        )
        profile["nationality"]    = seed["nationality"]
        profile["income_bracket"] = seed["income_bracket"]
        profile["age"]            = seed["age"]
        archetypes.append(profile)
        usages.append(usage)
        print(f"  EXP02 archetype [{i+1:02d}/{n_archetypes}]", end="\r")
    print()

    population = expand(archetypes, seeds, population_size)
    return archetypes, population, usages
