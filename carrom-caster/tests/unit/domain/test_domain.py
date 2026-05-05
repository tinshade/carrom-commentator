"""Unit tests for domain types — structural + immutability invariants."""
from __future__ import annotations

from uuid import uuid4

import pytest

from carrom_caster.domain.coin import Coin, CoinColor, Point
from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import PlayerScore
from carrom_caster.domain.player import Player, Team
from tests.conftest import _TS


class TestCoin:
    def test_frozen(self):
        coin = Coin(id="w1", color=CoinColor.WHITE, position=Point(0.1, 0.2), on_board=True)
        with pytest.raises(AttributeError):
            coin.id = "w2"  # type: ignore[misc]

    def test_point_normalized(self):
        p = Point(0.5, 0.5)
        assert p.x == 0.5
        assert p.y == 0.5


class TestGameEvent:
    def test_frozen_field(self):
        ev = GameEvent(type=EventType.TURN_ENDED, timestamp=_TS, frame_index=0, payload={})
        with pytest.raises(AttributeError):
            ev.type = EventType.COIN_POCKETED  # type: ignore[misc]

    def test_payload_accessible(self):
        ev = GameEvent(
            type=EventType.COIN_POCKETED,
            timestamp=_TS,
            frame_index=5,
            payload={"color": "white", "coin_id": "w1"},
        )
        assert ev.payload["color"] == "white"


class TestPlayer:
    def test_frozen(self):
        p = Player(id=uuid4(), name="Alice")
        with pytest.raises(AttributeError):
            p.name = "Bob"  # type: ignore[misc]


class TestPlayerScore:
    def test_frozen(self):
        ps = PlayerScore(player_id=uuid4(), points=5)
        with pytest.raises(AttributeError):
            ps.points = 10  # type: ignore[misc]


class TestTeam:
    def test_players_tuple(self):
        a = Player(id=uuid4(), name="A")
        b = Player(id=uuid4(), name="B")
        team = Team(id="t1", name="T1", players=(a, b))
        assert len(team.players) == 2
        assert isinstance(team.players, tuple)
