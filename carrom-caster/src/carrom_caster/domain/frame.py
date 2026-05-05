from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    """Metadata for a single camera frame. Image data lives in the vision layer."""

    index: int
    timestamp_ms: int  # milliseconds since match start
