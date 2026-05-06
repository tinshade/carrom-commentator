from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.domain.frame import Frame


@dataclass
class RawFrame:
    """Camera frame metadata + pixel data (numpy ndarray in BGR format)."""

    meta: Frame
    data: Any  # np.ndarray HxWx3 at runtime


@dataclass(frozen=True)
class DetectedCoin:
    """A coin found by color detection in a single frame."""

    color: CoinColor
    position: Point  # normalized [0,1]x[0,1] after calibration
    radius_norm: float  # normalized radius
    frame_index: int


@dataclass(frozen=True)
class TrackedCoin:
    """A coin with a stable cross-frame identity."""

    id: str  # e.g. "white_0", "black_3", "queen", "striker"
    color: CoinColor
    position: Point
    radius_norm: float
    frame_index: int
    frames_since_seen: int = 0
