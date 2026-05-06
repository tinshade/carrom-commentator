"""Unit tests for CommentaryEngine, prompt building, and Fakes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.commentary.llm import FakeLLMClient
from carrom_caster.commentary.prompts import build_user_prompt, load_system_prompt
from carrom_caster.commentary.tts import FakeTTSEngine
from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchMode
from carrom_caster.domain.player import Player, Team
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules
from carrom_caster.scoring.four_player import FourPlayerRules

_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

PA = Player(id=uuid4(), name="Alice")
PB = Player(id=uuid4(), name="Bob")
PC = Player(id=uuid4(), name="Charlie")
PD = Player(id=uuid4(), name="Diana")
TEAM_W = Team(id="team_white", name="Team White", players=(PA, PC))
TEAM_B = Team(id="team_black", name="Team Black", players=(PB, PD))


def _ev(event_type: EventType, ts: datetime = _TS, **payload: object) -> GameEvent:
    return GameEvent(type=event_type, timestamp=ts, frame_index=0, payload=dict(payload))


def _3p_state():
    return Scorer(ThreePlayerRules()).initial_state(uuid4(), [PA, PB, PC])


def _4p_state():
    return Scorer(FourPlayerRules()).initial_state(uuid4(), [PA, PB, PC, PD], [TEAM_W, TEAM_B])


def _engine(debounce_ms: int = 500) -> tuple[CommentaryEngine, FakeLLMClient, FakeTTSEngine]:
    llm = FakeLLMClient()
    tts = FakeTTSEngine()
    engine = CommentaryEngine(
        llm=llm, tts=tts, system_prompt="Be dramatic.", debounce_ms=debounce_ms
    )
    return engine, llm, tts


# ── CommentaryEngine ──────────────────────────────────────────────────────────

class TestEngineOnEvent:
    def test_calls_llm_and_tts(self) -> None:
        engine, llm, tts = _engine()
        ev = _ev(EventType.COIN_POCKETED, color="white", coin_id="w1", pocket_corner="top_left")
        result = engine.on_event(ev, _3p_state())
        assert result == llm._response
        assert len(llm.calls) == 1
        assert tts.spoken == [llm._response]

    def test_returns_commentary_text(self) -> None:
        engine, llm, _ = _engine()
        llm._response = "OH MY GOODNESS!"
        ev = _ev(EventType.QUEEN_POCKETED, pocket_corner="top_right")
        result = engine.on_event(ev, _3p_state())
        assert result == "OH MY GOODNESS!"

    def test_passes_system_prompt_to_llm(self) -> None:
        engine, llm, _ = _engine()
        ev = _ev(EventType.COIN_POCKETED, color="black", coin_id="b1", pocket_corner="bottom_left")
        engine.on_event(ev, _3p_state())
        assert llm.calls[0][0] == "Be dramatic."

    def test_passes_max_tokens_to_llm(self) -> None:
        llm = FakeLLMClient()
        tts = FakeTTSEngine()
        engine = CommentaryEngine(llm=llm, tts=tts, system_prompt="s", max_tokens=42)
        ev = _ev(EventType.COIN_POCKETED, color="white", coin_id="w1", pocket_corner="top_left")
        engine.on_event(ev, _3p_state())
        assert llm.calls[0][2] == 42


class TestEngineSkips:
    def test_skips_strike_taken(self) -> None:
        engine, llm, tts = _engine()
        result = engine.on_event(_ev(EventType.STRIKE_TAKEN), _3p_state())
        assert result is None
        assert len(llm.calls) == 0
        assert tts.spoken == []

    def test_skips_turn_ended(self) -> None:
        engine, llm, tts = _engine()
        result = engine.on_event(_ev(EventType.TURN_ENDED), _3p_state())
        assert result is None
        assert len(llm.calls) == 0


class TestEngineDebounce:
    def test_debounces_same_event_type_within_window(self) -> None:
        engine, llm, _ = _engine(debounce_ms=500)
        state = _3p_state()
        ev1 = _ev(EventType.COIN_POCKETED, ts=_TS, color="white", coin_id="w1", pocket_corner="tl")
        ev2 = _ev(EventType.COIN_POCKETED, ts=_TS + timedelta(milliseconds=100), color="white", coin_id="w2", pocket_corner="tr")
        engine.on_event(ev1, state)
        result = engine.on_event(ev2, state)
        assert result is None
        assert len(llm.calls) == 1

    def test_passes_after_debounce_window(self) -> None:
        engine, llm, _ = _engine(debounce_ms=500)
        state = _3p_state()
        ev1 = _ev(EventType.COIN_POCKETED, ts=_TS, color="white", coin_id="w1", pocket_corner="tl")
        ev2 = _ev(EventType.COIN_POCKETED, ts=_TS + timedelta(milliseconds=600), color="white", coin_id="w2", pocket_corner="tr")
        engine.on_event(ev1, state)
        result = engine.on_event(ev2, state)
        assert result is not None
        assert len(llm.calls) == 2

    def test_different_event_types_not_debounced(self) -> None:
        engine, llm, _ = _engine(debounce_ms=500)
        state = _3p_state()
        ev1 = _ev(EventType.COIN_POCKETED, ts=_TS, color="white", coin_id="w1", pocket_corner="tl")
        ev2 = _ev(EventType.QUEEN_POCKETED, ts=_TS + timedelta(milliseconds=100), pocket_corner="tr")
        engine.on_event(ev1, state)
        result = engine.on_event(ev2, state)
        assert result is not None
        assert len(llm.calls) == 2

    def test_zero_debounce_never_skips(self) -> None:
        engine, llm, _ = _engine(debounce_ms=0)
        state = _3p_state()
        for i in range(3):
            ev = _ev(EventType.COIN_POCKETED, ts=_TS + timedelta(milliseconds=i), color="white", coin_id=f"w{i}", pocket_corner="tl")
            engine.on_event(ev, state)
        assert len(llm.calls) == 3


# ── Prompt building ───────────────────────────────────────────────────────────

class TestBuildUserPrompt:
    def test_contains_player_name(self) -> None:
        state = _3p_state()
        ev = _ev(EventType.COIN_POCKETED, color="white", coin_id="w1", pocket_corner="top_left")
        prompt = build_user_prompt(ev, state)
        assert "Alice" in prompt

    def test_contains_score(self) -> None:
        state = _3p_state()
        ev = _ev(EventType.COIN_POCKETED, color="black", coin_id="b1", pocket_corner="top_right")
        prompt = build_user_prompt(ev, state)
        assert "pts" in prompt

    def test_contains_coin_counts(self) -> None:
        state = _3p_state()
        ev = _ev(EventType.QUEEN_POCKETED, pocket_corner="top_left")
        prompt = build_user_prompt(ev, state)
        assert "white" in prompt
        assert "black" in prompt

    def test_4p_includes_boards_won(self) -> None:
        state = _4p_state()
        ev = _ev(EventType.COIN_POCKETED, color="white", coin_id="w1", pocket_corner="top_left")
        prompt = build_user_prompt(ev, state)
        assert "Boards won" in prompt

    def test_3p_no_boards_won(self) -> None:
        state = _3p_state()
        ev = _ev(EventType.COIN_POCKETED, color="white", coin_id="w1", pocket_corner="top_left")
        prompt = build_user_prompt(ev, state)
        assert "Boards won" not in prompt

    def test_queen_covered_description(self) -> None:
        state = _3p_state()
        ev = _ev(EventType.QUEEN_COVERED)
        prompt = build_user_prompt(ev, state)
        assert "queen" in prompt.lower()


# ── FakeLLMClient ─────────────────────────────────────────────────────────────

class TestFakeLLMClient:
    def test_returns_configured_response(self) -> None:
        llm = FakeLLMClient(response="TEST RESPONSE")
        result = llm.complete("sys", "user", 60)
        assert result == "TEST RESPONSE"

    def test_records_calls(self) -> None:
        llm = FakeLLMClient()
        llm.complete("sys1", "user1", 30)
        llm.complete("sys2", "user2", 60)
        assert len(llm.calls) == 2
        assert llm.calls[0] == ("sys1", "user1", 30)
        assert llm.calls[1] == ("sys2", "user2", 60)


# ── FakeTTSEngine ─────────────────────────────────────────────────────────────

class TestFakeTTSEngine:
    def test_records_spoken(self) -> None:
        tts = FakeTTSEngine()
        tts.speak("Hello!")
        tts.speak("World!")
        assert tts.spoken == ["Hello!", "World!"]
