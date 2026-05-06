from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from carrom_caster.domain.player import Player, PlayerGroup, Team
from carrom_caster.persistence.repositories import PlayerGroupRepository


class SetupScreen(QWidget):
    match_requested = Signal(object, object)  # (list[Player], list[Team])

    def __init__(self, group_repo: PlayerGroupRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._group_repo = group_repo
        self._build_ui()
        self._refresh_groups()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)

        title = QLabel("Carrom Caster")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 8px;")
        root.addWidget(title)

        # ── Player group ────────────────────────────────────────────────────────
        grp_box = QGroupBox("Player Group")
        grp_layout = QHBoxLayout(grp_box)
        self._group_combo = QComboBox()
        self._group_combo.setMinimumWidth(160)
        grp_layout.addWidget(self._group_combo, stretch=1)
        for label, slot in [("Load", self._load_group), ("Save", self._save_group), ("Delete", self._delete_group)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            grp_layout.addWidget(btn)
        root.addWidget(grp_box)

        # ── Mode ────────────────────────────────────────────────────────────────
        mode_box = QGroupBox("Match Mode")
        mode_layout = QHBoxLayout(mode_box)
        self._mode_3p = QRadioButton("3 Player FFA")
        self._mode_3p.setChecked(True)
        self._mode_3p.toggled.connect(self._on_mode_changed)
        self._mode_4p = QRadioButton("4 Player Partners")
        mode_layout.addWidget(self._mode_3p)
        mode_layout.addWidget(self._mode_4p)
        root.addWidget(mode_box)

        # ── Player names ────────────────────────────────────────────────────────
        players_box = QGroupBox("Players")
        players_layout = QFormLayout(players_box)
        self._player_edits: list[QLineEdit] = []
        for i in range(4):
            edit = QLineEdit(f"Player {i + 1}")
            self._player_edits.append(edit)
            players_layout.addRow(f"Player {i + 1}:", edit)
        root.addWidget(players_box)

        # ── Camera ──────────────────────────────────────────────────────────────
        cam_box = QGroupBox("Camera")
        cam_layout = QFormLayout(cam_box)
        self._camera_url = QLineEdit("http://192.168.1.100:8080/video")
        cam_layout.addRow("IP Webcam URL:", self._camera_url)
        root.addWidget(cam_box)

        # ── Providers ───────────────────────────────────────────────────────────
        prov_box = QGroupBox("Providers")
        prov_layout = QFormLayout(prov_box)
        self._llm_combo = QComboBox()
        self._llm_combo.addItems(["ollama (local)", "anthropic", "openai"])
        prov_layout.addRow("LLM:", self._llm_combo)
        self._tts_combo = QComboBox()
        self._tts_combo.addItems(["pyttsx3 (offline)", "elevenlabs"])
        prov_layout.addRow("TTS:", self._tts_combo)
        self._dry_run = QCheckBox("Dry run (print commentary, no audio)")
        prov_layout.addRow(self._dry_run)
        root.addWidget(prov_box)

        root.addStretch()

        # ── History link ────────────────────────────────────────────────────────
        hist_btn = QPushButton("View Match History →")
        hist_btn.setFlat(True)
        hist_btn.setStyleSheet("color: #0078d4; text-decoration: underline;")
        hist_btn.clicked.connect(self._history_requested)
        root.addWidget(hist_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # ── Start ───────────────────────────────────────────────────────────────
        self._start_btn = QPushButton("Start Match")
        self._start_btn.setMinimumHeight(48)
        self._start_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._start_btn.clicked.connect(self._on_start)
        root.addWidget(self._start_btn)

        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        four = self._mode_4p.isChecked()
        self._player_edits[3].setEnabled(four)
        row_widget = self._player_edits[3].parent()
        if row_widget:
            row_widget.setVisible(four)
        self._player_edits[3].setVisible(four)

    def _refresh_groups(self) -> None:
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("-- saved groups --", userData=None)
        for g in self._group_repo.list_all():
            self._group_combo.addItem(g.name, userData=g)
        self._group_combo.blockSignals(False)

    def _load_group(self) -> None:
        g: PlayerGroup | None = self._group_combo.currentData()
        if g is None:
            return
        for i, member in enumerate(g.members[:4]):
            self._player_edits[i].setText(member.name)
        if len(g.members) >= 4:
            self._mode_4p.setChecked(True)
        else:
            self._mode_3p.setChecked(True)

    def _save_group(self) -> None:
        names = self._player_names()
        if len(names) < 3:
            QMessageBox.warning(self, "Validation", "Enter at least 3 player names.")
            return
        players = tuple(Player(id=uuid4(), name=n) for n in names)
        group = PlayerGroup(
            id=uuid4(),
            name=", ".join(names),
            members=players,
            last_used=datetime.now(timezone.utc),
        )
        self._group_repo.save(group)
        self._refresh_groups()

    def _delete_group(self) -> None:
        g: PlayerGroup | None = self._group_combo.currentData()
        if g is None:
            return
        self._group_repo.delete(g.id)
        self._refresh_groups()

    def _history_requested(self) -> None:
        # Emitted to main window via a signal on the parent stack
        self.window().show_history()  # type: ignore[attr-defined]

    def _player_names(self) -> list[str]:
        count = 4 if self._mode_4p.isChecked() else 3
        return [n for i in range(count) if (n := self._player_edits[i].text().strip())]

    def _on_start(self) -> None:
        count = 4 if self._mode_4p.isChecked() else 3
        names = self._player_names()
        if len(names) < count:
            QMessageBox.warning(self, "Validation", f"Enter all {count} player names.")
            return
        players = [Player(id=uuid4(), name=n) for n in names]
        teams: list[Team] = []
        if self._mode_4p.isChecked():
            teams = [
                Team(id="team_a", name="Team A", players=(players[0], players[2])),
                Team(id="team_b", name="Team B", players=(players[1], players[3])),
            ]
        self.match_requested.emit(players, teams)

    @property
    def camera_url(self) -> str:
        return self._camera_url.text().strip()

    @property
    def dry_run(self) -> bool:
        return self._dry_run.isChecked()

    @property
    def llm_provider(self) -> str:
        txt = self._llm_combo.currentText()
        if "anthropic" in txt:
            return "anthropic"
        if "openai" in txt:
            return "openai"
        return "ollama"

    @property
    def tts_provider(self) -> str:
        return "elevenlabs" if "elevenlabs" in self._tts_combo.currentText() else "pyttsx3"
