from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from carrom_caster.domain.match import MatchState
from carrom_caster.persistence.repositories import MatchRepository


class HistoryScreen(QWidget):
    back_requested = Signal()

    def __init__(self, match_repo: MatchRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = match_repo
        self._matches: list[MatchState] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Match History")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.back_requested)
        header.addWidget(back_btn)
        root.addLayout(header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["ID", "Mode", "Players", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self._table)

        hint = QLabel("Double-click a row to view scores.")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(hint)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        root.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh(self) -> None:
        self._matches = self._repo.list_recent(limit=20)
        self._table.setRowCount(len(self._matches))
        for row, state in enumerate(self._matches):
            mid = str(state.match_id)[:8] + "…"
            players = ", ".join(p.name for p in state.players_in_order)
            status = "finished" if not state.is_active else "in progress"
            for col, text in enumerate([mid, state.mode.value, players, status]):
                self._table.setItem(row, col, QTableWidgetItem(text))

    def _on_double_click(self, index: object) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._matches):
            _MatchDetailDialog(self._matches[row], self).exec()


class _MatchDetailDialog(QDialog):
    def __init__(self, state: MatchState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Match  {str(state.match_id)[:8]}")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        info_box = QGroupBox("Info")
        info_layout = QVBoxLayout(info_box)
        info_layout.addWidget(QLabel(f"Mode: {state.mode.value}"))
        info_layout.addWidget(QLabel(f"Board: {state.board_number}"))
        info_layout.addWidget(QLabel(f"Events recorded: {len(state.history)}"))
        info_layout.addWidget(
            QLabel(f"Status: {'finished' if not state.is_active else 'in progress'}")
        )
        layout.addWidget(info_box)

        scores_box = QGroupBox("Scores")
        scores_layout = QVBoxLayout(scores_box)
        ranked = sorted(
            state.players_in_order,
            key=lambda p: state.score_for(p.id),
            reverse=True,
        )
        for i, player in enumerate(ranked):
            pts = state.score_for(player.id)
            prefix = "1st  " if i == 0 else f"{i + 1}th  "
            lbl = QLabel(f"{prefix}{player.name}:  {pts} pts")
            if i == 0 and not state.is_active:
                lbl.setStyleSheet("font-weight: bold;")
            scores_layout.addWidget(lbl)
        layout.addWidget(scores_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
