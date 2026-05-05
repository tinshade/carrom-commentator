from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    STRIKE_TAKEN = "strike_taken"
    COIN_POCKETED = "coin_pocketed"
    QUEEN_POCKETED = "queen_pocketed"
    QUEEN_COVERED = "queen_covered"
    STRIKER_POCKETED = "striker_pocketed"
    TURN_ENDED = "turn_ended"
    MATCH_ENDED = "match_ended"


@dataclass(frozen=True)
class GameEvent:
    """
    A single game event emitted by the EventDetector (or CLI loader).

    payload keys by type:
      COIN_POCKETED   : {coin_id: str, color: "white"|"black", pocket_corner: str}
      QUEEN_POCKETED  : {pocket_corner: str}
      QUEEN_COVERED   : {covered_by: str (player_id)}
      STRIKER_POCKETED: {pocket_corner: str}
      STRIKE_TAKEN    : {}
      TURN_ENDED      : {}
      MATCH_ENDED     : {}
    """

    type: EventType
    timestamp: datetime
    frame_index: int
    payload: dict[str, Any]
