"""Unit tests for FourPlayerRules — partner mode scoring."""
from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from carrom_caster.domain.match import MatchMode, QueenState
from carrom_caster.scoring.four_player import INITIAL_BLACK, INITIAL_WHITE, FourPlayerRules
from tests.conftest import (
    PLAYERS_4P,
    TEAMS_4P,
    coin_pocketed,
    match_ended,
    queen_pocketed,
    striker_pocketed,
    turn_ended,
)


@pytest.fixture
def rules() -> FourPlayerRules:
    return FourPlayerRules(boards_to_win=2)


@pytest.fixture
def state(rules, match_id):
    return rules.initial_state(match_id, PLAYERS_4P, TEAMS_4P)


# ── initial state ─────────────────────────────────────────────────────────────

class TestInitialState:
    def test_mode(self, state):
        assert state.mode == MatchMode.FOUR_PLAYER_PARTNERS

    def test_four_players(self, state):
        assert len(state.players_in_order) == 4

    def test_two_teams(self, state):
        assert len(state.teams) == 2

    def test_wrong_player_count(self, rules, match_id):
        with pytest.raises(ValueError):
            rules.initial_state(match_id, PLAYERS_4P[:3], TEAMS_4P)

    def test_wrong_team_count(self, rules, match_id):
        with pytest.raises(ValueError):
            rules.initial_state(match_id, PLAYERS_4P, [TEAMS_4P[0]])


# ── correct-color pocketing ───────────────────────────────────────────────────

class TestCorrectColor:
    def test_team0_pockets_white_scores(self, rules, state):
        # Player 0 → Team 0 → white
        s = rules.apply(state, coin_pocketed("white"))
        assert s.score_for(PLAYERS_4P[0].id) == 1

    def test_team1_pockets_black_scores(self, rules, state):
        # Advance to player 1 (Team 1)
        s = rules.apply(state, turn_ended())
        s = rules.apply(s, coin_pocketed("black"))
        assert s.score_for(PLAYERS_4P[1].id) == 1

    def test_white_count_decrements(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))
        assert s.white_coins_on_board == INITIAL_WHITE - 1


# ── wrong-color foul ──────────────────────────────────────────────────────────

class TestWrongColorFoul:
    def test_no_points_for_foul(self, rules, state):
        s = rules.apply(state, coin_pocketed("black"))  # player 0 pockets black = foul
        assert s.score_for(PLAYERS_4P[0].id) == 0

    def test_coin_returns_to_board(self, rules, state):
        # Black pocketed by team0 (foul): black coin returns
        s = rules.apply(state, coin_pocketed("black"))
        assert s.black_coins_on_board == INITIAL_BLACK  # returned

    def test_own_coin_also_returns(self, rules, state):
        # First pocket a white legitimately, then foul
        s = rules.apply(state, coin_pocketed("white"))   # white: 8
        s = rules.apply(s, coin_pocketed("black"))        # foul: white returns → 9
        assert s.white_coins_on_board == INITIAL_WHITE
        assert s.black_coins_on_board == INITIAL_BLACK    # black returned

    def test_no_own_coin_to_return(self, rules, state):
        # Team0 has pocketed 0 whites yet, then fouls — nothing to return
        s = rules.apply(state, coin_pocketed("black"))
        assert s.white_coins_on_board == INITIAL_WHITE  # no change
        assert s.black_coins_on_board == INITIAL_BLACK  # black returned


# ── queen mechanics (4P) ──────────────────────────────────────────────────────

class TestQueenMechanics4P:
    def test_queen_sets_uncovered(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        assert s.queen_state == QueenState.POCKETED_UNCOVERED

    def test_cover_with_team_color_awards_points(self, rules, state):
        # Player 0 (Team 0, white) pockets queen then covers with white
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, coin_pocketed("white"))
        assert s.queen_state == QueenState.COVERED
        assert s.score_for(PLAYERS_4P[0].id) == 3 + 1  # queen + cover coin

    def test_cover_with_wrong_color_does_not_cover(self, rules, state):
        # Player 0 (Team 0, white) pockets queen; pockets black = foul, no cover
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, coin_pocketed("black"))
        assert s.queen_state == QueenState.POCKETED_UNCOVERED  # still uncovered

    def test_queen_returns_if_not_covered_at_turn_end(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, turn_ended())
        assert s.queen_state == QueenState.ON_BOARD


# ── striker foul (4P) ─────────────────────────────────────────────────────────

class TestStrikerFoul4P:
    def test_own_coin_returns_on_striker(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))  # pocket 1 white
        s = rules.apply(s, striker_pocketed())           # foul → white returns
        assert s.white_coins_on_board == INITIAL_WHITE

    def test_no_coin_to_return(self, rules, state):
        s = rules.apply(state, striker_pocketed())
        assert s.white_coins_on_board == INITIAL_WHITE  # nothing to return


# ── board end + match end ─────────────────────────────────────────────────────

class TestBoardAndMatchEnd:
    def _clear_whites(self, rules, state):
        s = state
        for _ in range(INITIAL_WHITE):
            s = rules.apply(s, coin_pocketed("white"))
        return s

    def test_board_ends_when_team_clears(self, rules, state):
        s = self._clear_whites(rules, state)
        s = rules.apply(s, turn_ended())
        assert s.boards_won[0] == 1

    def test_match_not_over_after_one_board(self, rules, state):
        s = self._clear_whites(rules, state)
        s = rules.apply(s, turn_ended())
        assert s.is_active

    def test_match_ends_when_boards_to_win_reached(self, match_id):
        rules = FourPlayerRules(boards_to_win=1)
        state = rules.initial_state(match_id, PLAYERS_4P, TEAMS_4P)
        s = self._clear_whites(rules, state)
        s = rules.apply(s, turn_ended())
        assert not s.is_active

    def test_match_ended_event(self, rules, state):
        s = rules.apply(state, match_ended())
        assert not s.is_active


# ── Hypothesis properties ─────────────────────────────────────────────────────

_SAFE_4P = st.sampled_from([
    lambda: coin_pocketed("white"),
    lambda: coin_pocketed("black"),
    lambda: queen_pocketed(),
    lambda: striker_pocketed(),
    lambda: turn_ended(),
])


@given(event_factories=st.lists(_SAFE_4P, max_size=60))
@settings(max_examples=200)
def test_turn_index_valid_4p(event_factories):
    rules = FourPlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_4P, TEAMS_4P)
    for factory in event_factories:
        state = rules.apply(state, factory())
        assert 0 <= state.current_turn_index < 4


@given(event_factories=st.lists(_SAFE_4P, max_size=60))
@settings(max_examples=200)
def test_coin_counts_non_negative_4p(event_factories):
    rules = FourPlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_4P, TEAMS_4P)
    for factory in event_factories:
        state = rules.apply(state, factory())
        assert state.white_coins_on_board >= 0
        assert state.black_coins_on_board >= 0


@given(event_factories=st.lists(_SAFE_4P, max_size=60))
@settings(max_examples=200)
def test_boards_won_non_negative(event_factories):
    rules = FourPlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_4P, TEAMS_4P)
    for factory in event_factories:
        state = rules.apply(state, factory())
        assert state.boards_won[0] >= 0
        assert state.boards_won[1] >= 0
