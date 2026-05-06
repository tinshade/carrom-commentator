from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from carrom_caster.domain.match import MatchState, QueenState

_QUEEN_LABELS = {
    QueenState.ON_BOARD: "Queen: on board",
    QueenState.POCKETED_UNCOVERED: "Queen: needs cover!",
    QueenState.COVERED: "Queen: covered (+3)",
}

_QUEEN_COLORS = {
    QueenState.ON_BOARD: "",
    QueenState.POCKETED_UNCOVERED: "color: #c00; font-weight: bold;",
    QueenState.COVERED: "color: #090; font-weight: bold;",
}


class MatchScreen(QWidget):
    end_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # ── Header ──────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        self._status_label = QLabel("Match in progress...")
        self._status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(self._status_label)
        header.addStretch()
        end_btn = QPushButton("End Match")
        end_btn.clicked.connect(self.end_requested)
        header.addWidget(end_btn)
        root.addLayout(header)

        # ── Board status ────────────────────────────────────────────────────────
        status_box = QGroupBox("Board Status")
        status_layout = QHBoxLayout(status_box)
        self._turn_label = QLabel("Turn: —")
        self._turn_label.setStyleSheet("font-size: 13px;")
        self._queen_label = QLabel("Queen: on board")
        self._coins_label = QLabel("White: 9  |  Black: 9")
        status_layout.addWidget(self._turn_label)
        status_layout.addStretch()
        status_layout.addWidget(self._queen_label)
        status_layout.addStretch()
        status_layout.addWidget(self._coins_label)
        root.addWidget(status_box)

        # ── Score table ─────────────────────────────────────────────────────────
        score_box = QGroupBox("Scores")
        score_layout = QVBoxLayout(score_box)
        self._score_table = QTableWidget(0, 2)
        self._score_table.setHorizontalHeaderLabels(["Player", "Points"])
        self._score_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._score_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._score_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._score_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._score_table.verticalHeader().setVisible(False)
        self._score_table.setMaximumHeight(150)
        score_layout.addWidget(self._score_table)
        root.addWidget(score_box)

        # ── Commentary feed ──────────────────────────────────────────────────────
        comm_box = QGroupBox("Commentary")
        comm_layout = QVBoxLayout(comm_box)
        self._commentary_feed = QTextEdit()
        self._commentary_feed.setReadOnly(True)
        self._commentary_feed.setMinimumHeight(220)
        self._commentary_feed.setPlaceholderText("Commentary will appear here...")
        comm_layout.addWidget(self._commentary_feed)
        root.addWidget(comm_box, stretch=1)

    @Slot(object, object)
    def on_state_updated(self, state: MatchState, commentary: str | None) -> None:
        self._refresh(state)
        if commentary:
            self._commentary_feed.append(commentary)
            sb = self._commentary_feed.verticalScrollBar()
            sb.setValue(sb.maximum())

    @Slot(object)
    def on_match_finished(self, state: MatchState) -> None:
        self._refresh(state)
        self._status_label.setText("Match finished!")
        winner = max(state.players_in_order, key=lambda p: state.score_for(p.id))
        self._commentary_feed.append(f"\n--- {winner.name} wins! ---")

    def reset(self) -> None:
        self._status_label.setText("Match in progress...")
        self._commentary_feed.clear()
        self._score_table.setRowCount(0)
        self._turn_label.setText("Turn: —")
        self._queen_label.setText("Queen: on board")
        self._queen_label.setStyleSheet("")
        self._coins_label.setText("White: 9  |  Black: 9")

    def _refresh(self, state: MatchState) -> None:
        self._turn_label.setText(f"Turn: {state.current_player.name}")

        self._queen_label.setText(_QUEEN_LABELS[state.queen_state])
        self._queen_label.setStyleSheet(_QUEEN_COLORS[state.queen_state])

        self._coins_label.setText(
            f"White: {state.white_coins_on_board}  |  Black: {state.black_coins_on_board}"
        )

        ranked = sorted(
            state.players_in_order,
            key=lambda p: state.score_for(p.id),
            reverse=True,
        )
        self._score_table.setRowCount(len(ranked))
        current_id = state.current_player.id
        for row, player in enumerate(ranked):
            pts = state.score_for(player.id)
            name_text = f"▶ {player.name}" if player.id == current_id else player.name
            name_item = QTableWidgetItem(name_text)
            pts_item = QTableWidgetItem(str(pts))
            pts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._score_table.setItem(row, 0, name_item)
            self._score_table.setItem(row, 1, pts_item)
