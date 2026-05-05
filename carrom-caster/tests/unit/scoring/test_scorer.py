"""Unit tests for Scorer — thin orchestration layer."""
from __future__ import annotations

import pytest

from carrom_caster.domain.match import MatchMode
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules
from tests.conftest import PLAYERS_3P, coin_pocketed, turn_ended


@pytest.fixture
def scorer() -> Scorer:
    return Scorer(ThreePlayerRules())


@pytest.fixture
def state(scorer, match_id):
    return scorer.initial_state(match_id, PLAYERS_3P)


class TestScorer:
    def test_initial_state_delegates(self, scorer, match_id):
        s = scorer.initial_state(match_id, PLAYERS_3P)
        assert s.mode == MatchMode.THREE_PLAYER_FFA
        assert s.is_active

    def test_apply_delegates(self, scorer, state):
        s = scorer.apply(state, coin_pocketed("white"))
        assert s.score_for(PLAYERS_3P[0].id) == 1

    def test_apply_all_processes_sequence(self, scorer, state):
        events = [coin_pocketed("white"), coin_pocketed("black"), turn_ended()]
        s = scorer.apply_all(state, events)
        assert s.score_for(PLAYERS_3P[0].id) == 2
        assert s.current_turn_index == 1
        assert len(s.history) == 3

    def test_apply_all_stops_on_inactive(self, scorer, match_id):
        from tests.conftest import match_ended
        events = [match_ended(), coin_pocketed("white")]
        s = scorer.initial_state(match_id, PLAYERS_3P)
        s = scorer.apply_all(s, events)
        # After match_ended, the coin_pocketed should NOT be in history
        assert not s.is_active
        assert len(s.history) == 1
