from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchMode, MatchState, PlayerScore, QueenState
from carrom_caster.domain.player import Player, PlayerGroup, Team
from carrom_caster.persistence.schema import (
    match_events,
    match_players,
    match_scores,
    match_teams,
    matches,
    metadata,
    player_group_members,
    player_groups,
)


# ── Protocols ──────────────────────────────────────────────────────────────────

class PlayerGroupRepository(Protocol):
    def save(self, group: PlayerGroup) -> None: ...
    def get(self, group_id: UUID) -> PlayerGroup | None: ...
    def list_all(self) -> list[PlayerGroup]: ...
    def delete(self, group_id: UUID) -> None: ...
    def touch(self, group_id: UUID, when: datetime) -> None: ...


class MatchRepository(Protocol):
    def save(self, state: MatchState) -> None: ...
    def get(self, match_id: UUID) -> MatchState | None: ...
    def list_recent(self, limit: int = 10) -> list[MatchState]: ...


# ── Fakes ──────────────────────────────────────────────────────────────────────

class FakePlayerGroupRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, PlayerGroup] = {}

    def save(self, group: PlayerGroup) -> None:
        self._store[group.id] = group

    def get(self, group_id: UUID) -> PlayerGroup | None:
        return self._store.get(group_id)

    def list_all(self) -> list[PlayerGroup]:
        return sorted(self._store.values(), key=lambda g: g.last_used, reverse=True)

    def delete(self, group_id: UUID) -> None:
        self._store.pop(group_id, None)

    def touch(self, group_id: UUID, when: datetime) -> None:
        if group_id in self._store:
            self._store[group_id] = replace(self._store[group_id], last_used=when)


class FakeMatchRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, MatchState] = {}
        self._order: list[UUID] = []

    def save(self, state: MatchState) -> None:
        if state.match_id not in self._store:
            self._order.append(state.match_id)
        self._store[state.match_id] = state

    def get(self, match_id: UUID) -> MatchState | None:
        return self._store.get(match_id)

    def list_recent(self, limit: int = 10) -> list[MatchState]:
        return [self._store[mid] for mid in reversed(self._order)][:limit]


# ── SQLite implementations ─────────────────────────────────────────────────────

class SqlitePlayerGroupRepository:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine
        metadata.create_all(engine)

    def save(self, group: PlayerGroup) -> None:
        gid = str(group.id)
        stmt = sqlite_insert(player_groups).values(
            id=gid, name=group.name, last_used=group.last_used.isoformat()
        )
        with self._engine.begin() as conn:
            conn.execute(
                stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={"name": stmt.excluded.name, "last_used": stmt.excluded.last_used},
                )
            )
            conn.execute(
                player_group_members.delete().where(player_group_members.c.group_id == gid)
            )
            for i, m in enumerate(group.members):
                conn.execute(
                    player_group_members.insert().values(
                        group_id=gid, position=i, player_id=str(m.id), player_name=m.name
                    )
                )

    def get(self, group_id: UUID) -> PlayerGroup | None:
        gid = str(group_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                player_groups.select().where(player_groups.c.id == gid)
            ).fetchone()
            if row is None:
                return None
            return PlayerGroup(
                id=UUID(row.id),
                name=row.name,
                members=tuple(_load_members(conn, gid)),
                last_used=datetime.fromisoformat(row.last_used),
            )

    def list_all(self) -> list[PlayerGroup]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                player_groups.select().order_by(player_groups.c.last_used.desc())
            ).fetchall()
            return [
                PlayerGroup(
                    id=UUID(r.id),
                    name=r.name,
                    members=tuple(_load_members(conn, r.id)),
                    last_used=datetime.fromisoformat(r.last_used),
                )
                for r in rows
            ]

    def delete(self, group_id: UUID) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                player_groups.delete().where(player_groups.c.id == str(group_id))
            )

    def touch(self, group_id: UUID, when: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                player_groups.update()
                .where(player_groups.c.id == str(group_id))
                .values(last_used=when.isoformat())
            )


