from __future__ import annotations

from pathlib import Path

from carrom_caster.domain.event import EventType, GameEvent
from carrom_caster.domain.match import MatchMode, MatchState

_DESCRIPTIONS: dict[EventType, str] = {
    EventType.COIN_POCKETED: "pocketed a {color} coin ({pocket_corner} pocket)",
    EventType.QUEEN_POCKETED: "pocketed the QUEEN ({pocket_corner} pocket)",
    EventType.QUEEN_COVERED: "covered the queen — 3 bonus points!",
    EventType.STRIKER_POCKETED: "FOULED — striker went in!",
    EventType.MATCH_ENDED: "won the match!",
    EventType.TURN_ENDED: "ended their turn",
    EventType.STRIKE_TAKEN: "took a strike",
}


def load_system_prompt(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def build_user_prompt(event: GameEvent, state: MatchState) -> str:
    player = state.current_player
    template = _DESCRIPTIONS.get(event.type, event.type.value)
    try:
        desc = template.format(**event.payload)
    except KeyError:
        desc = template

    scores = ", ".join(
        f"{p.name}: {state.score_for(p.id)} pts" for p in state.players_in_order
    )
    lines = [
        f"Event: {player.name} {desc}",
        f"Score — {scores}",
        f"Coins left: {state.white_coins_on_board} white, {state.black_coins_on_board} black."
        f" Queen: {state.queen_state.value}.",
    ]
    if state.mode == MatchMode.FOUR_PLAYER_PARTNERS and state.teams:
        lines.append(f"Boards won: {state.boards_won[0]}-{state.boards_won[1]}.")
    return "\n".join(lines)
