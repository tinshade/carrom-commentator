"""Shared fixtures for all tests."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.player import Player, Team

# ── canonical player/team fixtures ────────────────────────────────────────────

PLAYER_A = Player(id=UUID("aaaaaaaa-0000-0000-0000-000000000001"), name="Alice")
PLAYER_B = Player(id=UUID("bbbbbbbb-0000-0000-0000-000000000002"), name="Bob")
PLAYER_C = Player(id=UUID("cccccccc-0000-0000-0000-000000000003"), name="Charlie")
PLAYER_D = Player(id=UUID("dddddddd-0000-0000-0000-000000000004"), name="Diana")

TEAM_WHITE = Team(id="team_white", name="Team White", players=(PLAYER_A, PLAYER_C))
TEAM_BLACK = Team(id="team_black", name="Team Black", players=(PLAYER_B, PLAYER_D))

PLAYERS_3P = [PLAYER_A, PLAYER_B, PLAYER_C]
PLAYERS_4P = [PLAYER_A, PLAYER_B, PLAYER_C, PLAYER_D]
TEAMS_4P = [TEAM_WHITE, TEAM_BLACK]


@pytest.fixture
def match_id() -> UUID:
    return uuid4()


# ── event factory helpers ──────────────────────────────────────────────────────

_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_event(
    event_type: EventType,
    frame_index: int = 0,
    **payload,
) -> GameEvent:
    return GameEvent(type=event_type, timestamp=_TS, frame_index=frame_index, payload=dict(payload))


def coin_pocketed(color: str, frame_index: int = 0) -> GameEvent:
    return make_event(EventType.COIN_POCKETED, frame_index=frame_index, color=color, coin_id="x")


def queen_pocketed(frame_index: int = 0) -> GameEvent:
    return make_event(EventType.QUEEN_POCKETED, frame_index=frame_index)


def striker_pocketed(frame_index: int = 0) -> GameEvent:
    return make_event(EventType.STRIKER_POCKETED, frame_index=frame_index)


def turn_ended(frame_index: int = 0) -> GameEvent:
    return make_event(EventType.TURN_ENDED, frame_index=frame_index)


def match_ended(frame_index: int = 0) -> GameEvent:
    return make_event(EventType.MATCH_ENDED, frame_index=frame_index)
