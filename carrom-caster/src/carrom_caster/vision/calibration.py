"""
Board calibration via homography.

Usage:
    1. Capture a frame.
    2. Click the 4 board corners (top-left, top-right, bottom-right, bottom-left).
    3. Call compute_homography(corners) once per session.
    4. Pass CalibrationResult to warp_frame() before every detect() call.

Warped frame is output_size × output_size pixels.
Coin positions in the warped frame are divided by output_size to get [0,1] coords.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CalibrationResult:
    homography: Any  # np.ndarray 3x3 at runtime
    output_size: int  # warped frame is square: output_size × output_size px


class IdentityCalibration:
    """No-op calibration — coin positions are already normalized.

    Use in unit tests or when the camera is mounted directly above the board
    and already fills the frame without perspective distortion.
    """

    def __init__(self, output_size: int = 800) -> None:
        self.output_size = output_size

    def as_result(self) -> CalibrationResult:
        try:
            import numpy as np
            H: Any = np.eye(3, dtype=np.float32)
        except ImportError:
            H = None
        return CalibrationResult(homography=H, output_size=self.output_size)


def compute_homography(
    corners: list[tuple[int, int]],
    output_size: int = 800,
) -> CalibrationResult:
    """Compute homography from 4 board corners (pixels) to a square output.

    corners: [top_left, top_right, bottom_right, bottom_left] in pixel coords.
    """
    if len(corners) != 4:
        raise ValueError(f"Need exactly 4 corners, got {len(corners)}")
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise RuntimeError("opencv-python not installed — run: uv sync --extra vision")

    src = np.array(corners, dtype=np.float32)
    dst = np.array(
        [
            [0, 0],
            [output_size - 1, 0],
            [output_size - 1, output_size - 1],
            [0, output_size - 1],
        ],
        dtype=np.float32,
    )
    H, _ = cv2.findHomography(src, dst)
    return CalibrationResult(homography=H, output_size=output_size)


def warp_frame(data: Any, calibration: CalibrationResult) -> Any:
    """Apply homography warp to a raw image ndarray.

    Returns a square ndarray of shape (output_size, output_size, 3).
    """
    try:
        import cv2
    except ImportError:
        raise RuntimeError("opencv-python not installed — run: uv sync --extra vision")

    s = calibration.output_size
    return cv2.warpPerspective(data, calibration.homography, (s, s))
