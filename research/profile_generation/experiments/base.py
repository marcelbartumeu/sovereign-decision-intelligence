"""Shared profile generation helper used by all experiments."""

import json
import re
from models.base import ModelClient, GenerationResult
from schema import OUTPUT_SCHEMA

GENERATION_INSTRUCTION = f"""
Output ONLY valid JSON matching this schema. No prose, no markdown fences, no explanations.
Remove all inline comments (// ...) before the JSON.

{OUTPUT_SCHEMA}
"""


def generate_profile(
    system: str,
    user_msg: str,
    agent_id: str,
    client: ModelClient,
    use_cache: bool = False,
) -> tuple[dict, GenerationResult]:
    """
    Generate one profile. Returns (profile_dict, GenerationResult).
    Retries once on JSON parse failure.
    """
    for attempt in range(2):
        result = client.generate(system=system, user_msg=user_msg, use_cache=use_cache)
        try:
            profile = _parse(result.text)
            profile["agent_id"] = agent_id
            return profile, result
        except (json.JSONDecodeError, ValueError):
            if attempt == 1:
                raise ValueError(
                    f"JSON parse failed after 2 attempts for {agent_id}.\n"
                    f"Raw output: {result.text[:300]}"
                )


def _parse(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text.strip())


def demo_to_str(demo: dict) -> str:
    return ", ".join(f"{k}: {v}" for k, v in demo.items())
