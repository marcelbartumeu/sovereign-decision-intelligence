"""
Anthropic Claude client with prompt caching support.

Pricing (claude-sonnet-4-6 / claude-haiku-4-5):
  Input:       $3.00 / $0.80  per 1M tokens
  Output:      $15.00 / $4.00 per 1M tokens
  Cache write: $3.75 / $1.00  per 1M tokens
  Cache read:  $0.30 / $0.08  per 1M tokens
"""

from __future__ import annotations
import anthropic
from .base import ModelClient, GenerationResult

PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80, "output": 4.00, "cache_write": 1.00, "cache_read": 0.08,
    },
}


class ClaudeClient(ModelClient):
    def __init__(self, model_id: str, api_key: str):
        self.model_id = model_id
        self.display_name = model_id.replace("claude-", "").replace("-20251001", "")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._price = PRICING.get(model_id, PRICING["claude-sonnet-4-6"])

    def generate(self, system: str, user_msg: str, use_cache: bool = False) -> GenerationResult:
        system_content = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if use_cache else system
        )
        resp = self._client.messages.create(
            model=self.model_id,
            max_tokens=1500,
            system=system_content,
            messages=[{"role": "user", "content": user_msg}],
        )
        u = resp.usage
        input_tok  = u.input_tokens
        output_tok = u.output_tokens
        cache_read = getattr(u, "cache_read_input_tokens",  0) or 0
        cache_write= getattr(u, "cache_creation_input_tokens", 0) or 0

        cost = (
            (input_tok  / 1e6) * self._price["input"]  +
            (output_tok / 1e6) * self._price["output"] +
            (cache_write/ 1e6) * self._price["cache_write"] +
            (cache_read / 1e6) * self._price["cache_read"]
        )
        return GenerationResult(
            text=resp.content[0].text,
            input_tokens=input_tok,
            output_tokens=output_tok,
            cached_tokens=cache_read,
            cost_usd=cost,
        )
