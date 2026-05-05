from __future__ import annotations

from uuid import UUID

from carrom_caster.domain.event import GameEvent
from carrom_caster.domain.match import MatchState
from carrom_caster.domain.player import Player, Team
from carrom_caster.scoring.rules import ScoringRules


class Scorer:
    """Thin orchestrator — delegates entirely to a ScoringRules strategy."""

    def __init__(self, rules: ScoringRules) -> None:
        self._rules = rules

    def initial_state(
        self,
        match_id: UUID,
        players: list[Player],
        teams: list[Team] | None = None,
        board_number: int = 1,
    ) -> MatchState:
        return self._rules.initial_state(
            match_id=match_id,
            players=players,
            teams=teams or [],
            board_number=board_number,
        )

    def apply(self, state: MatchState, event: GameEvent) -> MatchState:
        return self._rules.apply(state, event)

    def apply_all(self, state: MatchState, events: list[GameEvent]) -> MatchState:
        for event in events:
            state = self._rules.apply(state, event)
            if not state.is_active:
                break
        return state
