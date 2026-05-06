"""
Composition root for the headless pipeline.

App wires all stages together and runs the main loop:
  VideoSource → warp → Detector → Tracker → EventDetector
                               ↓
               Scorer (score) + CommentaryEngine (audio)
                               ↓
                      MatchRepository (persist)
"""
from __future__ import annotations

import structlog
from uuid import UUID, uuid4

from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.domain.event import GameEvent
from carrom_caster.domain.match import MatchState
from carrom_caster.domain.player import Player, Team
from carrom_caster.persistence.repositories import MatchRepository
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.vision.calibration import CalibrationResult, warp_frame
from carrom_caster.vision.detector import CoinDetector
from carrom_caster.vision.events import EventDetector
from carrom_caster.vision.source import VideoSource
from carrom_caster.vision.tracker import CoinTracker

log = structlog.get_logger()

_SAVE_EVERY_N_FRAMES = 30


class App:
    """Headless pipeline — no UI dependency."""

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
    ) -> None:
        self._source = source
        self._calibration = calibration
        self._detector = detector
        self._tracker = tracker
        self._event_detector = event_detector
        self._scorer = scorer
        self._commentary = commentary
        self._match_repo = match_repo

    def run(
        self,
        players: list[Player],
        teams: list[Team] | None = None,
        match_id: UUID | None = None,
    ) -> MatchState:
        """Run the full pipeline until the match ends or source is exhausted."""
        state = self._scorer.initial_state(match_id or uuid4(), players, teams or [])
        log.info("match_started", match_id=str(state.match_id), players=[p.name for p in players])

        try:
            while state.is_active:
                raw = self._source.read()
                if raw is None:
                    log.info("source_exhausted")
                    break

                # Calibration warp (skip if no homography — identity / test mode)
                image = raw.data
                if image is not None and self._calibration.homography is not None:
                    image = warp_frame(image, self._calibration)

                detections = self._detector.detect(image, raw.meta.index)
                tracked = self._tracker.update(detections, raw.meta.index)
                events = self._event_detector.update(tracked, raw.meta.index)

                for ev in events:
                    state = self._scorer.apply(state, ev)
                    commentary_text = self._commentary.on_event(ev, state)
                    self._on_event(ev, state, commentary_text)

                if raw.meta.index % _SAVE_EVERY_N_FRAMES == 0:
                    self._match_repo.save(state)

        finally:
            self._match_repo.save(state)
            self._source.close()

        log.info(
            "match_ended",
            match_id=str(state.match_id),
            is_active=state.is_active,
            events_total=len(state.history),
        )
        return state

    def stop(self) -> None:
        """Close the video source so the pipeline loop exits on the next read."""
        self._source.close()

    def _on_event(self, event: GameEvent, state: MatchState, commentary: str | None = None) -> None:
        """Hook for subclasses (e.g. UI layer). Default: structured log."""
        log.info(
            "game_event",
            type=event.type.value,
            player=state.current_player.name,
            frame=event.frame_index,
        )
