"""
EXP04 — LLM-generated social profiles per archetype.

Mirrors EXP01 (GRAVITY): the LLM acts as a generative prior for parameters
that are not directly available for Andorra, bounded by Prem 2021 Spain
contact matrix priors (contact_priors.py).

One LLM call per archetype (75 calls total with world-context cache).
Falls back to Prem 2021 Spain defaults if JSON parsing fails after retry.

Output: one SocialProfile per archetype, in the same order as the
archetypes list passed in.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from models.base import ModelClient, GenerationResult
from .schema import SocialProfile, SOCIAL_PROFILE_SCHEMA
from .contact_priors import get_priors, get_bounds


# ── System prompt (cached across all 75 archetype calls) ─────────────────────

SYSTEM = """You are a computational social scientist generating social connectivity profiles for a synthetic population of Andorra.

Andorra context (relevant to social network parameterisation):
- ~77,000 residents in 467 km², 7 parishes. ~55% foreign-born.
  Nationalities: Andorran 35.6%, Spanish 33.5%, Portuguese 17.1%, French 6.6%, Other 7.2%.
- Economy: tourism/retail (55%), finance (15%), construction (5%), public sector (10%).
- Small-country social fabric: overlapping professional/social networks. People repeatedly
  cross paths across institutional settings (work, school, market, civic).
- Naturalisation requires 20 years residence → immigrant communities maintain strong
  ethnic in-group cohesion for years before gradual bridging develops.
- Cross-border commuters (~20K/day) from Spain and France have split social networks
  between Andorra and their origin country.
- High car dependency; parishes are physically separated by mountain topography,
  reducing incidental cross-community contact compared to flat dense cities.

Your task: given an archetype's full demographic profile and the Prem 2021 Spain
contact matrix priors for their age band, generate a realistic SocialProfile in JSON.

Parameter guidance:
  home_contacts      — constrained by Prem 2021 prior ±40%. Larger household types
                       (couple_with_children, multi_generational) → higher; single → lower.
  work_contacts      — constrained by Prem 2021 prior ±50%. Set to 0.0 for retired,
                       student, homemaker, or unemployed employment status.
  community_contacts — constrained by Prem 2021 prior ±50% (up to +60% for Andorra's
                       small-country overlap effect). Civically active, high-bridging,
                       or tourism-sector agents may reach the upper bound.
  workplace_k        — NWS nearest neighbours (integer 2–8). Default 4 (Jiang et al.
                       2022 validated for urban populations). Finance/professional roles:
                       lower k (2–3, specialist networks). Hospitality/retail: higher k
                       (5–6, broad daily customer contact).
  workplace_p        — NWS shortcut probability (0.05–0.50). Default 0.3. Higher for
                       open, high-bridging agents who bridge across cliques.
  nationality_homophily — anchor to Putnam bonding_capital. Recent immigrants with
                          high bonding_capital → 0.7–0.9. Long-term or Andorran
                          nationals with moderate bridging → 0.3–0.6.
  age_homophily      — anchored to household_composition and sector. Shared
                       accommodation or student environments → lower (0.2–0.4).
                       Senior or family-centred agents → higher (0.5–0.7).
  bridging_weight    — must be numerically close to bridging_capital in the profile.
                       Andorra's small scale amplifies bridging relative to Spain.

Output ONLY valid JSON matching the schema exactly. No markdown fences, no prose."""


def _build_prompt(archetype: dict, idx: int) -> str:
    age    = archetype.get("age", 35)
    priors = get_priors(age)
    bounds = get_bounds(age)

    arch_display = {k: v for k, v in archetype.items() if k != "place_preferences"}

    return (
        f"Archetype [{idx:03d}] profile:\n"
        f"{json.dumps(arch_display, indent=2)}\n\n"
        f"Prem 2021 Spain contact priors for age {age} "
        f"({_age_band_label(age)} band):\n"
        f"  home_contacts      prior {priors['home_contacts']:.1f}  "
        f"  allowed {bounds['home_contacts'][0]:.1f}–{bounds['home_contacts'][1]:.1f}\n"
        f"  work_contacts      prior {priors['work_contacts']:.1f}  "
        f"  allowed {bounds['work_contacts'][0]:.1f}–{bounds['work_contacts'][1]:.1f}\n"
        f"  community_contacts prior {priors['community_contacts']:.1f}  "
        f"  allowed {bounds['community_contacts'][0]:.1f}–{bounds['community_contacts'][1]:.1f}\n\n"
        f"Output JSON matching this schema:\n{SOCIAL_PROFILE_SCHEMA}"
    )


def _age_band_label(age: int) -> str:
    if age < 15:  return "child (0–14)"
    if age < 30:  return "young (15–29)"
    if age < 65:  return "adult (30–64)"
    return "senior (65+)"


def _parse(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text.strip())


def _to_profile(data: dict) -> SocialProfile:
    return SocialProfile(
        home_contacts         = float(data["home_contacts"]),
        work_contacts         = float(data["work_contacts"]),
        community_contacts    = float(data["community_contacts"]),
        workplace_k           = int(data["workplace_k"]),
        workplace_p           = float(data["workplace_p"]),
        nationality_homophily = float(data["nationality_homophily"]),
        age_homophily         = float(data["age_homophily"]),
        bridging_weight       = float(data["bridging_weight"]),
    )


def _fallback_profile(archetype: dict) -> SocialProfile:
    """Use Prem 2021 Spain defaults when LLM parsing fails."""
    age   = archetype.get("age", 35)
    p     = get_priors(age)
    bridg = float(archetype.get("social", {}).get("bridging_capital", 0.4))
    return SocialProfile(
        home_contacts         = p["home_contacts"],
        work_contacts         = p["work_contacts"],
        community_contacts    = p["community_contacts"],
        workplace_k           = 4,
        workplace_p           = 0.3,
        nationality_homophily = max(0.1, 0.8 - bridg),   # high bridging → lower homophily
        age_homophily         = 0.4,
        bridging_weight       = bridg,
    )


def run(
    archetypes: list,
    client: ModelClient,
) -> tuple:
    """
    Generate one SocialProfile per archetype.

    Parameters
    ──────────
    archetypes : list of archetype profile dicts (output of EXP01)
    client     : ModelClient instance

    Returns
    ───────
    (profiles: list[SocialProfile], usages: list[GenerationResult])
    One profile per archetype, in the same order.
    """
    profiles: list = []
    usages:   list = []
    n = len(archetypes)

    for i, arch in enumerate(archetypes):
        prompt = _build_prompt(arch, i)
        profile = None
        last_result = None

        for attempt in range(2):
            result = client.generate(system=SYSTEM, user_msg=prompt, use_cache=True)
            last_result = result
            try:
                data = _parse(result.text)
                profile = _to_profile(data)
                break
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                if attempt == 1:
                    profile = _fallback_profile(arch)

        profiles.append(profile)
        usages.append(last_result)
        print(f"  EXP04 social profile [{i+1:02d}/{n}]  "
              f"home={profile.home_contacts:.1f} work={profile.work_contacts:.1f} "
              f"k={profile.workplace_k} p={profile.workplace_p:.2f} "
              f"nat_hom={profile.nationality_homophily:.2f}", end="\r")

    print()
    return profiles, usages
