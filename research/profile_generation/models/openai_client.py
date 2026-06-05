"""
OpenAI client (GPT-4o, GPT-4o-mini).

OpenAI applies automatic prompt caching for prompts > 1024 tokens
(no explicit opt-in required). Cached tokens are reported in usage.

Pricing:
  gpt-4o:       Input $2.50 / Output $10.00 / Cached $1.25  per 1M tokens
  gpt-4o-mini:  Input $0.15 / Output $0.60  / Cached $0.075 per 1M tokens
"""

from __future__ import annotations
from .base import ModelClient, GenerationResult

PRICING: dict[str, dict[str, float]] = {
    "gpt-4o":      {"input": 2.50, "output": 10.00, "cached": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output":  0.60, "cached": 0.075},
}


class OpenAIClient(ModelClient):
    def __init__(self, model_id: str, api_key: str):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")

        self.model_id = model_id
        self.display_name = model_id
        self._client = OpenAI(api_key=api_key)
        self._price = PRICING.get(model_id, PRICING["gpt-4o"])

    def generate(self, system: str, user_msg: str, use_cache: bool = False) -> GenerationResult:
        # OpenAI caches automatically — use_cache flag has no effect on the API call
        resp = self._client.chat.completions.create(
            model=self.model_id,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        u = resp.usage
        input_tok  = u.prompt_tokens
        output_tok = u.completion_tokens
        cached_tok = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0

        # Cached tokens are billed at the lower cached rate; non-cached at full rate
        non_cached = input_tok - cached_tok
        cost = (
            (non_cached / 1e6) * self._price["input"]  +
            (cached_tok / 1e6) * self._price["cached"] +
            (output_tok / 1e6) * self._price["output"]
        )
        return GenerationResult(
            text=resp.choices[0].message.content,
            input_tokens=input_tok,
            output_tokens=output_tok,
            cached_tokens=cached_tok,
            cost_usd=cost,
        )