class SqliteMatchRepository:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine
        metadata.create_all(engine)

    def save(self, state: MatchState) -> None:
        mid = str(state.match_id)
        stmt = sqlite_insert(matches).values(
            id=mid,
            mode=state.mode.value,
            board_number=state.board_number,
            boards_won_0=state.boards_won[0],
            boards_won_1=state.boards_won[1],
            queen_state=state.queen_state.value,
            queen_pocketed_by_index=state.queen_pocketed_by_index,
            white_coins_on_board=state.white_coins_on_board,
            black_coins_on_board=state.black_coins_on_board,
            current_turn_index=state.current_turn_index,
            is_active=int(state.is_active),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._engine.begin() as conn:
            for tbl in (match_events, match_scores, match_players, match_teams):
                conn.execute(tbl.delete().where(tbl.c.match_id == mid))
            conn.execute(
                stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "mode": stmt.excluded.mode,
                        "board_number": stmt.excluded.board_number,
                        "boards_won_0": stmt.excluded.boards_won_0,
                        "boards_won_1": stmt.excluded.boards_won_1,
                        "queen_state": stmt.excluded.queen_state,
                        "queen_pocketed_by_index": stmt.excluded.queen_pocketed_by_index,
                        "white_coins_on_board": stmt.excluded.white_coins_on_board,
                        "black_coins_on_board": stmt.excluded.black_coins_on_board,
                        "current_turn_index": stmt.excluded.current_turn_index,
                        "is_active": stmt.excluded.is_active,
                        # created_at preserved from first insert
                    },
                )
            )
            for i, p in enumerate(state.players_in_order):
                conn.execute(
                    match_players.insert().values(
                        match_id=mid,
                        position=i,
                        player_id=str(p.id),
                        player_name=p.name,
                        team_index=_player_team_index(p, state.teams),
                    )
                )
            for i, t in enumerate(state.teams):
                conn.execute(
                    match_teams.insert().values(
                        match_id=mid, team_index=i, team_id=t.id, team_name=t.name
                    )
                )
            for ps in state.player_scores:
                conn.execute(
                    match_scores.insert().values(
                        match_id=mid, player_id=str(ps.player_id), points=ps.points
                    )
                )
            for seq, ev in enumerate(state.history):
                conn.execute(
                    match_events.insert().values(
                        match_id=mid,
                        sequence=seq,
                        event_type=ev.type.value,
                        timestamp=ev.timestamp.isoformat(),
                        frame_index=ev.frame_index,
                        payload=json.dumps(ev.payload),
                    )
                )

    def get(self, match_id: UUID) -> MatchState | None:
        mid = str(match_id)
        with self._engine.connect() as conn:
            row = conn.execute(matches.select().where(matches.c.id == mid)).fetchone()
            if row is None:
                return None
            return _build_match_state(conn, row)

    def list_recent(self, limit: int = 10) -> list[MatchState]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                matches.select().order_by(matches.c.created_at.desc()).limit(limit)
            ).fetchall()
            return [_build_match_state(conn, r) for r in rows]


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_members(conn: sa.Connection, group_id: str) -> list[Player]:
    rows = conn.execute(
        player_group_members.select()
        .where(player_group_members.c.group_id == group_id)
        .order_by(player_group_members.c.position)
    ).fetchall()
    return [Player(id=UUID(r.player_id), name=r.player_name) for r in rows]


def _player_team_index(player: Player, teams: tuple[Team, ...]) -> int | None:
    for i, team in enumerate(teams):
        if player in team.players:
            return i
    return None


def _build_match_state(conn: sa.Connection, row: Any) -> MatchState:
    mid = row.id
    player_rows = conn.execute(
        match_players.select()
        .where(match_players.c.match_id == mid)
        .order_by(match_players.c.position)
    ).fetchall()
    players = tuple(Player(id=UUID(r.player_id), name=r.player_name) for r in player_rows)

    team_rows = conn.execute(
        match_teams.select()
        .where(match_teams.c.match_id == mid)
        .order_by(match_teams.c.team_index)
    ).fetchall()
    teams = tuple(
        Team(
            id=tr.team_id,
            name=tr.team_name,
            players=tuple(
                Player(id=UUID(pr.player_id), name=pr.player_name)
                for pr in player_rows
                if pr.team_index == tr.team_index
            ),
        )
        for tr in team_rows
    )

    score_rows = conn.execute(
        match_scores.select().where(match_scores.c.match_id == mid)
    ).fetchall()
    scores = tuple(PlayerScore(player_id=UUID(r.player_id), points=r.points) for r in score_rows)

    event_rows = conn.execute(
        match_events.select()
        .where(match_events.c.match_id == mid)
        .order_by(match_events.c.sequence)
    ).fetchall()
    history = tuple(
        GameEvent(
            type=EventType(r.event_type),
            timestamp=datetime.fromisoformat(r.timestamp),
            frame_index=r.frame_index,
            payload=json.loads(r.payload),
        )
        for r in event_rows
    )

    return MatchState(
        match_id=UUID(mid),
        mode=MatchMode(row.mode),
        players_in_order=players,
        teams=teams,
        current_turn_index=row.current_turn_index,
        player_scores=scores,
        queen_state=QueenState(row.queen_state),
        queen_pocketed_by_index=row.queen_pocketed_by_index,
        white_coins_on_board=row.white_coins_on_board,
        black_coins_on_board=row.black_coins_on_board,
        history=history,
        board_number=row.board_number,
        boards_won=(row.boards_won_0, row.boards_won_1),
        is_active=bool(row.is_active),
    )
