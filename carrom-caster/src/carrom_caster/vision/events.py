"""
EventDetector: converts tracked coin positions into GameEvents.

State machine tracks:
 - Which coin IDs are active (for disappearance/pocket detection)
 - Per-coin position history (for velocity / STRIKE_TAKEN / TURN_ENDED)
 - Whether we are in a post-strike settling period
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.vision.types import TrackedCoin

_POCKET_CORNERS = {
    "top_left": Point(0.04, 0.04),
    "top_right": Point(0.96, 0.04),
    "bottom_left": Point(0.04, 0.96),
    "bottom_right": Point(0.96, 0.96),
}


def _dist(a: Point, b: Point) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _nearest_pocket(pos: Point, pocket_radius: float) -> str | None:
    for name, corner in _POCKET_CORNERS.items():
        if _dist(pos, corner) <= pocket_radius:
            return name
    return None


def _ts(frame_index: int, fps: float = 30.0) -> datetime:
    ms = int(frame_index * 1000 / fps)
    return datetime(1970, 1, 1, tzinfo=timezone.utc).replace(
        second=ms // 1000, microsecond=(ms % 1000) * 1000
    )


@dataclass
class _EventDetectorState:
    prev_ids: set[str] = field(default_factory=set)
    prev_positions: dict[str, Point] = field(default_factory=dict)
    # per-coin: how many consecutive frames velocity was below settle threshold
    settle_counts: dict[str, int] = field(default_factory=dict)
    post_strike: bool = False
    settle_frame_count: int = 0


class EventDetector:
    """Pure-Python state machine — no cv2/numpy dependency."""

    def __init__(
        self,
        pocket_radius: float = 0.06,
        strike_velocity: float = 0.02,
        settle_velocity: float = 0.002,
        settle_frames: int = 10,
        fps: float = 30.0,
    ) -> None:
        self._pocket_radius = pocket_radius
        self._strike_vel = strike_velocity
        self._settle_vel = settle_velocity
        self._settle_frames = settle_frames
        self._fps = fps
        self._state = _EventDetectorState()

    def update(self, coins: list[TrackedCoin], frame_index: int) -> list[GameEvent]:
        """Process one frame's tracked coins; return any newly detected events."""
        events: list[GameEvent] = []
        current_ids = {c.id for c in coins}
        current_pos = {c.id: c.position for c in coins}

        # ── Disappearance detection (pocket events) ──────────────────────────
        for coin_id in self._state.prev_ids - current_ids:
            last_pos = self._state.prev_positions.get(coin_id)
            if last_pos is None:
                continue
            pocket = _nearest_pocket(last_pos, self._pocket_radius)
            if pocket is None:
                continue  # lost due to occlusion, not pocketed

            color_str = coin_id.split("_")[0]
            payload: dict = {"coin_id": coin_id, "pocket_corner": pocket}

            if color_str == CoinColor.QUEEN.value:
                events.append(GameEvent(
                    type=EventType.QUEEN_POCKETED,
                    timestamp=_ts(frame_index, self._fps),
                    frame_index=frame_index,
                    payload={"pocket_corner": pocket},
                ))
            elif color_str == CoinColor.STRIKER.value:
                events.append(GameEvent(
                    type=EventType.STRIKER_POCKETED,
                    timestamp=_ts(frame_index, self._fps),
                    frame_index=frame_index,
                    payload={"pocket_corner": pocket},
                ))
            else:
                events.append(GameEvent(
                    type=EventType.COIN_POCKETED,
                    timestamp=_ts(frame_index, self._fps),
                    frame_index=frame_index,
                    payload={**payload, "color": color_str},
                ))

        # ── Velocity-based events (STRIKE_TAKEN / TURN_ENDED) ────────────────
        moving_count = 0
        for c in coins:
            prev = self._state.prev_positions.get(c.id)
            if prev is None:
                continue
            vel = _dist(c.position, prev)  # normalized units/frame
            if vel > self._strike_vel:
                moving_count += 1
                self._state.settle_counts[c.id] = 0
            elif vel < self._settle_vel:
                self._state.settle_counts[c.id] = (
                    self._state.settle_counts.get(c.id, 0) + 1
                )

        if moving_count > 0 and not self._state.post_strike:
            self._state.post_strike = True
            self._state.settle_frame_count = 0
            events.append(GameEvent(
                type=EventType.STRIKE_TAKEN,
                timestamp=_ts(frame_index, self._fps),
                frame_index=frame_index,
                payload={},
            ))

        if self._state.post_strike and moving_count == 0:
            all_settled = all(
                self._state.settle_counts.get(c.id, 0) >= self._settle_frames
                for c in coins
            )
            if all_settled:
                self._state.post_strike = False
                self._state.settle_counts.clear()
                events.append(GameEvent(
                    type=EventType.TURN_ENDED,
                    timestamp=_ts(frame_index, self._fps),
                    frame_index=frame_index,
                    payload={},
                ))

        self._state.prev_ids = current_ids
        self._state.prev_positions = current_pos
        return events

    def reset(self) -> None:
        self._state = _EventDetectorState()
