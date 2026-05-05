from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Player:
    id: UUID
    name: str


@dataclass(frozen=True)
class PlayerGroup:
    """A saved group of players for quick re-use."""

    id: UUID
    name: str
    members: tuple[Player, ...]  # tuple for hashability
    last_used: datetime


@dataclass(frozen=True)
class Team:
    """Two players paired for 4-player partner mode."""

    id: str
    name: str
    players: tuple[Player, ...]
