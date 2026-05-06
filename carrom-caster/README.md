# Carrom Caster

Live WWE-style audio commentary and automatic score tracking for carrom board games.

Watch a carrom match through your phone's camera, get real-time AI-generated commentary, and track scores for 3-player or 4-player matches — all on your Windows desktop.

## Why Carrom Caster?

Carrom is a classic board game, but scoring live matches is tedious and commentary is non-existent. Carrom Caster bridges that gap:

- **Automatic detection** — classical computer vision (HSV color detection + HoughCircles) identifies coins, tracks them, and detects when they're pocketed
- **Live commentary** — an LLM (local Ollama or cloud API) generates WWE-style color commentary reacting to shots and scores within 1–2 seconds
- **Accurate scoring** — rules engine enforces 3-player FFA or 4-player partner scoring with queen mechanics, fouls, and game-end detection
- **Local first** — runs fully offline (Ollama LLM + pyttsx3 TTS) or upgrade to cloud providers (Anthropic, OpenAI, ElevenLabs) with one config change

## What's Built

- ✅ **Domain + Scoring rules** — frozen dataclasses, pure state transitions, property-based tests
- ✅ **CLI event replayer** — feed JSON event logs, see final scores and match state
- ✅ **Persistence + Player Groups** — SQLite via SQLAlchemy Core; save/load player groups and match history
- ✅ **Commentary engine** — LLM + TTS with debouncing; pluggable providers (Ollama, Anthropic, OpenAI, ElevenLabs)
- ✅ **Vision pipeline** — HSV coin detection, Hungarian-algorithm tracker, state-machine event detector; tested on recorded clips
- ✅ **Full headless pipeline** — phone camera → vision → scorer + commentary → SQLite, all wired in `app.py`
- ✅ **PySide6 desktop UI** — setup screen, live match screen, score lookup screen
- ✅ **165 unit tests** — domain, scoring, persistence, commentary, vision (Fake + SQLite, property-based)

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

# Install all dependencies including UI, vision, commentary
uv sync --extra vision --extra commentary --extra ui

# Run all unit tests (should see 165 passed)
uv run pytest tests/unit/ -v
```

### Running the App

**Desktop UI (default):**

```powershell
uv run python -m carrom_caster
```

Opens the setup screen. Enter player names, set the IP Webcam URL, pick providers, and click **Start Match**.

**Headless CLI (no UI):**

```powershell
uv run python -m carrom_caster --headless --players Alice Bob Charlie
uv run python -m carrom_caster --headless --players Alice Bob Charlie Dave --mode 4P_PARTNERS --dry-run
```

**Score a match from a JSON event log:**

```powershell
uv run python -m carrom_caster.scripts.score_from_events scripts/sample_events_3p.json
```

**Offline mode** (default) — no API keys needed. Uses Ollama (local LLM) + pyttsx3 (Windows TTS).

**Cloud providers** — add keys to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

Then set `llm_provider` / `tts_provider` in `config/default.yaml`, or select them in the UI setup screen.

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

## Project Structure

```
carrom-caster/
├── pyproject.toml          # uv project config, dependencies
├── .env                    # secrets (gitignored) — API keys
├── config/
│   ├── default.yaml        # board dims, HSV ranges, LLM/TTS/DB settings
│   └── prompts/wwe_commentary.txt
├── src/carrom_caster/
│   ├── app.py              # composition root — wires all pipeline stages
│   ├── config.py           # pydantic-settings config + secrets
│   ├── domain/             # frozen dataclasses (Coin, Event, Player, MatchState)
│   ├── scoring/            # rules engines (3P FFA, 4P partners) + Scorer
│   ├── persistence/        # schema.py (SQLAlchemy Core) + repositories
│   ├── commentary/         # LLM clients, TTS engines, CommentaryEngine
│   ├── vision/             # detector, tracker, calibration, event state machine
│   ├── ui/
│   │   ├── main_window.py          # QMainWindow, screen navigation
│   │   ├── pipeline_thread.py      # QThread wrapping App
│   │   └── screens/
│   │       ├── setup_screen.py     # player entry, group management, providers
│   │       ├── match_screen.py     # live scores, turn, queen state, commentary feed
│   │       └── history_screen.py  # recent matches, score detail dialog
│   ├── scripts/
│   │   └── score_from_events.py   # CLI: JSON event log → score
│   └── utils/
└── tests/
    ├── unit/               # 165 tests (domain, scoring, persistence, commentary, vision)
    └── integration/        # video clip fixtures + pipeline smoke tests
```

## Development Workflow

### Running Tests

```powershell
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

```powershell
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

```powershell
uv run python -m carrom_caster.scripts.score_from_events test_match.json
```

## Architecture & Design

### Core Principles

1. **Linear Pipeline** — each stage (source → detector → tracker → events → scorer → UI) is independently testable
2. **Immutable Domain** — frozen dataclasses, state transitions return new instances
3. **Pluggable Providers** — LLM, TTS, video source all behind `typing.Protocol`
4. **Composition Root** — `app.py` is the only place adapters are wired; UI and headless share the same `App` class
5. **No Global State** — dependency injection everywhere; tests inject fakes

### Pipeline

```
VideoSource → Calibration → Detector → Tracker → EventDetector ─┬─► Scorer → Repository (SQLite)
                                                                 │
                                                                 └─► CommentaryEngine → TTS → Speakers
                                                                                  ▲
                                                                         PySide6 UI (reads Repository + signals)
```

The UI wraps `App` in a `PipelineThread` (`QThread`). Game events cross the thread boundary via Qt signals — `state_updated(MatchState, commentary)` fires on the main thread after every event.

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
3. ✅ **Commentary Engine** — LLM + TTS, debouncing, pluggable providers
4. ✅ **Vision Pipeline** — phone camera → events; tested on recorded clips
5. ✅ **Wire Headless** — full pipeline from camera to score + audio, persisted
6. ✅ **UI** — PySide6 desktop app: setup screen, live match screen, score lookup
7. 🔜 **Polish** — ElevenLabs voices, settings UI, board calibration wizard, Windows installer

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

```powershell
uv run pytest tests/unit/scoring/ -v
```

**Format before commit:**

```powershell
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

## Troubleshooting

### Tests fail with import errors

```powershell
uv sync --extra vision --extra commentary --extra ui
uv run pytest tests/unit/
```

### "No module named carrom_caster"

```powershell
# Make sure you're in the project root (carrom-caster/)
cd D:\Projects\Personal\CarromCommentor\carrom-caster
uv run pytest tests/unit/
```

### UI won't open — "PySide6 not installed"

```powershell
uv sync --extra ui
uv run python -m carrom_caster
```

### Camera stream won't connect

- Confirm phone and PC are on same Wi-Fi network
- Open IP Webcam on phone, note the URL shown (e.g. `http://192.168.1.x:8080/video`)
- Paste it into the Camera URL field on the setup screen
- Test in a browser first — you should see the MJPEG stream

### CLI shows "File not found" for sample_events_3p.json

```powershell
uv run python -m carrom_caster.scripts.score_from_events scripts/sample_events_3p.json
```

## License

Educational project. Build for fun, learning, and carrom game enthusiasts.

---
