from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from carrom_caster.domain.event import GameEvent
from carrom_caster.domain.player import Player, Team


class MatchMode(Enum):
    THREE_PLAYER_FFA = "3P_FFA"
    FOUR_PLAYER_PARTNERS = "4P_PARTNERS"


class QueenState(Enum):
    ON_BOARD = "on_board"
    POCKETED_UNCOVERED = "pocketed_uncovered"  # waiting for cover this turn
    COVERED = "covered"                         # covered; +3 awarded


@dataclass(frozen=True)
class PlayerScore:
    player_id: UUID
    points: int


@dataclass(frozen=True)
class MatchState:
    """
    Complete, immutable snapshot of a match at a point in time.

    players_in_order : clockwise from left, as tagged at match start.
    teams            : empty for 3P; 2 teams for 4P (teams[0]=white, teams[1]=black).
    boards_won       : (team0_boards, team1_boards); always (0,0) in 3P.
    history          : all events applied so far, in order.
    """

    match_id: UUID
    mode: MatchMode
    players_in_order: tuple[Player, ...]
    teams: tuple[Team, ...]
    current_turn_index: int
    player_scores: tuple[PlayerScore, ...]
    queen_state: QueenState
    queen_pocketed_by_index: int | None  # index into players_in_order
    white_coins_on_board: int
    black_coins_on_board: int
    history: tuple[GameEvent, ...]
    board_number: int
    boards_won: tuple[int, int]
    is_active: bool

    @property
    def current_player(self) -> Player:
        return self.players_in_order[self.current_turn_index]

    def score_for(self, player_id: UUID) -> int:
        for ps in self.player_scores:
            if ps.player_id == player_id:
                return ps.points
        return 0
