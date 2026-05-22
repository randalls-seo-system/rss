"""Unified LLM dispatch for Claude CLI and OpenAI.

Replaces v1's inline call_claude_cli and call_openai. Adds retry logic,
caching of identical prompts, and structured error handling.

See docs/v2-module-architecture.md "lib/llm_client.py" for API contract.
"""

import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

CACHE_DIR = Path.home() / ".cache" / "rss-llm"

# Approximate pricing per million tokens (input, output).
# Claude CLI is subscription-covered so cost is informational only.
PRICING: dict[str, tuple[float, float]] = {
    "opus":         (15.00, 75.00),
    "sonnet":       (3.00,  15.00),
    "gpt-5.4-mini": (0.75,  4.50),
    "gpt-5.4":      (2.50,  20.00),
}

DEFAULT_MODELS: dict[str, str] = {
    "claude_cli": "opus",
    "openai":     "gpt-5.4-mini",
}

MAX_RETRIES = 2
BACKOFF_BASE = 1  # seconds


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost_estimate: float
    cached: bool
    provider: str
    model: str


class LLMClient:
    """Unified LLM client with caching and retry.

    Args:
        provider: 'claude_cli' or 'openai'.
        model: Model name override. Defaults per provider if None.
    """

    def __init__(self, provider: Literal["claude_cli", "openai"], model: str | None = None):
        if provider not in ("claude_cli", "openai"):
            raise ValueError(f"Unknown provider '{provider}'. Use 'claude_cli' or 'openai'.")
        self.provider = provider
        self.model = model or DEFAULT_MODELS[provider]

        if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY not set. Required for provider='openai'. "
                "Set it in your environment or .env file."
            )

    def call(
        self,
        prompt: str,
        system_msg: str | None = None,
        max_tokens: int = 4096,
        cache_key: str | None = None,
    ) -> LLMResponse:
        """Call the LLM, with optional disk-backed caching.

        Args:
            prompt: The user prompt text.
            system_msg: Optional system message.
            max_tokens: Max tokens for the response.
            cache_key: If set, enables per-section caching. Cache is keyed
                on (provider, model, cache_key, prompt).

        Returns:
            LLMResponse with text, token counts, and cost estimate.
        """
        # Check cache
        if cache_key is not None:
            cached = self._load_cache(prompt, cache_key)
            if cached is not None:
                return cached

        # Call with retries
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if self.provider == "claude_cli":
                    text, inp, out = self._call_claude_cli(prompt, system_msg, max_tokens)
                else:
                    text, inp, out = self._call_openai(prompt, system_msg, max_tokens)

                cost = self._estimate_cost(inp, out)
                response = LLMResponse(
                    text=text,
                    input_tokens=inp,
                    output_tokens=out,
                    cost_estimate=round(cost, 6),
                    cached=False,
                    provider=self.provider,
                    model=self.model,
                )

                if cache_key is not None:
                    self._save_cache(prompt, cache_key, response)

                return response

            except (subprocess.TimeoutExpired, OSError, ConnectionError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** attempt)
                    time.sleep(wait)
                continue

        raise RuntimeError(
            f"LLM call failed after {MAX_RETRIES + 1} attempts: {last_error}"
        ) from last_error

    def _call_claude_cli(
        self, prompt: str, system_msg: str | None, max_tokens: int
    ) -> tuple[str, int, int]:
        """Call Claude via the Claude Code CLI.

        Token counts not available via CLI — returns 0 for both.
        Cost is subscription-covered.
        """
        full_prompt = prompt
        if system_msg:
            full_prompt = f"[System: {system_msg}]\n\n{prompt}"

        result = subprocess.run(
            ["claude", "--model", self.model, "--print"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI failed (exit {result.returncode}): {result.stderr[:500]}"
            )
        return result.stdout.strip(), 0, 0

    def _call_openai(
        self, prompt: str, system_msg: str | None, max_tokens: int
    ) -> tuple[str, int, int]:
        """Call OpenAI API. Returns (text, input_tokens, output_tokens)."""
        from openai import OpenAI

        client = OpenAI()
        messages: list[dict[str, str]] = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": prompt})

        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=max_tokens,
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return text, usage.prompt_tokens, usage.completion_tokens

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost from token counts. Informational only."""
        if self.provider == "claude_cli":
            return 0.0  # subscription-covered
        rates = PRICING.get(self.model, (0.0, 0.0))
        return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000

    def _cache_hash(self, prompt: str, cache_key: str) -> str:
        """Compute cache file hash from (provider, model, cache_key, prompt)."""
        key_material = f"{self.provider}|{self.model}|{cache_key}|{prompt}"
        return hashlib.sha256(key_material.encode()).hexdigest()

    def _cache_path(self, prompt: str, cache_key: str) -> Path:
        return CACHE_DIR / f"{self._cache_hash(prompt, cache_key)}.json"

    def _load_cache(self, prompt: str, cache_key: str) -> LLMResponse | None:
        path = self._cache_path(prompt, cache_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            data["cached"] = True
            return LLMResponse(**data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _save_cache(self, prompt: str, cache_key: str, response: LLMResponse) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(prompt, cache_key)
        path.write_text(json.dumps(asdict(response), indent=2))
