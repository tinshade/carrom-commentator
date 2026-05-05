# Carrom Caster

Live WWE-style audio commentary and automatic score tracking for carrom board games.

Watch a carrom match through your phone's camera, get real-time AI-generated commentary, and track scores for 3-player or 4-player matches — all on your Windows desktop.

## Why Carrom Caster?

Carrom is a classic board game, but scoring live matches is tedious and commentary is non-existent. Carrom Caster bridges that gap:

- **Automatic detection** — classical computer vision (HSV color detection + HoughCircles) identifies coins, tracks them, and detects when they're pocketed
- **Live commentary** — an LLM (local Ollama or cloud API) generates WWE-style color commentary reacting to shots and scores within 1–2 seconds
- **Accurate scoring** — rules engine enforces 3-player FFA or 4-player partner scoring with queen mechanics, fouls, and game-end detection
- **Local first** — runs fully offline (Ollama LLM + pyttsx3 TTS) or upgrade to cloud providers (Anthropic, OpenAI, ElevenLabs) with one config change

## What's Built So Far

- ✅ **Domain + Scoring rules** — frozen dataclasses, pure state transitions, property-based tests
- ✅ **CLI event replayer** — feed JSON event logs, see final scores and match state
- ✅ **Persistence + Player Groups** — SQLite via SQLAlchemy Core; save/load player groups and match history
- ✅ **111 unit tests** — domain, scoring rules, and persistence (Fake + SQLite, parametrized)
- 🔜 **Commentary engine** (Milestone 3) — LLM + TTS with debouncing and priority queuing
- 🔜 **Vision pipeline** (Milestone 4) — coin detection, tracking, event generation from phone camera
- 🔜 **UI** (Milestone 6) — PySide6 desktop app with setup screen, live view, score lookup

## Tech Stack

| Layer        | Tech                                 | Why                                                                 |
| ------------ | ------------------------------------ | ------------------------------------------------------------------- |
| **Language** | Python 3.11+                         | Best CV/TTS/LLM ecosystems, single language                         |
| **CV**       | OpenCV (classical)                   | HSV + HoughCircles for coin detection, no ML training needed        |
| **Tracking** | scipy.optimize.linear_sum_assignment | Hungarian algorithm for centroid matching                           |
| **Storage**  | SQLite                               | Single file, zero config, perfect for player groups + match history |
| **LLM**      | Pluggable (Ollama/Anthropic/OpenAI)  | Local first, cloud upgrade via config                               |
| **TTS**      | Pluggable (pyttsx3/ElevenLabs)       | Offline SAPI on Windows or cloud voice                              |
| **UI**       | PySide6                              | Qt for Python, responsive, cross-platform                           |
| **Config**   | pydantic-settings + YAML             | Typed, validated, environment-aware                                 |
| **Testing**  | pytest + hypothesis                  | Fast unit tests + property-based invariants                         |
| **Linting**  | ruff                                 | Single tool for check + format                                      |

## Quick Start (Development)

### Prerequisites

- **Windows 11** (or Windows 10)
- **Python 3.11+** (tested on 3.12)
- **uv** package manager — install via `pip install uv`
- **Phone** with IP Webcam app (Android: free; iOS: EpocCam/Iriun ~$3–5)

### Clone & Setup

```powershell
cd <your project folder>\carrom-caster

# Install dependencies (creates .venv automatically)
uv sync

# Run all unit tests (should see 111 passed)
uv run pytest tests/unit/ -v

# Test the CLI on a sample match
uv run python -m carrom_caster.scripts.score_from_events scripts/sample_events_3p.json
```

### Running the App

> **Note:** Full app launch (`python -m carrom_caster`) requires Milestone 5 (vision pipeline wired). Currently only the scoring CLI is runnable.

**Score a match from a JSON event log (Milestone 1):**

```powershell
uv run python -m carrom_caster.scripts.score_from_events path\to\events.json
```

**Offline mode** (default) — no API keys needed. Uses Ollama (local LLM) + pyttsx3 (Windows TTS).

