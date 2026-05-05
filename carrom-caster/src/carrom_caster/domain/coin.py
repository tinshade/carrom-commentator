from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class CoinColor(Enum):
    WHITE = "white"
    BLACK = "black"
    QUEEN = "queen"
    STRIKER = "striker"


class Point(NamedTuple):
    """Normalized board coordinate in [0, 1] × [0, 1] space."""

    x: float
    y: float


@dataclass(frozen=True)
class Coin:
    id: str
    color: CoinColor
    position: Point
    on_board: bool
