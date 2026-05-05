"""
Entry point: python -m carrom_caster

Wires all components from config and runs the headless pipeline.
Requires vision + commentary extras:
    uv sync --extra vision --extra commentary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa

from carrom_caster.app import App
from carrom_caster.commentary.engine import CommentaryEngine
from carrom_caster.commentary.llm import AnthropicClient, OllamaClient
from carrom_caster.commentary.prompts import load_system_prompt
from carrom_caster.commentary.tts import FakeTTSEngine, Pyttsx3Engine
from carrom_caster.config import AppConfig, Secrets
from carrom_caster.domain.match import MatchMode
from carrom_caster.domain.player import Player, Team
from carrom_caster.persistence.repositories import SqliteMatchRepository
from carrom_caster.scoring.four_player import FourPlayerRules
from carrom_caster.scoring.scorer import Scorer
from carrom_caster.scoring.three_player import ThreePlayerRules
from carrom_caster.vision.calibration import IdentityCalibration, compute_homography
from carrom_caster.vision.detector import DetectorConfig, HsvDetector, HsvRange
from carrom_caster.vision.events import EventDetector
from carrom_caster.vision.source import PhoneCameraSource
from carrom_caster.vision.tracker import CoinTracker


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Carrom Caster — live commentary + scoring")
    p.add_argument("--players", nargs="+", default=["Player 1", "Player 2", "Player 3"])
    p.add_argument("--mode", choices=["3P_FFA", "4P_PARTNERS"], default="3P_FFA")
    p.add_argument("--config", default="config/default.yaml")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commentary instead of speaking (no pyttsx3 needed)",
    )
    return p.parse_args()


def _make_players(names: list[str]) -> list[Player]:
    return [Player(id=uuid4(), name=n) for n in names]


def _make_teams(players: list[Player]) -> list[Team]:
    return [
        Team(id="team_a", name="Team A", players=(players[0], players[2])),
        Team(id="team_b", name="Team B", players=(players[1], players[3])),
    ]


def _make_detector_config(cfg: AppConfig) -> DetectorConfig:
    c = cfg.vision.colors
    return DetectorConfig(
        white=HsvRange(lower=tuple(c.white.lower), upper=tuple(c.white.upper)),  # type: ignore[arg-type]
        black=HsvRange(lower=tuple(c.black.lower), upper=tuple(c.black.upper)),  # type: ignore[arg-type]
        queen=HsvRange(lower=tuple(c.queen.lower), upper=tuple(c.queen.upper)),  # type: ignore[arg-type]
    )


def _print_result(state) -> None:
    sep = "-" * 40
    print(f"\n{sep}")
    print(f"  Match  : {state.match_id}")
    print(f"  Mode   : {state.mode.value}")
    print(f"  Status : {'finished' if not state.is_active else 'in progress'}")
    print("\n  Scores:")
    ranked = sorted(
        [(state.score_for(p.id), p.name) for p in state.players_in_order],
        key=lambda x: -x[0],
    )
    for pts, name in ranked:
        marker = "  <- WINNER" if pts == ranked[0][0] and not state.is_active else ""
        print(f"    {name:<20} {pts:>4} pts{marker}")
    print(f"\n  Events processed: {len(state.history)}")
    print(f"{sep}\n")


def main() -> int:
    args = _parse_args()

    try:
        cfg = AppConfig.load(args.config)
    except FileNotFoundError:
        print(f"Config not found: {args.config}", file=sys.stderr)
        return 1

    secrets = Secrets()  # type: ignore[call-arg]

    # ── Vision ──────────────────────────────────────────────────────────────
    vc = cfg.vision
    source = PhoneCameraSource(cfg.camera.url)

    if vc.calibration_corners:
        corners = [tuple(c) for c in vc.calibration_corners]
        calibration = compute_homography(corners)  # type: ignore[arg-type]
    else:
        calibration = IdentityCalibration(800).as_result()

    detector = HsvDetector(_make_detector_config(cfg))
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

    # ── Scoring ─────────────────────────────────────────────────────────────
    mode = MatchMode(args.mode)
    rules = FourPlayerRules() if mode == MatchMode.FOUR_PLAYER_PARTNERS else ThreePlayerRules()
    scorer = Scorer(rules)

    # ── Commentary ───────────────────────────────────────────────────────────
    cc = cfg.commentary
    if args.dry_run:
        tts: object = FakeTTSEngine()
    else:
        tts = Pyttsx3Engine()

    if cc.llm_provider == "anthropic":
        llm = AnthropicClient(api_key=secrets.anthropic_api_key)
    else:
        llm = OllamaClient(model=cc.ollama_model)

    system_prompt = load_system_prompt(cc.prompt_path)
    commentary = CommentaryEngine(
        llm=llm, tts=tts, system_prompt=system_prompt,  # type: ignore[arg-type]
        max_tokens=cc.max_tokens, debounce_ms=cc.debounce_ms,
    )

    # ── Persistence ──────────────────────────────────────────────────────────
    db_path = Path(cfg.persistence.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    match_repo = SqliteMatchRepository(engine)

    # ── Players ──────────────────────────────────────────────────────────────
    players = _make_players(args.players)
    teams = _make_teams(players) if mode == MatchMode.FOUR_PLAYER_PARTNERS else None

    # ── Run ──────────────────────────────────────────────────────────────────
    app = App(
        source=source,
        calibration=calibration,
        detector=detector,
        tracker=tracker,
        event_detector=event_det,
        scorer=scorer,
        commentary=commentary,
        match_repo=match_repo,
    )

    state = app.run(players, teams)
    _print_result(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
