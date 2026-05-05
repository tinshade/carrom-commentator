"""
CLI: read a JSON event log and print the final score.

Usage:
    uv run python -m carrom_caster.scripts.score_from_events <events.json>

JSON format:
{
  "match_id": "optional-uuid-string",
  "mode": "3P_FFA" | "4P_PARTNERS",
  "players": [{"id": "uuid", "name": "Alice"}, ...],
  "teams": [                          # only for 4P_PARTNERS
    {"id": "team_a", "name": "Team A", "player_indices": [0, 2]},
    {"id": "team_b", "name": "Team B", "player_indices": [1, 3]}
  ],
  "events": [
    {
      "type": "COIN_POCKETED",
      "timestamp": "2024-01-01T10:00:00",
      "frame_index": 100,
      "payload": {"coin_id": "w1", "color": "white", "pocket_corner": "top_left"}
    },
    ...
  ]
}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchMode, MatchState
from carrom_caster.domain.player import Player, Team
from carrom_caster.scoring.four_player import FourPlayerRules
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules


def _parse_player(raw: dict) -> Player:
    return Player(id=UUID(raw["id"]), name=raw["name"])


def _parse_team(raw: dict, players: list[Player]) -> Team:
    team_players = tuple(players[i] for i in raw["player_indices"])
    return Team(id=raw["id"], name=raw["name"], players=team_players)


def _parse_event(raw: dict) -> GameEvent:
    return GameEvent(
        type=EventType[raw["type"]],
        timestamp=datetime.fromisoformat(raw["timestamp"]),
        frame_index=int(raw.get("frame_index", 0)),
        payload=raw.get("payload", {}),
    )


def _load(path: Path) -> tuple[Scorer, list[Player], list[Team], list[GameEvent], UUID]:
    data = json.loads(path.read_text(encoding="utf-8"))
    mode = MatchMode(data["mode"])
    players = [_parse_player(p) for p in data["players"]]
    teams = [_parse_team(t, players) for t in data.get("teams", [])]
    events = [_parse_event(e) for e in data["events"]]
    match_id = UUID(data["match_id"]) if "match_id" in data else uuid4()

    if mode == MatchMode.THREE_PLAYER_FFA:
        rules = ThreePlayerRules()
    else:
        rules = FourPlayerRules()

    return Scorer(rules), players, teams, events, match_id


def _print_result(state: MatchState) -> None:
    sep = "-" * 40
    print(f"\n{sep}")
    print(f"  Match  : {state.match_id}")
    print(f"  Mode   : {state.mode.value}")
    print(f"  Status : {'finished' if not state.is_active else 'in progress'}")
    print(f"  Board  : {state.board_number}")
    if state.mode == MatchMode.FOUR_PLAYER_PARTNERS:
        print(f"  Boards won : {state.boards_won[0]}-{state.boards_won[1]}")
    print("\n  Scores:")
    ranked = sorted(
        [(state.score_for(p.id), p.name) for p in state.players_in_order],
        key=lambda x: -x[0],
    )
    for pts, name in ranked:
        marker = "  <- WINNER" if pts == ranked[0][0] and not state.is_active else ""
        print(f"    {name:<20} {pts:>4} pts{marker}")
    print(f"\n  Queen  : {state.queen_state.value}")
    print(f"  White on board : {state.white_coins_on_board}")
    print(f"  Black on board : {state.black_coins_on_board}")
    print(f"  Events processed: {len(state.history)}")
    print(f"{sep}\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: score-from-events <events.json>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    try:
        scorer, players, teams, events, match_id = _load(path)
    except (KeyError, ValueError) as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 1

    state = scorer.initial_state(match_id, players, teams)
    state = scorer.apply_all(state, events)
    _print_result(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

