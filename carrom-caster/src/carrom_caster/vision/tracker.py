"""
Coin tracker: assigns stable IDs to DetectedCoins across frames.

Hungarian algorithm (scipy) matches new detections to existing tracked coins
by Euclidean distance. Falls back to greedy nearest-neighbour if scipy is absent.

A coin that is unmatched for `disappear_frames` consecutive frames is removed
from the active set — the EventDetector treats that as a pocket event.
"""
from __future__ import annotations

import math
from dataclasses import replace

from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.vision.types import DetectedCoin, TrackedCoin

_COLOR_ORDER = (CoinColor.WHITE, CoinColor.BLACK, CoinColor.QUEEN, CoinColor.STRIKER)


def _dist(a: Point, b: Point) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _match(cost: list[list[float]]) -> list[tuple[int, int]]:
    """Return (row, col) assignment pairs that minimise total cost."""
    if not cost or not cost[0]:
        return []
    try:
        from scipy.optimize import linear_sum_assignment
        import numpy as np

        rows, cols = linear_sum_assignment(np.array(cost))
        return list(zip(rows.tolist(), cols.tolist()))
    except ImportError:
        return _greedy(cost)


def _greedy(cost: list[list[float]]) -> list[tuple[int, int]]:
    """O(n²) greedy fallback — good enough for ≤20 coins."""
    used_rows: set[int] = set()
    used_cols: set[int] = set()
    pairs: list[tuple[int, int]] = []
    flat = sorted(
        ((cost[r][c], r, c) for r in range(len(cost)) for c in range(len(cost[0]))),
    )
    for _, r, c in flat:
        if r not in used_rows and c not in used_cols:
            pairs.append((r, c))
            used_rows.add(r)
            used_cols.add(c)
    return pairs


class CoinTracker:
    """Maintains stable coin IDs frame-to-frame via distance matching."""

    def __init__(
        self,
        max_distance: float = 0.05,
        disappear_frames: int = 5,
    ) -> None:
        self._max_distance = max_distance
        self._disappear_frames = disappear_frames
        self._tracked: list[TrackedCoin] = []
        self._next_id: dict[CoinColor, int] = {c: 0 for c in _COLOR_ORDER}

    def update(self, detections: list[DetectedCoin], frame_index: int) -> list[TrackedCoin]:
        """Match detections to existing tracked coins; return updated tracked set."""
        if not self._tracked:
            self._tracked = [self._new(d, frame_index) for d in detections]
            return list(self._tracked)

        # Build cost matrix: tracked × detected (same color only; inf otherwise)
        n, m = len(self._tracked), len(detections)
        INF = 1e9
        cost = [
            [
                _dist(self._tracked[r].position, detections[c].position)
                if self._tracked[r].color == detections[c].color
                else INF
                for c in range(m)
            ]
            for r in range(n)
        ]

        pairs = _match(cost) if (n > 0 and m > 0) else []
        matched_tracked: set[int] = set()
        matched_det: set[int] = set()
        updated: list[TrackedCoin] = []

        for r, c in pairs:
            if cost[r][c] <= self._max_distance:
                updated.append(
                    replace(
                        self._tracked[r],
                        position=detections[c].position,
                        radius_norm=detections[c].radius_norm,
                        frame_index=frame_index,
                        frames_since_seen=0,
                    )
                )
                matched_tracked.add(r)
                matched_det.add(c)

        # Unmatched tracked: increment absence counter or drop if over limit.
        for r, tc in enumerate(self._tracked):
            if r not in matched_tracked:
                absent = replace(tc, frames_since_seen=tc.frames_since_seen + 1)
                if absent.frames_since_seen <= self._disappear_frames:
                    updated.append(absent)

        # Unmatched detections: new coins.
        for c, det in enumerate(detections):
            if c not in matched_det:
                updated.append(self._new(det, frame_index))

        self._tracked = updated
        return list(self._tracked)

    def _new(self, det: DetectedCoin, frame_index: int) -> TrackedCoin:
        idx = self._next_id[det.color]
        self._next_id[det.color] += 1
        coin_id = det.color.value if det.color == CoinColor.QUEEN else f"{det.color.value}_{idx}"
        return TrackedCoin(
            id=coin_id,
            color=det.color,
            position=det.position,
            radius_norm=det.radius_norm,
            frame_index=frame_index,
            frames_since_seen=0,
        )

    def reset(self) -> None:
        self._tracked = []
        self._next_id = {c: 0 for c in _COLOR_ORDER}
