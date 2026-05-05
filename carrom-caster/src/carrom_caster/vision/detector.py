"""
Coin detection via HSV color segmentation + HoughCircles.

Each color (white, black, queen, striker) has an HSV lower/upper range.
HoughCircles finds circular blobs matching the expected coin radius.
Positions are divided by output_size to normalize to [0,1].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.vision.types import DetectedCoin


@dataclass(frozen=True)
class HsvRange:
    lower: tuple[int, int, int]
    upper: tuple[int, int, int]


@dataclass(frozen=True)
class DetectorConfig:
    white: HsvRange
    black: HsvRange
    queen: HsvRange
    # Min/max coin radius in the warped frame (pixels).
    min_radius_px: int = 15
    max_radius_px: int = 35
    # Striker is larger — anything above this ratio of max_radius is striker.
    striker_radius_ratio: float = 1.4
    hough_param1: int = 50
    hough_param2: int = 25

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> DetectorConfig:
        def _range(d: dict[str, Any]) -> HsvRange:
            return HsvRange(lower=tuple(d["lower"]), upper=tuple(d["upper"]))  # type: ignore[arg-type]

        colors = cfg["colors"]
        return cls(
            white=_range(colors["white"]),
            black=_range(colors["black"]),
            queen=_range(colors["queen"]),
        )


class CoinDetector(Protocol):
    def detect(self, warped_image: Any, frame_index: int) -> list[DetectedCoin]: ...


class FakeCoinDetector:
    """Returns pre-configured detections per frame — for unit tests."""

    def __init__(self, detections: list[list[DetectedCoin]] | None = None) -> None:
        self._detections = detections or []
        self._call_count = 0

    def detect(self, warped_image: Any, frame_index: int) -> list[DetectedCoin]:
        if self._call_count < len(self._detections):
            result = self._detections[self._call_count]
        else:
            result = []
        self._call_count += 1
        return result


class HsvDetector:
    """Real detector: HSV masking + HoughCircles per color."""

    def __init__(self, config: DetectorConfig) -> None:
        self._cfg = config

    def detect(self, warped_image: Any, frame_index: int) -> list[DetectedCoin]:
        try:
            import cv2
            import numpy as np
        except ImportError:
            raise RuntimeError("opencv-python not installed — run: uv sync --extra vision")

        output_size = warped_image.shape[0]
        hsv = cv2.cvtColor(warped_image, cv2.COLOR_BGR2HSV)
        coins: list[DetectedCoin] = []

        color_map = [
            (CoinColor.WHITE, self._cfg.white),
            (CoinColor.BLACK, self._cfg.black),
            (CoinColor.QUEEN, self._cfg.queen),
        ]
        for color, hsv_range in color_map:
            mask = cv2.inRange(
                hsv,
                np.array(hsv_range.lower, dtype=np.uint8),
                np.array(hsv_range.upper, dtype=np.uint8),
            )
            circles = cv2.HoughCircles(
                mask,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=self._cfg.min_radius_px * 2,
                param1=self._cfg.hough_param1,
                param2=self._cfg.hough_param2,
                minRadius=self._cfg.min_radius_px,
                maxRadius=self._cfg.max_radius_px,
            )
            if circles is None:
                continue
            for cx, cy, r in np.round(circles[0]).astype(int):
                norm_r = float(r) / output_size
                actual_color = color
                if color == CoinColor.WHITE:
                    if r > self._cfg.max_radius_px * self._cfg.striker_radius_ratio:
                        actual_color = CoinColor.STRIKER
                coins.append(
                    DetectedCoin(
                        color=actual_color,
                        position=Point(x=float(cx) / output_size, y=float(cy) / output_size),
                        radius_norm=norm_r,
                        frame_index=frame_index,
                    )
                )
        return coins
