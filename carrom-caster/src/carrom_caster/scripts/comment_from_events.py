"""
CLI: read a JSON event log and speak live WWE-style commentary.

Usage:
    uv run python -m carrom_caster.scripts.comment_from_events <events.json> [--dry-run]

    --dry-run   Print commentary to stdout instead of speaking it.
                Requires no audio hardware or pyttsx3.

JSON format is identical to score_from_events.py.
Requires commentary extras: uv sync --extra commentary
"""
from __future__ import annotations

import sys
from pathlib import Path

from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.commentary.llm import OllamaClient
from carrom_caster.commentary.prompts import load_system_prompt
from carrom_caster.commentary.tts import Pyttsx3Engine
from carrom_caster.scripts.score_from_events import _load

_PROMPT_PATH = Path("config/prompts/wwe_commentary.txt")


class _PrintTTS:
    """TTS stub that prints instead of speaking — used with --dry-run."""

    def speak(self, text: str) -> None:
        print(f"  [TTS] {text}")


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: comment-from-events <events.json> [--dry-run]",
            file=sys.stderr,
        )
        return 1

    path = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    if not _PROMPT_PATH.exists():
        print(f"System prompt not found: {_PROMPT_PATH}", file=sys.stderr)
        return 1

    try:
        scorer, players, teams, events, match_id = _load(path)
    except (KeyError, ValueError) as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 1

    system_prompt = load_system_prompt(_PROMPT_PATH)
    llm = OllamaClient()
    tts: Pyttsx3Engine | _PrintTTS = _PrintTTS() if dry_run else Pyttsx3Engine()
    engine = CommentaryEngine(
        llm=llm,
        tts=tts,
        system_prompt=system_prompt,
        debounce_ms=0,  # CLI replay: no debounce, comment every event
    )

    state = scorer.initial_state(match_id, players, teams)
    for event in events:
        state = scorer.apply(state, event)
        commentary = engine.on_event(event, state)
        if commentary:
            print(f"[{event.type.value}] {commentary}")
        if not state.is_active:
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
