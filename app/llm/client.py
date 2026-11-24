"""Groq (OpenAI-compatible) chat client."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    """Raised when the provider cannot return usable text."""


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        """Send a prompt and return the assistant text."""


class GroqClient:
    """HTTP adapter for Groq's OpenAI-compatible chat completions API."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url.rstrip("/")
        self._model = settings.llm_model
        self._timeout = settings.llm_timeout_seconds
        self._verify = settings.llm_ssl_verify

    def complete(self, prompt: str) -> str:
        if not self._api_key:
            raise LLMClientError("LLM_API_KEY is not set")

        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You rank restaurants from a supplied candidate list. "
                        "Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        try:
            with httpx.Client(timeout=self._timeout, verify=self._verify) as client:
                response = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise LLMClientError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMClientError(
                f"LLM HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
            message = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("LLM response was missing chat content") from exc

        content = message.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise LLMClientError("LLM response content was not text")
        return content
