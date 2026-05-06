"""Unit tests for CoinTracker — pure Python, no cv2/scipy required."""
from __future__ import annotations

import pytest

from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.vision.tracker import CoinTracker
from carrom_caster.vision.types import DetectedCoin


def _det(color: CoinColor, x: float, y: float, frame: int = 0) -> DetectedCoin:
    return DetectedCoin(color=color, position=Point(x, y), radius_norm=0.03, frame_index=frame)


W = CoinColor.WHITE
B = CoinColor.BLACK
Q = CoinColor.QUEEN


class TestNewCoins:
    def test_assigns_ids_to_first_frame(self) -> None:
        tracker = CoinTracker()
        coins = tracker.update([_det(W, 0.1, 0.1), _det(B, 0.9, 0.9)], frame_index=0)
        assert len(coins) == 2
        ids = {c.id for c in coins}
        assert any("white" in i for i in ids)
        assert any("black" in i for i in ids)

    def test_queen_id_is_queen(self) -> None:
        tracker = CoinTracker()
        coins = tracker.update([_det(Q, 0.5, 0.5)], frame_index=0)
        assert coins[0].id == "queen"

    def test_multiple_white_get_unique_ids(self) -> None:
        tracker = CoinTracker()
        coins = tracker.update([_det(W, 0.1, 0.1), _det(W, 0.2, 0.2)], frame_index=0)
        ids = [c.id for c in coins]
        assert len(set(ids)) == 2

    def test_frames_since_seen_zero_on_first_frame(self) -> None:
        tracker = CoinTracker()
        coins = tracker.update([_det(W, 0.5, 0.5)], frame_index=0)
        assert coins[0].frames_since_seen == 0


class TestStableIds:
    def test_same_coin_keeps_id_across_frames(self) -> None:
        tracker = CoinTracker(max_distance=0.05)
        coins0 = tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        coins1 = tracker.update([_det(W, 0.51, 0.51, 1)], frame_index=1)
        assert coins0[0].id == coins1[0].id

    def test_position_updated_on_match(self) -> None:
        tracker = CoinTracker(max_distance=0.05)
        tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        coins1 = tracker.update([_det(W, 0.52, 0.52, 1)], frame_index=1)
        assert coins1[0].position == Point(0.52, 0.52)

    def test_far_coin_gets_new_id(self) -> None:
        tracker = CoinTracker(max_distance=0.05)
        coins0 = tracker.update([_det(W, 0.1, 0.1, 0)], frame_index=0)
        coins1 = tracker.update([_det(W, 0.9, 0.9, 1)], frame_index=1)
        assert coins0[0].id != coins1[-1].id

    def test_different_colors_not_matched(self) -> None:
        tracker = CoinTracker()
        coins0 = tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        coins1 = tracker.update([_det(B, 0.5, 0.5, 1)], frame_index=1)
        # White coin from frame 0 should not match black detection
        white_ids = {c.id for c in coins0}
        black_ids = {c.id for c in coins1 if c.color == B}
        assert not white_ids.intersection(black_ids)


class TestDisappearance:
    def test_missing_coin_increments_frames_since_seen(self) -> None:
        tracker = CoinTracker(disappear_frames=5)
        tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        coins = tracker.update([], frame_index=1)
        assert len(coins) == 1
        assert coins[0].frames_since_seen == 1

    def test_coin_removed_after_disappear_frames(self) -> None:
        tracker = CoinTracker(disappear_frames=3)
        tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        for i in range(1, 5):  # 4 empty frames
            coins = tracker.update([], frame_index=i)
        assert len(coins) == 0

    def test_coin_still_present_at_disappear_limit(self) -> None:
        tracker = CoinTracker(disappear_frames=3)
        tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        for i in range(1, 4):  # exactly disappear_frames empty frames
            coins = tracker.update([], frame_index=i)
        assert len(coins) == 1

    def test_reappearing_coin_gets_fresh_id(self) -> None:
        tracker = CoinTracker(disappear_frames=2)
        coins0 = tracker.update([_det(W, 0.5, 0.5, 0)], frame_index=0)
        tracker.update([], frame_index=1)
        tracker.update([], frame_index=2)
        tracker.update([], frame_index=3)  # now removed
        coins4 = tracker.update([_det(W, 0.5, 0.5, 4)], frame_index=4)
        assert coins0[0].id != coins4[0].id


class TestReset:
    def test_reset_clears_state(self) -> None:
        tracker = CoinTracker()
        tracker.update([_det(W, 0.1, 0.1)], frame_index=0)
        tracker.reset()
        coins = tracker.update([_det(W, 0.1, 0.1)], frame_index=1)
        assert coins[0].id == "white_0"
