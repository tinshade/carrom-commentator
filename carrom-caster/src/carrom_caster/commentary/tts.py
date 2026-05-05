from __future__ import annotations

from typing import Any, Protocol


class TTSEngine(Protocol):
    def speak(self, text: str) -> None: ...


class FakeTTSEngine:
    """In-memory fake — records spoken lines for test assertions."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


class Pyttsx3Engine:
    """Windows SAPI TTS via pyttsx3 — default offline provider."""

    def __init__(self, rate: int = 175) -> None:
        self._rate = rate
        self._engine: Any = None

    def _init(self) -> Any:
        if self._engine is None:
            try:
                import pyttsx3
            except ImportError:
                raise RuntimeError("pyttsx3 not installed — run: uv sync --extra commentary")
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
        return self._engine

    def speak(self, text: str) -> None:
        engine = self._init()
        engine.say(text)
        engine.runAndWait()
