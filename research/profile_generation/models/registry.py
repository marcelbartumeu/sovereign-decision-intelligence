"""
Model registry — maps model name strings to client instances.
Reads API keys from environment variables.
"""

from __future__ import annotations
import os
from .base import ModelClient
from .claude import ClaudeClient
from .openai_client import OpenAIClient
from .gemini import GeminiClient

# Available models: display_name → (ClientClass, model_id, env_var)
REGISTRY: dict[str, tuple] = {
    "claude-sonnet":  (ClaudeClient,  "claude-sonnet-4-6",          "ANTHROPIC_API_KEY"),
    "claude-haiku":   (ClaudeClient,  "claude-haiku-4-5-20251001",   "ANTHROPIC_API_KEY"),
    "gpt-4o":         (OpenAIClient,  "gpt-4o",                      "OPENAI_API_KEY"),
    "gpt-4o-mini":    (OpenAIClient,  "gpt-4o-mini",                 "OPENAI_API_KEY"),
    "gemini-flash":   (GeminiClient,  "gemini-2.0-flash",            "GOOGLE_API_KEY"),
    "gemini-pro":     (GeminiClient,  "gemini-1.5-pro",              "GOOGLE_API_KEY"),
}


def load_model(name: str) -> ModelClient:
    """
    Instantiate a model client by name. Raises clearly if the API key is missing.

    Available names: claude-sonnet, claude-haiku, gpt-4o, gpt-4o-mini,
                     gemini-flash, gemini-pro
    """
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown model '{name}'. Available: {', '.join(REGISTRY)}"
        )
    ClientClass, model_id, env_var = REGISTRY[name]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise EnvironmentError(
            f"Model '{name}' requires {env_var} to be set in .env"
        )
    return ClientClass(model_id=model_id, api_key=api_key)


def available_models() -> list[str]:
    """Return names of models whose API keys are present in the environment."""
    available = []
    for name, (_, _, env_var) in REGISTRY.items():
        if os.environ.get(env_var):
            available.append(name)
    return available
