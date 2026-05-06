from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str: ...


class FakeLLMClient:
    """In-memory fake — returns a fixed response; records all calls."""

    def __init__(self, response: str = "UNBELIEVABLE! WHAT A SHOT!") -> None:
        self._response = response
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return self._response


class OllamaClient:
    """Local Ollama inference — default offline provider."""

    def __init__(self, model: str = "llama3.2:3b") -> None:
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama not installed — run: uv sync --extra commentary")

        response = ollama.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"num_predict": max_tokens},
        )
        return str(response.message.content).strip()


class AnthropicClient:
    """Anthropic API — cloud provider, requires ANTHROPIC_API_KEY."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed — run: uv sync --extra commentary")

        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return str(message.content[0].text).strip()  # type: ignore[union-attr]
