"""
Application configuration loaded from config/default.yaml + .env secrets.

Usage:
    cfg = AppConfig.load()
    key = cfg.secrets.anthropic_api_key
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── nested config models ───────────────────────────────────────────────────────

class HsvRangeConfig(BaseModel):
    lower: list[int]
    upper: list[int]


class ColorsConfig(BaseModel):
    white: HsvRangeConfig
    black: HsvRangeConfig
    queen: HsvRangeConfig


class VisionConfig(BaseModel):
    colors: ColorsConfig
    pockets: dict[str, list[float]]
    pocket_radius: float = 0.06
    disappear_frames: int = 5
    max_centroid_distance: float = 0.05
    strike_velocity_threshold: float = 0.02
    settle_velocity_threshold: float = 0.002
    settle_frames: int = 10
    # Optional: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] board corners in pixels
    calibration_corners: list[list[int]] | None = None


class ScoringConfig(BaseModel):
    rules_variant: str = "indian_standard"
    queen_points: int = 3
    foul_points: int = -1
    initial_white_coins: int = 9
    initial_black_coins: int = 9
    queen_cover_same_turn: bool = True
    boards_to_win: int = 2


class CommentaryConfig(BaseModel):
    llm_provider: str = "ollama"
    ollama_model: str = "llama3.2:3b"
    tts_provider: str = "pyttsx3"
    max_tokens: int = 60
    prompt_path: str = "config/prompts/wwe_commentary.txt"
    debounce_ms: int = 500


class CameraConfig(BaseModel):
    url: str = "http://192.168.1.100:8080/video"
    fps_target: int = 30
    resolution: list[int] = [1280, 720]


class PersistenceConfig(BaseModel):
    db_path: str = "data/carrom.db"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"


class AppConfig(BaseModel):
    scoring: ScoringConfig = ScoringConfig()
    vision: VisionConfig
    commentary: CommentaryConfig = CommentaryConfig()
    camera: CameraConfig = CameraConfig()
    persistence: PersistenceConfig = PersistenceConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def load(cls, path: str | Path = "config/default.yaml") -> AppConfig:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(**data)


# ── secrets (loaded from .env) ─────────────────────────────────────────────────

class Secrets(BaseSettings):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
