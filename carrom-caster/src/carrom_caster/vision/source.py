from __future__ import annotations

from typing import Any, Protocol

from carrom_caster.domain.frame import Frame
from carrom_caster.vision.types import RawFrame


class VideoSource(Protocol):
    def read(self) -> RawFrame | None: ...
    def close(self) -> None: ...


class FakeVideoSource:
    """Yields frames from a pre-built list — for unit tests and replay."""

    def __init__(self, frames: list[RawFrame]) -> None:
        self._frames = frames
        self._index = 0

    def read(self) -> RawFrame | None:
        if self._index >= len(self._frames):
            return None
        frame = self._frames[self._index]
        self._index += 1
        return frame

    def close(self) -> None:
        pass

    @classmethod
    def blank(cls, count: int, width: int = 640, height: int = 480) -> FakeVideoSource:
        """Creates n blank (black) frames — useful for structural tests."""
        try:
            import numpy as np
            data: Any = np.zeros((height, width, 3), dtype=np.uint8)
        except ImportError:
            data = None
        frames = [
            RawFrame(meta=Frame(index=i, timestamp_ms=i * 33), data=data)
            for i in range(count)
        ]
        return cls(frames)


class PhoneCameraSource:
    """Reads MJPEG/RTSP stream from IP Webcam (Android) or EpocCam (iOS)."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._cap: Any = None
        self._frame_index = 0

    def _open(self) -> Any:
        if self._cap is None:
            try:
                import cv2
            except ImportError:
                raise RuntimeError("opencv-python not installed — run: uv sync --extra vision")
            self._cap = cv2.VideoCapture(self._url)
            if not self._cap.isOpened():
                raise RuntimeError(f"Cannot open camera stream: {self._url}")
        return self._cap

    def read(self) -> RawFrame | None:
        import time
        cap = self._open()
        ok, data = cap.read()
        if not ok or data is None:
            return None
        meta = Frame(index=self._frame_index, timestamp_ms=int(time.monotonic() * 1000))
        self._frame_index += 1
        return RawFrame(meta=meta, data=data)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class FileVideoSource:
    """Reads a recorded video file — for integration tests and replay."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._cap: Any = None
        self._frame_index = 0

    def _open(self) -> Any:
        if self._cap is None:
            try:
                import cv2
            except ImportError:
                raise RuntimeError("opencv-python not installed — run: uv sync --extra vision")
            self._cap = cv2.VideoCapture(self._path)
            if not self._cap.isOpened():
                raise RuntimeError(f"Cannot open video file: {self._path}")
        return self._cap

    def read(self) -> RawFrame | None:
        cap = self._open()
        ok, data = cap.read()
        if not ok or data is None:
            return None
        fps = self._cap.get(5) or 30.0  # type: ignore[union-attr]
        ts_ms = int(self._frame_index * 1000 / fps)
        meta = Frame(index=self._frame_index, timestamp_ms=ts_ms)
        self._frame_index += 1
        return RawFrame(meta=meta, data=data)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
