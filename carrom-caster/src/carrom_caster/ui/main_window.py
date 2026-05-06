from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.commentary.llm import AnthropicClient, OllamaClient
from carrom_caster.commentary.prompts import load_system_prompt
from carrom_caster.commentary.tts import FakeTTSEngine, Pyttsx3Engine
from carrom_caster.config import AppConfig, Secrets
from carrom_caster.domain.match import MatchMode
from carrom_caster.domain.player import Player, Team
from carrom_caster.persistence.repositories import (
    SqliteMatchRepository,
    SqlitePlayerGroupRepository,
)
from carrom_caster.scoring.four_player import FourPlayerRules
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules
from carrom_caster.vision.calibration import IdentityCalibration, compute_homography
from carrom_caster.vision.detector import DetectorConfig, HsvDetector, HsvRange
from carrom_caster.vision.events import EventDetector
from carrom_caster.vision.source import PhoneCameraSource
from carrom_caster.vision.tracker import CoinTracker

from carrom_caster.ui.pipeline_thread import PipelineThread
from carrom_caster.ui.screens.history_screen import HistoryScreen
from carrom_caster.ui.screens.match_screen import MatchScreen
from carrom_caster.ui.screens.setup_screen import SetupScreen

_IDX_SETUP = 0
_IDX_MATCH = 1
_IDX_HISTORY = 2


class MainWindow(QMainWindow):
    def __init__(self, config_path: str = "config/default.yaml") -> None:
        super().__init__()
        self.setWindowTitle("Carrom Caster")
        self.setMinimumSize(640, 740)

        self._cfg = AppConfig.load(config_path)
        self._secrets = Secrets()  # type: ignore[call-arg]

        db_path = Path(self._cfg.persistence.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = sa.create_engine(f"sqlite:///{db_path}")

        self._match_repo = SqliteMatchRepository(engine)
        self._group_repo = SqlitePlayerGroupRepository(engine)
        self._pipeline: PipelineThread | None = None

        stack = QStackedWidget()
        self.setCentralWidget(stack)
        self._stack = stack

        self._setup_screen = SetupScreen(self._group_repo)
        self._match_screen = MatchScreen()
        self._history_screen = HistoryScreen(self._match_repo)

        stack.addWidget(self._setup_screen)   # _IDX_SETUP
        stack.addWidget(self._match_screen)   # _IDX_MATCH
        stack.addWidget(self._history_screen) # _IDX_HISTORY

        self._setup_screen.match_requested.connect(self._on_match_requested)
        self._match_screen.end_requested.connect(self._on_end_requested)
        self._history_screen.back_requested.connect(
            lambda: self._stack.setCurrentIndex(_IDX_SETUP)
        )

        menu = self.menuBar()
        view_menu = menu.addMenu("View")
        hist_action = view_menu.addAction("Match History")
        hist_action.triggered.connect(self.show_history)  # type: ignore[union-attr]

    def show_history(self) -> None:
        self._history_screen.refresh()
        self._stack.setCurrentIndex(_IDX_HISTORY)

    @Slot(object, object)
    def _on_match_requested(self, players: object, teams: object) -> None:
        player_list: list[Player] = players  # type: ignore[assignment]
        team_list: list[Team] = teams  # type: ignore[assignment]

        cfg = self._cfg
        vc = cfg.vision

        source = PhoneCameraSource(self._setup_screen.camera_url)

        if vc.calibration_corners:
            corners = [tuple(c) for c in vc.calibration_corners]
            calibration = compute_homography(corners)  # type: ignore[arg-type]
        else:
            calibration = IdentityCalibration(800).as_result()

        c = vc.colors
        detector = HsvDetector(
            DetectorConfig(
                white=HsvRange(lower=tuple(c.white.lower), upper=tuple(c.white.upper)),  # type: ignore[arg-type]
                black=HsvRange(lower=tuple(c.black.lower), upper=tuple(c.black.upper)),  # type: ignore[arg-type]
                queen=HsvRange(lower=tuple(c.queen.lower), upper=tuple(c.queen.upper)),  # type: ignore[arg-type]
            )
        )
        tracker = CoinTracker(
            max_distance=vc.max_centroid_distance,
            disappear_frames=vc.disappear_frames,
        )
        event_det = EventDetector(
            pocket_radius=vc.pocket_radius,
            strike_velocity=vc.strike_velocity_threshold,
            settle_velocity=vc.settle_velocity_threshold,
            settle_frames=vc.settle_frames,
        )

        mode = MatchMode.FOUR_PLAYER_PARTNERS if len(team_list) == 2 else MatchMode.THREE_PLAYER_FFA
        rules = FourPlayerRules() if mode == MatchMode.FOUR_PLAYER_PARTNERS else ThreePlayerRules()
        scorer = Scorer(rules)

        cc = cfg.commentary
        if self._setup_screen.dry_run:
            tts: object = FakeTTSEngine()
        else:
            tts = Pyttsx3Engine()

        llm_prov = self._setup_screen.llm_provider
        if llm_prov == "anthropic":
            llm: object = AnthropicClient(api_key=self._secrets.anthropic_api_key)
        else:
            llm = OllamaClient(model=cc.ollama_model)

        system_prompt = load_system_prompt(cc.prompt_path)
        commentary = CommentaryEngine(
            llm=llm,  # type: ignore[arg-type]
            tts=tts,  # type: ignore[arg-type]
            system_prompt=system_prompt,
            max_tokens=cc.max_tokens,
            debounce_ms=cc.debounce_ms,
        )

        self._pipeline = PipelineThread(
            source=source,
            calibration=calibration,
            detector=detector,
            tracker=tracker,
            event_detector=event_det,
            scorer=scorer,
            commentary=commentary,
            match_repo=self._match_repo,
            players=player_list,
            teams=team_list or None,
        )
        self._pipeline.state_updated.connect(self._match_screen.on_state_updated)
        self._pipeline.match_finished.connect(self._match_screen.on_match_finished)
        self._pipeline.error_occurred.connect(self._on_pipeline_error)

        self._match_screen.reset()
        self._stack.setCurrentIndex(_IDX_MATCH)
        self._pipeline.start()

    @Slot()
    def _on_end_requested(self) -> None:
        if self._pipeline and self._pipeline.isRunning():
            self._pipeline.stop()
            self._pipeline = None
        self._stack.setCurrentIndex(_IDX_SETUP)

    @Slot(str)
    def _on_pipeline_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Pipeline Error", msg)
        self._pipeline = None
        self._stack.setCurrentIndex(_IDX_SETUP)

    def closeEvent(self, event: object) -> None:
        if self._pipeline and self._pipeline.isRunning():
            self._pipeline.stop()
        super().closeEvent(event)  # type: ignore[arg-type]
