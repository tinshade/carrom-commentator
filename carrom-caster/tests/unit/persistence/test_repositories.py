"""Unit tests for PlayerGroupRepository and MatchRepository (Fake + SQLite)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchMode, MatchState, PlayerScore, QueenState
from carrom_caster.domain.player import Player, PlayerGroup, Team
from carrom_caster.persistence.repositories import (
    FakeMatchRepository,
    FakePlayerGroupRepository,
    SqliteMatchRepository,
    SqlitePlayerGroupRepository,
)
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules
from carrom_caster.scoring.four_player import FourPlayerRules

# ── constants ──────────────────────────────────────────────────────────────────

_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

PA = Player(id=UUID("aaaaaaaa-0000-0000-0000-000000000001"), name="Alice")
PB = Player(id=UUID("bbbbbbbb-0000-0000-0000-000000000002"), name="Bob")
PC = Player(id=UUID("cccccccc-0000-0000-0000-000000000003"), name="Charlie")
PD = Player(id=UUID("dddddddd-0000-0000-0000-000000000004"), name="Diana")

TEAM_W = Team(id="team_white", name="Team White", players=(PA, PC))
TEAM_B = Team(id="team_black", name="Team Black", players=(PB, PD))


def _mem_engine() -> sa.Engine:
    return sa.create_engine("sqlite:///:memory:")


def _group(name: str = "Weekend Crew", members: tuple[Player, ...] = (PA, PB, PC)) -> PlayerGroup:
    return PlayerGroup(id=uuid4(), name=name, members=members, last_used=_TS)


def _3p_state(match_id: UUID | None = None) -> MatchState:
    scorer = Scorer(ThreePlayerRules())
    return scorer.initial_state(match_id or uuid4(), [PA, PB, PC])


def _4p_state(match_id: UUID | None = None) -> MatchState:
    scorer = Scorer(FourPlayerRules())
    return scorer.initial_state(match_id or uuid4(), [PA, PB, PC, PD], [TEAM_W, TEAM_B])


def _ev(event_type: EventType, **payload: object) -> GameEvent:
    return GameEvent(type=event_type, timestamp=_TS, frame_index=0, payload=dict(payload))


# ── parametrized fixtures ──────────────────────────────────────────────────────

@pytest.fixture(params=["fake", "sqlite"])
def group_repo(request: pytest.FixtureRequest) -> FakePlayerGroupRepository | SqlitePlayerGroupRepository:
    if request.param == "fake":
        return FakePlayerGroupRepository()
    return SqlitePlayerGroupRepository(_mem_engine())


@pytest.fixture(params=["fake", "sqlite"])
def match_repo(request: pytest.FixtureRequest) -> FakeMatchRepository | SqliteMatchRepository:
    if request.param == "fake":
        return FakeMatchRepository()
    return SqliteMatchRepository(_mem_engine())


# ── PlayerGroupRepository tests ────────────────────────────────────────────────

class TestPlayerGroupSaveGet:
    def test_round_trip(self, group_repo: object) -> None:
        g = _group()
        group_repo.save(g)  # type: ignore[union-attr]
        loaded = group_repo.get(g.id)  # type: ignore[union-attr]
        assert loaded == g

    def test_get_nonexistent_returns_none(self, group_repo: object) -> None:
        assert group_repo.get(uuid4()) is None  # type: ignore[union-attr]

    def test_save_overwrites(self, group_repo: object) -> None:
        g = _group()
        group_repo.save(g)  # type: ignore[union-attr]
        updated = PlayerGroup(id=g.id, name="New Name", members=(PA,), last_used=_TS)
        group_repo.save(updated)  # type: ignore[union-attr]
        assert group_repo.get(g.id) == updated  # type: ignore[union-attr]

    def test_member_order_preserved(self, group_repo: object) -> None:
        g = PlayerGroup(id=uuid4(), name="g", members=(PC, PA, PB), last_used=_TS)
        group_repo.save(g)  # type: ignore[union-attr]
        loaded = group_repo.get(g.id)  # type: ignore[union-attr]
        assert loaded is not None
        assert loaded.members == (PC, PA, PB)


class TestPlayerGroupListAll:
    def test_empty(self, group_repo: object) -> None:
        assert group_repo.list_all() == []  # type: ignore[union-attr]

    def test_sorted_by_last_used_desc(self, group_repo: object) -> None:
        old = PlayerGroup(id=uuid4(), name="old", members=(PA,), last_used=_TS)
        new = PlayerGroup(
            id=uuid4(), name="new", members=(PB,), last_used=_TS + timedelta(hours=1)
        )
        group_repo.save(old)  # type: ignore[union-attr]
        group_repo.save(new)  # type: ignore[union-attr]
        result = group_repo.list_all()  # type: ignore[union-attr]
        assert result[0].name == "new"
        assert result[1].name == "old"


class TestPlayerGroupDelete:
    def test_delete_removes(self, group_repo: object) -> None:
        g = _group()
        group_repo.save(g)  # type: ignore[union-attr]
        group_repo.delete(g.id)  # type: ignore[union-attr]
        assert group_repo.get(g.id) is None  # type: ignore[union-attr]

    def test_delete_nonexistent_noop(self, group_repo: object) -> None:
        group_repo.delete(uuid4())  # type: ignore[union-attr]  # must not raise


class TestPlayerGroupTouch:
    def test_updates_last_used(self, group_repo: object) -> None:
        g = _group()
        group_repo.save(g)  # type: ignore[union-attr]
        later = _TS + timedelta(days=1)
        group_repo.touch(g.id, later)  # type: ignore[union-attr]
        loaded = group_repo.get(g.id)  # type: ignore[union-attr]
        assert loaded is not None
        assert loaded.last_used == later

    def test_touch_nonexistent_noop(self, group_repo: object) -> None:
        group_repo.touch(uuid4(), _TS)  # type: ignore[union-attr]  # must not raise


# ── MatchRepository tests ──────────────────────────────────────────────────────

class TestMatchSaveGet:
    def test_3p_round_trip(self, match_repo: object) -> None:
        s = _3p_state()
        match_repo.save(s)  # type: ignore[union-attr]
        loaded = match_repo.get(s.match_id)  # type: ignore[union-attr]
        assert loaded is not None
        assert loaded.match_id == s.match_id
        assert loaded.mode == MatchMode.THREE_PLAYER_FFA
        assert loaded.players_in_order == s.players_in_order
        assert loaded.teams == ()
        assert loaded.is_active == s.is_active

    def test_4p_round_trip(self, match_repo: object) -> None:
        s = _4p_state()
        match_repo.save(s)  # type: ignore[union-attr]
        loaded = match_repo.get(s.match_id)  # type: ignore[union-attr]
        assert loaded is not None
        assert loaded.mode == MatchMode.FOUR_PLAYER_PARTNERS
        assert len(loaded.teams) == 2
        assert loaded.teams[0].id == TEAM_W.id
        assert loaded.teams[1].id == TEAM_B.id
        assert set(p.id for p in loaded.teams[0].players) == {PA.id, PC.id}

    def test_get_nonexistent_returns_none(self, match_repo: object) -> None:
        assert match_repo.get(uuid4()) is None  # type: ignore[union-attr]

    def test_scores_round_trip(self, match_repo: object) -> None:
        s = _3p_state()
        match_repo.save(s)  # type: ignore[union-attr]
        loaded = match_repo.get(s.match_id)  # type: ignore[union-attr]
        assert loaded is not None
        score_ids = {ps.player_id for ps in loaded.player_scores}
        assert PA.id in score_ids

    def test_queen_pocketed_by_index_none(self, match_repo: object) -> None:
        s = _3p_state()
        match_repo.save(s)  # type: ignore[union-attr]
        loaded = match_repo.get(s.match_id)  # type: ignore[union-attr]
        assert loaded is not None
        assert loaded.queen_pocketed_by_index is None

    def test_history_round_trip(self, match_repo: object) -> None:
        scorer = Scorer(ThreePlayerRules())
        mid = uuid4()
        state = scorer.initial_state(mid, [PA, PB, PC])
        ev = _ev(EventType.COIN_POCKETED, coin_id="w1", color="white", pocket_corner="top_left")
        state = scorer.apply(state, ev)
        match_repo.save(state)  # type: ignore[union-attr]
        loaded = match_repo.get(mid)  # type: ignore[union-attr]
        assert loaded is not None
        assert len(loaded.history) == 1
        assert loaded.history[0].type == EventType.COIN_POCKETED
        assert loaded.history[0].payload["color"] == "white"

    def test_resave_updates_state(self, match_repo: object) -> None:
        scorer = Scorer(ThreePlayerRules())
        mid = uuid4()
        state = scorer.initial_state(mid, [PA, PB, PC])
        match_repo.save(state)  # type: ignore[union-attr]
        ev = _ev(EventType.COIN_POCKETED, coin_id="w1", color="white", pocket_corner="top_left")
        state2 = scorer.apply(state, ev)
        match_repo.save(state2)  # type: ignore[union-attr]
        loaded = match_repo.get(mid)  # type: ignore[union-attr]
        assert loaded is not None
        assert len(loaded.history) == 1


class TestMatchListRecent:
    def test_empty(self, match_repo: object) -> None:
        assert match_repo.list_recent() == []  # type: ignore[union-attr]

    def test_limit_respected(self, match_repo: object) -> None:
        for _ in range(5):
            match_repo.save(_3p_state())  # type: ignore[union-attr]
        assert len(match_repo.list_recent(limit=3)) == 3  # type: ignore[union-attr]

    def test_most_recent_first(self, match_repo: object) -> None:
        ids = [uuid4() for _ in range(3)]
        for mid in ids:
            match_repo.save(_3p_state(mid))  # type: ignore[union-attr]
        result = match_repo.list_recent()  # type: ignore[union-attr]
        assert result[0].match_id == ids[-1]
