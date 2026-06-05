"""
Unified model client interface for multi-provider experiments.

All providers implement the same generate() call so experiments are
model-agnostic. Cost tracking is built in per provider.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int   # prompt cache hits (provider-specific)
    cost_usd: float


class ModelClient(ABC):
    model_id: str
    display_name: str

    @abstractmethod
    def generate(self, system: str, user_msg: str, use_cache: bool = False) -> GenerationResult:
        """
        Generate a completion.

        system    : system prompt (cached if use_cache=True and provider supports it)
        user_msg  : user message (never cached — always unique per agent)
        use_cache : request prompt caching for the system prompt
        """
        ...
