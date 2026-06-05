"""
Google Gemini client via the OpenAI-compatible endpoint.

Using the OpenAI SDK with Gemini's compatibility layer avoids an extra
dependency (google-generativeai) while keeping the interface identical.

Compatibility endpoint: https://generativelanguage.googleapis.com/v1beta/openai/

Pricing (as of 2025):
  gemini-2.0-flash:  Input $0.10  / Output $0.40  per 1M tokens
  gemini-1.5-flash:  Input $0.075 / Output $0.30  per 1M tokens  (≤128k ctx)
  gemini-1.5-pro:    Input $1.25  / Output $5.00  per 1M tokens  (≤128k ctx)

Gemini does not offer per-request prompt caching in the standard API.
Context caching exists but requires explicit cache object creation — out of scope.
"""

from __future__ import annotations
from .base import ModelClient, GenerationResult

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

PRICING: dict[str, dict[str, float]] = {
    "gemini-2.0-flash":         {"input": 0.10,  "output": 0.40},
    "gemini-1.5-flash":         {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b":      {"input": 0.0375,"output": 0.15},
    "gemini-1.5-pro":           {"input": 1.25,  "output": 5.00},
}


class GeminiClient(ModelClient):
    def __init__(self, model_id: str, api_key: str):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")

        self.model_id = model_id
        self.display_name = model_id
        self._client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
        self._price = PRICING.get(model_id, PRICING["gemini-1.5-flash"])

    def generate(self, system: str, user_msg: str, use_cache: bool = False) -> GenerationResult:
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

        cost = (
            (input_tok  / 1e6) * self._price["input"] +
            (output_tok / 1e6) * self._price["output"]
        )
        return GenerationResult(
            text=resp.choices[0].message.content,
            input_tokens=input_tok,
            output_tokens=output_tok,
            cached_tokens=0,  # no per-request caching in standard Gemini API
            cost_usd=cost,
        )