**Cloud providers** — uncomment keys in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

Then set `llm_provider` / `tts_provider` in `config/default.yaml`.

### Expected CLI Output (3P sample)

```
----------------------------------------
  Match  : 11111111-0000-0000-0000-000000000001
  Mode   : 3P_FFA
  Status : in progress
  Board  : 1

  Scores:
    Charlie                 4 pts
    Alice                   1 pts
    Bob                     1 pts

  Queen  : covered
  White on board : 7
  Black on board : 7
  Events processed: 10
----------------------------------------
```

### Run Sample 4P Match

```bash
uv run python -m carrom_caster.scripts.score_from_events scripts/sample_events_4p.json
```

## Project Structure

```
carrom-caster/
├── pyproject.toml          # uv project config, dependencies
├── .env                    # secrets (gitignored) — API keys
├── config/
│   ├── default.yaml        # board dims, HSV ranges, LLM/TTS/DB settings
│   └── prompts/wwe_commentary.txt
├── src/carrom_caster/
│   ├── domain/             # frozen dataclasses (Coin, Event, Player, MatchState)
│   ├── scoring/            # rules engines (3P FFA, 4P partners) + Scorer
│   ├── persistence/        # ✅ schema.py (SQLAlchemy Core tables) + repositories.py
│   ├── scripts/
│   │   └── score_from_events.py  # CLI: JSON → score
│   ├── vision/             # [future] detector, tracker, event_detector
│   ├── commentary/         # [future] llm, tts, engine
│   ├── ui/                 # [future] PySide6 screens
│   └── utils/
└── tests/
    ├── unit/               # 111 tests (domain + scoring + persistence)
    └── integration/        # [future] video clips
```

## Development Workflow

### Running Tests

```bash
# Fast unit tests (run on every save)
uv run pytest tests/unit/ -v

# Specific test file
uv run pytest tests/unit/scoring/test_three_player.py -v

# Single test
uv run pytest tests/unit/scoring/test_three_player.py::TestQueenMechanics::test_queen_covered_awards_bonus -v

# With coverage
uv run pytest tests/unit/ --cov=src/carrom_caster
```

### Linting & Type Checking

```bash
# Check code style + unused imports
uv run ruff check src/ tests/

# Auto-fix style issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/

# Type check (strict on domain + scoring)
uv run mypy src/carrom_caster/domain src/carrom_caster/scoring
```

### Creating a New Event JSON for Testing

```json
{
  "match_id": "your-uuid-here",
  "mode": "3P_FFA",
  "players": [
    { "id": "uuid1", "name": "Alice" },
    { "id": "uuid2", "name": "Bob" },
    { "id": "uuid3", "name": "Charlie" }
  ],
  "teams": [],
  "events": [
    {
      "type": "COIN_POCKETED",
      "timestamp": "2024-01-01T10:00:01",
      "frame_index": 30,
      "payload": {
        "color": "white",
        "coin_id": "w1",
        "pocket_corner": "top_left"
      }
    },
    {
      "type": "TURN_ENDED",
      "timestamp": "2024-01-01T10:00:03",
      "frame_index": 90,
      "payload": {}
    }
  ]
}
```

Save as `test_match.json` then run:

```bash
uv run python -m carrom_caster.scripts.score_from_events test_match.json
```

## Architecture & Design

### Core Principles

1. **Linear Pipeline** — each stage (source → detector → tracker → events → scorer → UI) is independently testable
2. **Immutable Domain** — frozen dataclasses, state transitions return new instances
3. **Pluggable Providers** — LLM, TTS, video source all behind `typing.Protocol`
4. **Composition Root** — `app.py` (not yet written) is the only place adapters are wired
5. **No Global State** — dependency injection everywhere; tests inject fakes

### MatchState Snapshot

Every match is represented as an immutable snapshot:

