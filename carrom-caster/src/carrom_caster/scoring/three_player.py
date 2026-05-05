"""
Three-player free-for-all scoring rules (Indian standard).

Rules assumed:
- 9 white + 9 black coins on board. Queen is separate.
- Any pocketed coin (white or black): +1 to current player.
- Queen pocketed: must be covered in the SAME turn by pocketing any coin.
  If covered: +3 to current player. If not covered: queen returns to center.
- Striker pocketed: -1 to current player. Turn ends.
- Game ends when all white + black coins pocketed AND queen is covered.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchMode, MatchState, PlayerScore, QueenState
from carrom_caster.domain.player import Player, Team
from carrom_caster.scoring._helpers import add_points, with_event

INITIAL_WHITE = 9
INITIAL_BLACK = 9
QUEEN_POINTS = 3
FOUL_POINTS = -1


class ThreePlayerRules:
    def initial_state(
        self,
        match_id: UUID,
        players: list[Player],
        teams: list[Team],
        board_number: int = 1,
    ) -> MatchState:
        if len(players) != 3:
            raise ValueError(f"Three-player mode needs 3 players, got {len(players)}")
        return MatchState(
            match_id=match_id,
            mode=MatchMode.THREE_PLAYER_FFA,
            players_in_order=tuple(players),
            teams=(),
            current_turn_index=0,
            player_scores=tuple(PlayerScore(p.id, 0) for p in players),
            queen_state=QueenState.ON_BOARD,
            queen_pocketed_by_index=None,
            white_coins_on_board=INITIAL_WHITE,
            black_coins_on_board=INITIAL_BLACK,
            history=(),
            board_number=board_number,
            boards_won=(0, 0),
            is_active=True,
        )

    def apply(self, state: MatchState, event: GameEvent) -> MatchState:
        state = with_event(state, event)
        match event.type:
            case EventType.COIN_POCKETED:
                return _coin_pocketed(state, event)
            case EventType.QUEEN_POCKETED:
                return _queen_pocketed(state)
            case EventType.STRIKER_POCKETED:
                return _striker_pocketed(state)
            case EventType.TURN_ENDED:
                return _turn_ended(state)
            case EventType.MATCH_ENDED:
                return replace(state, is_active=False)
            case _:
                return state


# ── per-event helpers (module-private) ────────────────────────────────────────

def _coin_pocketed(state: MatchState, event: GameEvent) -> MatchState:
    color: str = event.payload.get("color", "")
    player_id = state.current_player.id

    # Update coin counts.
    if color == "white":
        state = replace(state, white_coins_on_board=max(0, state.white_coins_on_board - 1))
    elif color == "black":
        state = replace(state, black_coins_on_board=max(0, state.black_coins_on_board - 1))

    # Any coin pocketed after queen in the same turn = cover.
    if state.queen_state == QueenState.POCKETED_UNCOVERED:
        scores = add_points(state.player_scores, player_id, QUEEN_POINTS + 1)
        return replace(
            state,
            queen_state=QueenState.COVERED,
            queen_pocketed_by_index=None,
            player_scores=scores,
        )

    return replace(state, player_scores=add_points(state.player_scores, player_id, 1))


def _queen_pocketed(state: MatchState) -> MatchState:
    return replace(
        state,
        queen_state=QueenState.POCKETED_UNCOVERED,
        queen_pocketed_by_index=state.current_turn_index,
    )


def _striker_pocketed(state: MatchState) -> MatchState:
    scores = add_points(state.player_scores, state.current_player.id, FOUL_POINTS)
    return replace(state, player_scores=scores)


def _turn_ended(state: MatchState) -> MatchState:
    # Queen uncovered at turn end → returns to board.
    if state.queen_state == QueenState.POCKETED_UNCOVERED:
        state = replace(state, queen_state=QueenState.ON_BOARD, queen_pocketed_by_index=None)

    next_index = (state.current_turn_index + 1) % len(state.players_in_order)
    state = replace(state, current_turn_index=next_index)

    # Game ends when all coins cleared and queen covered.
    if (
        state.white_coins_on_board == 0
        and state.black_coins_on_board == 0
        and state.queen_state == QueenState.COVERED
    ):
        state = replace(state, is_active=False)

    return state
