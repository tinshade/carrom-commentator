"""
Four-player 2v2 partner scoring rules (Indian standard).

Teams:
  teams[0] — plays WHITE coins (players at indices 0, 2)
  teams[1] — plays BLACK coins (players at indices 1, 3)
Turn order: 0 → 1 → 2 → 3 → 0 … (clockwise, alternating teams)

Rules assumed:
- Pocketing your team's color: +1 to current player.
- Pocketing opponent's color (foul): that coin returns to board center,
  AND one of your team's already-pocketed coins returns to center.
  No points scored.
- Queen pocketed: must be covered in the SAME turn by pocketing your team's color.
  If covered: +3 to queen-pocketing player, +1 to covering player (may be same player).
  If not covered: queen returns to center.
- Striker pocketed: one of your team's pocketed coins returns to board.
- A board ends when a team pockets all their color coins (at TURN_ENDED).
- Match ends when one team wins `boards_to_win` boards (default best-of-3 → 2).
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

_TEAM_COLOR = {0: "white", 1: "black"}


class FourPlayerRules:
    def __init__(self, boards_to_win: int = 2) -> None:
        self.boards_to_win = boards_to_win

    def initial_state(
        self,
        match_id: UUID,
        players: list[Player],
        teams: list[Team],
        board_number: int = 1,
    ) -> MatchState:
        if len(players) != 4:
            raise ValueError(f"Four-player mode needs 4 players, got {len(players)}")
        if len(teams) != 2:
            raise ValueError(f"Four-player mode needs 2 teams, got {len(teams)}")
        return MatchState(
            match_id=match_id,
            mode=MatchMode.FOUR_PLAYER_PARTNERS,
            players_in_order=tuple(players),
            teams=tuple(teams),
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
                return _turn_ended(state, self.boards_to_win)
            case EventType.MATCH_ENDED:
                return replace(state, is_active=False)
            case _:
                return state


# ── per-event helpers ─────────────────────────────────────────────────────────

def _team_index(turn_index: int) -> int:
    return turn_index % 2


def _return_own_coin(state: MatchState) -> MatchState:
    """Return one pocketed coin of the current team back to the board."""
    team_idx = _team_index(state.current_turn_index)
    if team_idx == 0 and state.white_coins_on_board < INITIAL_WHITE:
        return replace(state, white_coins_on_board=state.white_coins_on_board + 1)
    if team_idx == 1 and state.black_coins_on_board < INITIAL_BLACK:
        return replace(state, black_coins_on_board=state.black_coins_on_board + 1)
    return state  # nothing to return


def _coin_pocketed(state: MatchState, event: GameEvent) -> MatchState:
    color: str = event.payload.get("color", "")
    team_idx = _team_index(state.current_turn_index)
    own_color = _TEAM_COLOR[team_idx]
    current_player = state.current_player

    # Decrement the pocketed color's count.
    if color == "white":
        state = replace(state, white_coins_on_board=max(0, state.white_coins_on_board - 1))
    elif color == "black":
        state = replace(state, black_coins_on_board=max(0, state.black_coins_on_board - 1))

    # Foul: wrong color — wrongly pocketed coin returns AND one of own team's returns.
    if color in ("white", "black") and color != own_color:
        # Undo the decrement: wrongly pocketed coin returns to board.
        if color == "white":
            state = replace(state, white_coins_on_board=state.white_coins_on_board + 1)
        else:
            state = replace(state, black_coins_on_board=state.black_coins_on_board + 1)
        state = _return_own_coin(state)  # penalty: one of yours also returns
        return state  # no points

    # Check queen cover.
    if state.queen_state == QueenState.POCKETED_UNCOVERED:
        queen_pocketer_idx = state.queen_pocketed_by_index or 0
        queen_team_color = _TEAM_COLOR[_team_index(queen_pocketer_idx)]
        if color == queen_team_color:
            queen_pocketer = state.players_in_order[queen_pocketer_idx]
            scores = add_points(state.player_scores, queen_pocketer.id, QUEEN_POINTS)
            scores = add_points(scores, current_player.id, 1)
            return replace(
                state,
                queen_state=QueenState.COVERED,
                queen_pocketed_by_index=None,
                player_scores=scores,
            )

    # Normal pocket.
    return replace(state, player_scores=add_points(state.player_scores, current_player.id, 1))


def _queen_pocketed(state: MatchState) -> MatchState:
    return replace(
        state,
        queen_state=QueenState.POCKETED_UNCOVERED,
        queen_pocketed_by_index=state.current_turn_index,
    )


def _striker_pocketed(state: MatchState) -> MatchState:
    return _return_own_coin(state)


def _turn_ended(state: MatchState, boards_to_win: int) -> MatchState:
    # Queen uncovered at turn end → returns to board.
    if state.queen_state == QueenState.POCKETED_UNCOVERED:
        state = replace(state, queen_state=QueenState.ON_BOARD, queen_pocketed_by_index=None)

    next_index = (state.current_turn_index + 1) % len(state.players_in_order)
    state = replace(state, current_turn_index=next_index)

    # Board ends when a team clears all their color coins.
    team0_cleared = state.white_coins_on_board == 0
    team1_cleared = state.black_coins_on_board == 0

    if team0_cleared or team1_cleared:
        winning_team = 0 if team0_cleared else 1
        if winning_team == 0:
            new_boards = (state.boards_won[0] + 1, state.boards_won[1])
        else:
            new_boards = (state.boards_won[0], state.boards_won[1] + 1)
        state = replace(state, boards_won=new_boards)

        if max(state.boards_won) >= boards_to_win:
            state = replace(state, is_active=False)

    return state
