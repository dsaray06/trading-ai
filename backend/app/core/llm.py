"""Centralized Claude (Anthropic) client wrapper.

Per docs/08-coding-standards.md, all LLM calls go through one place; the model
name comes from config. Agents use this only for *reasoning prose* — never for
the numeric scores that must be deterministic (those are computed in pure
functions and unit-tested).

Graceful degradation: if no `ANTHROPIC_API_KEY` is configured, `generate_reasoning`
returns None and the caller falls back to a templated, deterministic explanation.
This keeps the app demoable and the test suite fully offline.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Thin wrapper over the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # lazily constructed on first use

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def generate_reasoning(self, system: str, prompt: str, max_tokens: int = 600) -> str | None:
        """Return a short natural-language explanation, or None on any failure.

        Callers must treat None as "LLM unavailable" and supply their own
        deterministic fallback text.
        """
        if not self.enabled:
            return None
        try:
            client = self._ensure_client()
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = [block.text for block in response.content if block.type == "text"]
            text = "".join(parts).strip()
            usage = response.usage
            logger.info(
                "Claude reasoning generated (model=%s, in=%d, out=%d tokens)",
                self._model,
                usage.input_tokens,
                usage.output_tokens,
            )
            return text or None
        except Exception as exc:  # noqa: BLE001 - never let LLM issues break a research run
            logger.warning("LLM reasoning generation failed: %s", exc)
            return None


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    return LLMClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
