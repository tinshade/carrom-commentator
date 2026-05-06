from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

from carrom_caster.app import App
from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.domain.event import GameEvent
from carrom_caster.domain.match import MatchState
from carrom_caster.domain.player import Player, Team
from carrom_caster.persistence.repositories import MatchRepository
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.vision.calibration import CalibrationResult
from carrom_caster.vision.detector import CoinDetector
from carrom_caster.vision.events import EventDetector
from carrom_caster.vision.source import VideoSource
from carrom_caster.vision.tracker import CoinTracker


class _EventApp(App):
    """App subclass that fires callbacks on every game event."""

    def __init__(
        self,
        *args: object,
        on_event: Callable[[GameEvent, MatchState, str | None], None],
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._event_cb = on_event

    def _on_event(self, event: GameEvent, state: MatchState, commentary: str | None = None) -> None:
        super()._on_event(event, state, commentary)
        self._event_cb(event, state, commentary)


class PipelineThread(QThread):
    """Runs the App pipeline on a background thread, emitting Qt signals."""

    state_updated = Signal(object, object)  # (MatchState, commentary: str | None)
    match_finished = Signal(object)         # final MatchState
    error_occurred = Signal(str)

    def __init__(
        self,
        source: VideoSource,
        calibration: CalibrationResult,
        detector: CoinDetector,
        tracker: CoinTracker,
        event_detector: EventDetector,
        scorer: Scorer,
        commentary: CommentaryEngine,
        match_repo: MatchRepository,
        players: list[Player],
        teams: list[Team] | None = None,
    ) -> None:
        super().__init__()
        self._app = _EventApp(
            source=source,
            calibration=calibration,
            detector=detector,
            tracker=tracker,
            event_detector=event_detector,
            scorer=scorer,
            commentary=commentary,
            match_repo=match_repo,
            on_event=self._on_event_cb,
        )
        self._players = players
        self._teams = teams or []

    def _on_event_cb(self, event: GameEvent, state: MatchState, commentary: str | None) -> None:
        self.state_updated.emit(state, commentary)

    def run(self) -> None:
        try:
            state = self._app.run(self._players, self._teams or None)
            self.match_finished.emit(state)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def stop(self) -> None:
        self._app.stop()
        self.wait()
