from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from carrom_caster.domain.event import GameEvent
from carrom_caster.domain.match import MatchState, PlayerScore


def with_event(state: MatchState, event: GameEvent) -> MatchState:
    """Return state with event appended to history."""
    return replace(state, history=state.history + (event,))


def add_points(
    scores: tuple[PlayerScore, ...], player_id: UUID, delta: int
) -> tuple[PlayerScore, ...]:
    """Return scores tuple with delta added to the given player."""
    return tuple(
        replace(s, points=s.points + delta) if s.player_id == player_id else s
        for s in scores
    )
