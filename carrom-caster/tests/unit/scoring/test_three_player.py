"""Unit tests for ThreePlayerRules — covers every rule branch + edge cases."""
from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from carrom_caster.domain.match import MatchMode, QueenState
from carrom_caster.scoring.three_player import INITIAL_BLACK, INITIAL_WHITE, ThreePlayerRules
from tests.conftest import (
    PLAYERS_3P,
    coin_pocketed,
    match_ended,
    queen_pocketed,
    striker_pocketed,
    turn_ended,
)


@pytest.fixture
def rules() -> ThreePlayerRules:
    return ThreePlayerRules()


@pytest.fixture
def state(rules, match_id):
    return rules.initial_state(match_id, PLAYERS_3P, [])


# ── initial state ─────────────────────────────────────────────────────────────

class TestInitialState:
    def test_mode(self, state):
        assert state.mode == MatchMode.THREE_PLAYER_FFA

    def test_three_players(self, state):
        assert len(state.players_in_order) == 3

    def test_all_coins_on_board(self, state):
        assert state.white_coins_on_board == INITIAL_WHITE
        assert state.black_coins_on_board == INITIAL_BLACK

    def test_queen_on_board(self, state):
        assert state.queen_state == QueenState.ON_BOARD

    def test_scores_zero(self, state):
        for ps in state.player_scores:
            assert ps.points == 0

    def test_first_turn(self, state):
        assert state.current_turn_index == 0

    def test_active(self, state):
        assert state.is_active is True

    def test_wrong_player_count(self, rules, match_id):
        with pytest.raises(ValueError):
            rules.initial_state(match_id, PLAYERS_3P[:2], [])


# ── coin pocketing ────────────────────────────────────────────────────────────

class TestCoinPocketed:
    def test_white_gives_one_point(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))
        assert s.score_for(PLAYERS_3P[0].id) == 1

    def test_black_gives_one_point(self, rules, state):
        s = rules.apply(state, coin_pocketed("black"))
        assert s.score_for(PLAYERS_3P[0].id) == 1

    def test_white_decrements_count(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))
        assert s.white_coins_on_board == INITIAL_WHITE - 1

    def test_black_decrements_count(self, rules, state):
        s = rules.apply(state, coin_pocketed("black"))
        assert s.black_coins_on_board == INITIAL_BLACK - 1

    def test_only_current_player_scores(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))
        assert s.score_for(PLAYERS_3P[1].id) == 0
        assert s.score_for(PLAYERS_3P[2].id) == 0

    def test_unknown_color_no_decrement(self, rules, state):
        s = rules.apply(state, coin_pocketed("unknown"))
        assert s.white_coins_on_board == INITIAL_WHITE
        assert s.black_coins_on_board == INITIAL_BLACK


# ── queen mechanics ───────────────────────────────────────────────────────────

