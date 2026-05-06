"""Unit tests for EventDetector state machine — pure Python, no cv2 required."""
from __future__ import annotations

import pytest

from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.domain.event import EventType
from carrom_caster.vision.events import EventDetector
from carrom_caster.vision.types import TrackedCoin


def _coin(
    coin_id: str,
    color: CoinColor,
    x: float,
    y: float,
    frame: int = 0,
    fseen: int = 0,
) -> TrackedCoin:
    return TrackedCoin(
        id=coin_id,
        color=color,
        position=Point(x, y),
        radius_norm=0.03,
        frame_index=frame,
        frames_since_seen=fseen,
    )


W = CoinColor.WHITE
B = CoinColor.BLACK
Q = CoinColor.QUEEN
S = CoinColor.STRIKER

# Pocket positions from config
TL = Point(0.04, 0.04)
TR = Point(0.96, 0.04)
BL = Point(0.04, 0.96)
BR = Point(0.96, 0.96)


def _detector(**kwargs) -> EventDetector:
    defaults = dict(
        pocket_radius=0.06,
        strike_velocity=0.02,
        settle_velocity=0.002,
        settle_frames=3,
        fps=30.0,
    )
    defaults.update(kwargs)
    return EventDetector(**defaults)


class TestCoinPocketed:
    def test_white_coin_disappears_near_pocket(self) -> None:
        det = _detector()
        det.update([_coin("white_0", W, TL.x, TL.y, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        pocket_events = [e for e in events if e.type == EventType.COIN_POCKETED]
        assert len(pocket_events) == 1
        assert pocket_events[0].payload["color"] == "white"
        assert pocket_events[0].payload["pocket_corner"] == "top_left"

    def test_black_coin_disappears_near_pocket(self) -> None:
        det = _detector()
        det.update([_coin("black_0", B, BR.x, BR.y, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        types = [e.type for e in events]
        assert EventType.COIN_POCKETED in types

    def test_coin_disappears_not_near_pocket_no_event(self) -> None:
        det = _detector()
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        pocket_events = [e for e in events if e.type == EventType.COIN_POCKETED]
        assert len(pocket_events) == 0

    def test_coin_id_in_payload(self) -> None:
        det = _detector()
        det.update([_coin("white_3", W, TL.x, TL.y, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        assert events[0].payload["coin_id"] == "white_3"

    def test_multiple_coins_pocketed_same_frame(self) -> None:
        det = _detector()
        det.update([
            _coin("white_0", W, TL.x, TL.y, 0),
            _coin("black_0", B, TR.x, TR.y, 0),
        ], frame_index=0)
        events = det.update([], frame_index=1)
        pocket_events = [e for e in events if e.type == EventType.COIN_POCKETED]
        assert len(pocket_events) == 2


class TestQueenPocketed:
    def test_queen_disappears_near_pocket(self) -> None:
        det = _detector()
        det.update([_coin("queen", Q, TR.x, TR.y, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        queen_events = [e for e in events if e.type == EventType.QUEEN_POCKETED]
        assert len(queen_events) == 1
        assert queen_events[0].payload["pocket_corner"] == "top_right"

    def test_queen_disappears_not_near_pocket_no_event(self) -> None:
        det = _detector()
        det.update([_coin("queen", Q, 0.5, 0.5, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        assert not any(e.type == EventType.QUEEN_POCKETED for e in events)


class TestStrikerPocketed:
    def test_striker_disappears_near_pocket(self) -> None:
        det = _detector()
        det.update([_coin("striker_0", S, BL.x, BL.y, 0)], frame_index=0)
        events = det.update([], frame_index=1)
        assert any(e.type == EventType.STRIKER_POCKETED for e in events)


class TestStrikeTaken:
    def test_fast_movement_emits_strike(self) -> None:
        det = _detector(strike_velocity=0.02)
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        # Move fast (0.1 >> 0.02 threshold)
        events = det.update([_coin("white_0", W, 0.6, 0.5, 1)], frame_index=1)
        assert any(e.type == EventType.STRIKE_TAKEN for e in events)

    def test_slow_movement_no_strike(self) -> None:
        det = _detector(strike_velocity=0.02)
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        events = det.update([_coin("white_0", W, 0.501, 0.5, 1)], frame_index=1)
        assert not any(e.type == EventType.STRIKE_TAKEN for e in events)

    def test_strike_only_emitted_once(self) -> None:
        det = _detector(strike_velocity=0.02)
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        det.update([_coin("white_0", W, 0.6, 0.5, 1)], frame_index=1)
        events2 = det.update([_coin("white_0", W, 0.7, 0.5, 2)], frame_index=2)
        assert not any(e.type == EventType.STRIKE_TAKEN for e in events2)


class TestTurnEnded:
    def test_coins_settle_after_strike(self) -> None:
        det = _detector(strike_velocity=0.02, settle_velocity=0.002, settle_frames=2)
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        det.update([_coin("white_0", W, 0.6, 0.5, 1)], frame_index=1)  # fast → strike
        det.update([_coin("white_0", W, 0.600, 0.5, 2)], frame_index=2)  # settled
        events = det.update([_coin("white_0", W, 0.600, 0.5, 3)], frame_index=3)  # settled frame 2
        assert any(e.type == EventType.TURN_ENDED for e in events)

    def test_no_turn_ended_before_settle_frames(self) -> None:
        det = _detector(strike_velocity=0.02, settle_velocity=0.002, settle_frames=5)
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        det.update([_coin("white_0", W, 0.6, 0.5, 1)], frame_index=1)
        # Only 1 settled frame — not enough
        events = det.update([_coin("white_0", W, 0.6, 0.5, 2)], frame_index=2)
        assert not any(e.type == EventType.TURN_ENDED for e in events)

    def test_no_turn_ended_without_prior_strike(self) -> None:
        det = _detector(settle_frames=1)
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        events = det.update([_coin("white_0", W, 0.5, 0.5, 1)], frame_index=1)
        assert not any(e.type == EventType.TURN_ENDED for e in events)


class TestReset:
    def test_reset_clears_state(self) -> None:
        det = _detector()
        det.update([_coin("white_0", W, 0.5, 0.5, 0)], frame_index=0)
        det.reset()
        # After reset, same coin ID disappearing should not produce events
        # (prev_ids is empty, so no disappearance can be detected)
        events = det.update([], frame_index=1)
        assert events == []
