from __future__ import annotations

from typing import Protocol
from uuid import UUID

from carrom_caster.domain.event import GameEvent
from carrom_caster.domain.match import MatchState
from carrom_caster.domain.player import Player, Team


class ScoringRules(Protocol):
    """Strategy interface for carrom scoring rule variants."""

    def initial_state(
        self,
        match_id: UUID,
        players: list[Player],
        teams: list[Team],
        board_number: int = 1,
    ) -> MatchState: ...

    def apply(self, state: MatchState, event: GameEvent) -> MatchState: ...