class TestQueenMechanics:
    def test_queen_pocketed_sets_uncovered(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        assert s.queen_state == QueenState.POCKETED_UNCOVERED

    def test_queen_pocketed_no_points_yet(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        assert s.score_for(PLAYERS_3P[0].id) == 0

    def test_queen_covered_awards_bonus(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, coin_pocketed("white"))
        # +3 (queen) + +1 (cover coin) = 4
        assert s.score_for(PLAYERS_3P[0].id) == 4
        assert s.queen_state == QueenState.COVERED

    def test_queen_covered_with_black_coin(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, coin_pocketed("black"))
        assert s.queen_state == QueenState.COVERED
        assert s.score_for(PLAYERS_3P[0].id) == 4

    def test_queen_returns_if_uncovered_at_turn_end(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, turn_ended())
        assert s.queen_state == QueenState.ON_BOARD

    def test_queen_returns_clears_pocketed_by(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, turn_ended())
        assert s.queen_pocketed_by_index is None

    def test_queen_returns_no_points_awarded(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, turn_ended())
        assert s.score_for(PLAYERS_3P[0].id) == 0

    def test_coin_before_queen_normal_points(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))
        s = rules.apply(s, queen_pocketed())
        s = rules.apply(s, coin_pocketed("white"))
        # first coin: +1, cover coin: +4 → total 5
        assert s.score_for(PLAYERS_3P[0].id) == 5


# ── foul (striker pocketed) ───────────────────────────────────────────────────

class TestStrikerPocketed:
    def test_minus_one(self, rules, state):
        s = rules.apply(state, striker_pocketed())
        assert s.score_for(PLAYERS_3P[0].id) == -1

    def test_only_current_player_penalised(self, rules, state):
        s = rules.apply(state, striker_pocketed())
        assert s.score_for(PLAYERS_3P[1].id) == 0

    def test_queen_uncovered_returns_after_turn_end(self, rules, state):
        s = rules.apply(state, queen_pocketed())
        s = rules.apply(s, striker_pocketed())
        s = rules.apply(s, turn_ended())
        assert s.queen_state == QueenState.ON_BOARD


# ── turn progression ──────────────────────────────────────────────────────────

class TestTurnProgression:
    def test_turn_advances(self, rules, state):
        s = rules.apply(state, turn_ended())
        assert s.current_turn_index == 1

    def test_turn_wraps(self, rules, state):
        s = state
        for _ in range(3):
            s = rules.apply(s, turn_ended())
        assert s.current_turn_index == 0

    def test_history_grows(self, rules, state):
        s = rules.apply(state, coin_pocketed("white"))
        s = rules.apply(s, turn_ended())
        assert len(s.history) == 2


# ── game end ──────────────────────────────────────────────────────────────────

class TestGameEnd:
    def _clear_board(self, rules, state):
        """Pocket all 9 white + 9 black coins, then queen + cover, for player 0."""
        s = state
        for _ in range(INITIAL_WHITE):
            s = rules.apply(s, coin_pocketed("white"))
        for _ in range(INITIAL_BLACK):
            s = rules.apply(s, coin_pocketed("black"))
        s = rules.apply(s, queen_pocketed())
        s = rules.apply(s, coin_pocketed("white"))  # cover — but white count is 0...
        return s

    def test_game_not_active_when_cleared(self, rules, state):
        s = self._clear_board(rules, state)
        s = rules.apply(s, turn_ended())
        assert not s.is_active

    def test_game_stays_active_queen_not_covered(self, rules, state):
        s = state
        for _ in range(INITIAL_WHITE):
            s = rules.apply(s, coin_pocketed("white"))
        for _ in range(INITIAL_BLACK):
            s = rules.apply(s, coin_pocketed("black"))
        s = rules.apply(s, turn_ended())
        # Queen still on board → game continues
        assert s.is_active

    def test_match_ended_event_deactivates(self, rules, state):
        s = rules.apply(state, match_ended())
        assert not s.is_active


# ── Hypothesis property tests ─────────────────────────────────────────────────

_SAFE_EVENTS = st.sampled_from([
    lambda: coin_pocketed("white"),
    lambda: coin_pocketed("black"),
    lambda: queen_pocketed(),
    lambda: striker_pocketed(),
    lambda: turn_ended(),
])


@given(event_factories=st.lists(_SAFE_EVENTS, max_size=50))
@settings(max_examples=200)
def test_turn_index_always_valid(event_factories):
    rules = ThreePlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_3P, [])
    for factory in event_factories:
        state = rules.apply(state, factory())
        assert 0 <= state.current_turn_index < len(state.players_in_order)


@given(event_factories=st.lists(_SAFE_EVENTS, max_size=50))
@settings(max_examples=200)
def test_coin_counts_non_negative(event_factories):
    rules = ThreePlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_3P, [])
    for factory in event_factories:
        state = rules.apply(state, factory())
        assert state.white_coins_on_board >= 0
        assert state.black_coins_on_board >= 0


@given(event_factories=st.lists(_SAFE_EVENTS, max_size=50))
@settings(max_examples=200)
def test_queen_state_valid_values(event_factories):
    rules = ThreePlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_3P, [])
    for factory in event_factories:
        state = rules.apply(state, factory())
        assert state.queen_state in list(QueenState)


@given(event_factories=st.lists(_SAFE_EVENTS, max_size=50))
@settings(max_examples=200)
def test_total_score_bounded(event_factories):
    """Total points across all players stay within theoretical max."""
    rules = ThreePlayerRules()
    state = rules.initial_state(uuid4(), PLAYERS_3P, [])
    max_possible = INITIAL_WHITE + INITIAL_BLACK + 3  # all coins + queen
    for factory in event_factories:
        state = rules.apply(state, factory())
        total = sum(ps.points for ps in state.player_scores)
        assert total <= max_possible
