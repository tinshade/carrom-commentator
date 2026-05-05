from __future__ import annotations

from datetime import datetime, timedelta

from carrom_caster.commentary.llm import LLMClient
from carrom_caster.commentary.prompts import build_user_prompt
from carrom_caster.commentary.tts import TTSEngine
from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchState

# These events fire too frequently or carry no narrative value.
_SKIP_EVENTS = frozenset({EventType.STRIKE_TAKEN, EventType.TURN_ENDED})


class CommentaryEngine:
    """Receives game events, generates LLM commentary, speaks via TTS.

    Debounce uses event timestamps so it works identically in CLI replay
    and live pipeline.
    """

    def __init__(
        self,
        llm: LLMClient,
        tts: TTSEngine,
        system_prompt: str,
        max_tokens: int = 60,
        debounce_ms: int = 500,
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._debounce = timedelta(milliseconds=debounce_ms)
        self._last_spoken: dict[EventType, datetime] = {}

    def on_event(self, event: GameEvent, state: MatchState) -> str | None:
        """Process one event. Returns commentary text, or None if skipped."""
        if event.type in _SKIP_EVENTS:
            return None

        last = self._last_spoken.get(event.type)
        if last is not None and (event.timestamp - last) < self._debounce:
            return None

        user_prompt = build_user_prompt(event, state)
        commentary = self._llm.complete(self._system_prompt, user_prompt, self._max_tokens)
        self._tts.speak(commentary)
        self._last_spoken[event.type] = event.timestamp
        return commentary
