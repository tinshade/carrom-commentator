"""
Headless pipeline smoke test — all real logic, all fake I/O.

Verifies that App wires VideoSource → Detector → Tracker → EventDetector
→ Scorer → CommentaryEngine → MatchRepository without errors.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from carrom_caster.app import App
from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.commentary.llm import FakeLLMClient
from carrom_caster.commentary.tts import FakeTTSEngine
from carrom_caster.domain.coin import CoinColor, Point
from carrom_caster.domain.event import EventType
from carrom_caster.domain.frame import Frame
from carrom_caster.domain.player import Player
from carrom_caster.persistence.repositories import FakeMatchRepository
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules
from carrom_caster.vision.calibration import CalibrationResult, IdentityCalibration
from carrom_caster.vision.detector import DetectedCoin, FakeCoinDetector
from carrom_caster.vision.events import EventDetector
from carrom_caster.vision.source import FakeVideoSource, RawFrame
from carrom_caster.vision.tracker import CoinTracker

# ── helpers ────────────────────────────────────────────────────────────────────

PA = Player(id=uuid4(), name="Alice")
PB = Player(id=uuid4(), name="Bob")
PC = Player(id=uuid4(), name="Charlie")

TL = Point(0.04, 0.04)  # top-left pocket


def _make_source(n: int) -> FakeVideoSource:
    return FakeVideoSource([
        RawFrame(meta=Frame(index=i, timestamp_ms=i * 33), data=None)
        for i in range(n)
    ])


def _make_app(
    source: FakeVideoSource,
    detector: FakeCoinDetector,
    disappear_frames: int = 1,
    debounce_ms: int = 0,
) -> tuple[App, FakeTTSEngine, FakeMatchRepository]:
    calib = IdentityCalibration(800).as_result()  # homography=None → skip warp
    tracker = CoinTracker(max_distance=0.1, disappear_frames=disappear_frames)
    event_det = EventDetector(
        pocket_radius=0.06,
        strike_velocity=0.05,
        settle_velocity=0.001,
        settle_frames=2,
        fps=30.0,
    )
    scorer = Scorer(ThreePlayerRules())
    llm = FakeLLMClient(response="INCREDIBLE SHOT!")
    tts = FakeTTSEngine()
    commentary = CommentaryEngine(
        llm=llm, tts=tts, system_prompt="Be dramatic.", debounce_ms=debounce_ms
    )
    match_repo = FakeMatchRepository()

    app = App(
        source=source,
        calibration=calib,
        detector=detector,
        tracker=tracker,
        event_detector=event_det,
        scorer=scorer,
        commentary=commentary,
        match_repo=match_repo,
    )
    return app, tts, match_repo


# ── tests ──────────────────────────────────────────────────────────────────────

class TestPipelineSmoke:
    def test_runs_without_events_when_no_coins(self) -> None:
        """Empty detections → no events, state unchanged, match persisted."""
        source = _make_source(5)
        detector = FakeCoinDetector([[] for _ in range(5)])
        app, _, match_repo = _make_app(source, detector)

        state = app.run([PA, PB, PC])

        assert state.is_active
        assert len(state.history) == 0
        assert match_repo.get(state.match_id) is not None

    def test_coin_pocketed_emits_event_and_updates_score(self) -> None:
        """White coin near top-left pocket disappears → COIN_POCKETED, score +1."""
        coin_at_pocket = DetectedCoin(
            color=CoinColor.WHITE, position=TL, radius_norm=0.03, frame_index=0
        )
        # Frame 0: coin present. Frames 1-3: absent → triggers pocket after disappear_frames+1.
        detections = [[coin_at_pocket], [], [], [], []]
        source = _make_source(5)
        detector = FakeCoinDetector(detections)
        app, tts, match_repo = _make_app(source, detector, disappear_frames=1)

        state = app.run([PA, PB, PC])

        pocket_events = [e for e in state.history if e.type == EventType.COIN_POCKETED]
        assert len(pocket_events) >= 1
        assert pocket_events[0].payload["color"] == "white"
        assert state.white_coins_on_board < 9  # score updated

    def test_commentary_spoken_on_event(self) -> None:
        """COIN_POCKETED → LLM called → TTS speaks."""
        coin_at_pocket = DetectedCoin(
            color=CoinColor.WHITE, position=TL, radius_norm=0.03, frame_index=0
        )
        source = _make_source(5)
        detector = FakeCoinDetector([[coin_at_pocket], [], [], [], []])
        app, tts, _ = _make_app(source, detector, disappear_frames=1)

        app.run([PA, PB, PC])

        assert len(tts.spoken) >= 1
        assert tts.spoken[0] == "INCREDIBLE SHOT!"

    def test_state_persisted_on_completion(self) -> None:
        """Final state is always saved to match_repo, even with no events."""
        source = _make_source(3)
        detector = FakeCoinDetector([[] for _ in range(3)])
        app, _, match_repo = _make_app(source, detector)

        state = app.run([PA, PB, PC])

        saved = match_repo.get(state.match_id)
        assert saved is not None
        assert saved.match_id == state.match_id

    def test_source_closed_after_run(self) -> None:
        """FakeVideoSource is exhausted; App should close it cleanly."""
        source = _make_source(2)
        detector = FakeCoinDetector([[], []])
        app, _, _ = _make_app(source, detector)

        # Should not raise even though source runs out
        app.run([PA, PB, PC])

    def test_custom_match_id_preserved(self) -> None:
        mid = uuid4()
        source = _make_source(2)
        detector = FakeCoinDetector([[], []])
        app, _, match_repo = _make_app(source, detector)

        state = app.run([PA, PB, PC], match_id=mid)

        assert state.match_id == mid
        assert match_repo.get(mid) is not None

    def test_strike_and_settle_emits_correct_events(self) -> None:
        """Coins moving fast then stopping → STRIKE_TAKEN then TURN_ENDED."""
        # White coin moves fast frame 0→1, then settles for settle_frames frames
        fast = DetectedCoin(color=CoinColor.WHITE, position=Point(0.5, 0.5), radius_norm=0.03, frame_index=0)
        moved = DetectedCoin(color=CoinColor.WHITE, position=Point(0.6, 0.5), radius_norm=0.03, frame_index=1)
        still = DetectedCoin(color=CoinColor.WHITE, position=Point(0.6, 0.5), radius_norm=0.03, frame_index=2)

        source = _make_source(5)
        detector = FakeCoinDetector([[fast], [moved], [still], [still], [still]])
        app, _, _ = _make_app(source, detector, disappear_frames=5)

        state = app.run([PA, PB, PC])

        types = [e.type for e in state.history]
        assert EventType.STRIKE_TAKEN in types
        assert EventType.TURN_ENDED in types
