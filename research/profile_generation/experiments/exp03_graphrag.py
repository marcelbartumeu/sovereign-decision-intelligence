"""
EXP03 — GraphRAG + GRAVITY archetype generation.

Combines GRAVITY's holistic world-context grounding (cached system prompt) with
graph-retrieved narrative context injected per-call into the user message.

Unlike HAG (EXP02), which injects explicit field-by-field numerical constraints,
this experiment retrieves qualitative sociological narratives from the knowledge graph
and lets the LLM infer behavioral parameters from that context. This preserves
GRAVITY's coherent reasoning while adding demographically-specific grounding.

Hypothesis: narrative retrieval outperforms both GRAVITY (richer per-seed context)
and HAG (avoids mechanical constraint satisfaction that fragments holistic reasoning).

Phase 1: one LLM call per seed (world context cached, narratives per call) → N archetypes.
Phase 2: expand archetypes to population_size agents (shared, no LLM calls).
"""

from models.base import ModelClient
from .base import generate_profile, demo_to_str, GENERATION_INSTRUCTION
from .seeds import generate_seeds
from .expand import expand
from config import ANDORRA_WORLD_CONTEXT
from graph.andorra import ANDORRA_GRAPH
from graph import get_narratives

SYSTEM = f"""You generate behavioral preference profiles for synthetic residents of Andorra.
Use the world context and the retrieved sociological context below to produce a profile
that is internally coherent with the lived experience of this specific person.

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
        context = get_narratives(ANDORRA_GRAPH, seed)
        profile, usage = generate_profile(
            system=SYSTEM,
            user_msg=(
                f"Generate a preference profile for this resident.\n\n"
                f"Demographics: {demo_to_str(seed)}\n\n"
                f"{context}\n\n"
                "Use the sociological context above to infer this person's behavioral tendencies. "
                "Reason from their lived situation — do not mechanically fill ranges. "
                "Ensure all values are internally consistent."
            ),
            agent_id=f"EXP03-ARCH-{i:03d}",
            client=client,
            use_cache=True,
        )
        profile["nationality"]    = seed["nationality"]
        profile["income_bracket"] = seed["income_bracket"]
        profile["age"]            = seed["age"]
        archetypes.append(profile)
        usages.append(usage)
        print(f"  EXP03 archetype [{i+1:02d}/{n_archetypes}]", end="\r")
    print()

    population = expand(archetypes, seeds, population_size)
    return archetypes, population, usages