```python
@dataclass(frozen=True)
class MatchState:
    match_id: UUID
    mode: MatchMode                          # 3P_FFA or 4P_PARTNERS
    players_in_order: tuple[Player, ...]     # clockwise from left
    teams: tuple[Team, ...]                  # empty for 3P
    current_turn_index: int
    player_scores: tuple[PlayerScore, ...]
    queen_state: QueenState                  # ON_BOARD, POCKETED_UNCOVERED, COVERED
    queen_pocketed_by_index: int | None
    white_coins_on_board: int
    black_coins_on_board: int
    history: tuple[GameEvent, ...]           # full event log
    board_number: int
    boards_won: tuple[int, int]              # for 4P multi-board tracking
    is_active: bool
```

Apply events via `Scorer.apply(state, event) → new_state`. Pure function, no side effects.

### Scoring Rules Variants

**3-Player FFA (Indian Standard)**

- 9 white + 9 black coins, 1 queen
- Any pocketed coin: +1 to current player
- Queen: +3, must be covered (pocket any coin same turn) or returns
- Striker pocketed: -1 to current player
- Game ends: all coins cleared + queen covered

**4-Player Partners (2v2)**

- teams[0] plays white (players 0, 2); teams[1] plays black (players 1, 3)
- Correct color: +1
- Wrong color (foul): that coin returns + one of your color returns, no points
- Queen: +3, must be covered with your team's color
- Board ends: team clears all their color coins
- Match ends: first team to win `boards_to_win` boards (default 2, best-of-3)

Both rules behind `ScoringRules` Protocol for easy extension.

## Build Milestones

Each milestone is shippable on its own.

1. ✅ **Domain + Scoring** — JSON event log → score (CLI)
2. ✅ **Persistence + Player Groups** — SQLite via SQLAlchemy Core, save/load groups + match history
3. 🔜 **Commentary Engine** — LLM + TTS, debouncing
4. 🔜 **Vision Pipeline** — phone camera → events
5. 🔜 **Wire Headless** — full pipeline from camera to score + audio
6. 🔜 **UI** — PySide6 desktop app
7. 🔜 **Polish** — better voices, settings UI, installer

## Configuration

### `.env` (Secrets, gitignored)

```bash
# Optional: only if using cloud LLM/TTS
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

### `config/default.yaml` (Committed, tune-able)

```yaml
scoring:
  rules_variant: indian_standard
  boards_to_win: 2

vision:
  colors:
    white: { lower: [0, 0, 180], upper: [179, 60, 255] }
    black: { lower: [0, 0, 0], upper: [179, 255, 60] }
    queen: { lower: [0, 120, 80], upper: [10, 255, 255] }

commentary:
  llm_provider: ollama
  ollama_model: llama3.2:3b
  tts_provider: pyttsx3
  max_tokens: 60

camera:
  url: "http://192.168.1.100:8080/video" # IP Webcam default
```

## Contributing

### Before You Code

- Check CLAUDE.md for conventions + architecture details
- Confirm which milestone is in progress (ask if unsure)
- File size limit: keep modules < 250 lines
- Type hints on public functions
- Fakes over mocks for testing

### Common Tasks

**Add a new scoring rule variant:**

1. Create `src/carrom_caster/scoring/house_rules.py`
2. Implement `ScoringRules` protocol
3. Add unit tests in `tests/unit/scoring/test_house_rules.py`
4. Update `config/default.yaml` and `config.py`

**Test a change:**

```bash
uv run pytest tests/unit/scoring/ -v
```

**Format before commit:**

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

## Troubleshooting

### Tests fail with import errors

```bash
# Sync dependencies
uv sync

# Re-run
uv run pytest tests/unit/
```

### "No module named carrom_caster"

```bash
# Make sure you're in the project root (carrom-caster/)
cd D:\Projects\Personal\CarromCommentor\carrom-caster
uv run pytest tests/unit/
```

### CLI shows "File not found" for sample_events_3p.json

```bash
uv run python -m carrom_caster.scripts.score_from_events scripts/sample_events_3p.json
```

## Next Steps

- **Run tests** to validate the scoring rules
- **Explore the code** — start with `src/carrom_caster/domain/match.py` to understand MatchState

## License

Educational project. Build for fun, learning, and carrom game enthusiasts.

---
