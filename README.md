# Baja-Insights

> **The scoreboard doesn't tell the whole story. We show who really won the match.**
>
> *From Baja to the Premier: insight has no borders.*

**[Live demo](https://ambitious-smoke-08207d610.6.azurestaticapps.net)** · **[Demo video]((https://www.youtube.com/watch?v=gwrig1QaKmw))**

Baja-Insights turns a live stream of football match events into explainable, personalised match intelligence: a live MVP race, flank duels measured against role baselines, standout milestones for the players who usually go unnoticed, goal-chain analysis that credits the *invisible assist*, player cards that level up during the match, and an "Ask the match" chat that only answers from real data.

Built for **Inside the Game: Developer Hackathon** (Microsoft × Premier League). All teams, players and venues are fictional and all data is synthetic.

## What you see

- **MVP race.** A live ranking that only announces climbs, and a final top 3 explained with the plays that decided it.
- **Duels.** A bar that shows who is winning between two players, measured against what is expected for each role.
- **Standout milestones.** The full-back with eight recoveries or the midfielder breaking lines, the players a scoreboard never shows.
- **Goal analysis.** Every goal rebuilt as a chain, with credit split among everyone who built it, including the runner who dragged a defender away without touching the ball.
- **Player cards.** Seven attributes that level up during the match, each change with its reason.
- **Ask the match.** A chat that answers only through the engine's query functions and never reveals what happens after the current minute.
- **Fan or analyst, English or Spanish.** Every graphic is written in four versions.
- **The pitch.** All 22 players and the ball, anchored to every event, with set pieces and the change of ends at half-time. The positions are illustrative: the engine never uses them.

The same graphics orders drive three views: the web app, a transparent 1920×1080 overlay for OBS or vMix (`/broadcast`) and a cinema mode for recording (`/cine`).

## How it works

```
┌──────────────────────────┐  events (JSONL stream)  ┌──────────────────────┐
│ Synthetic match generator│ ──────────────────────▶ │ Insight engine       │
│ players decide from the  │                         │ deterministic, no    │
│ play: press, carry, shoot│                         │ LLM: MVP, duels,     │
│ first time, penalties    │                         │ cards, goal chains   │
└────────────┬─────────────┘                         └──────────┬───────────┘
             │ events                                insights + │ query functions (MCP)
             ▼                                                  ▼
┌──────────────────────────┐         ┌──────────────────────────────────────────────┐
│ Positions model          │         │ Agents on Microsoft Foundry, orchestrated    │
│ 22 players and the ball, │         │ with Microsoft Agent Framework:              │
│ 2 frames per second      │         │ Curator → Narrator → Personalization ⇄       │
└────────────┬─────────────┘         │ Verifier → Composer · Ask the match          │
             │                       └──────────────────────┬───────────────────────┘
             │                                              │ graphics orders (JSON)
             ▼                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ WebSocket stream (clock, scoreline, orders) → Web UI or any broadcast engine      │
│ MVP race, duel bar, cards, goal chains, chat · fan / analyst · English / Spanish  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

**Two layers by design.** Detecting and measuring plays is deterministic code, so every number on screen is exact and reproducible. AI agents decide what to show, explain why it matters and adapt it to each viewer and language.
- A Verifier agent checks every claim against the data.
- Code rejects any number that is not in the insight.
- If a text still fails, a template takes its place.

The agents never invent numbers.

## The data

**The demo match, `f091`, is played without a script.** Real Cardón goes 2-0 up and Bahía FC comes back to 2-2 with a penalty in the 78th minute. Nobody chose the comeback, the penalty or the MVP: the generator played the match and the engine found them.

**The generator** (`src/baja_insights/generator/decisions.py`) makes every decision from the play:
- the nearest player presses or wins a loose ball;
- a pressed player lets the ball go before the presser arrives, or waits for him and risks losing it;
- strikers shoot first time when the chance is worth it, and inside the box look for the better-placed team-mate;
- teams counter-attack after winning the ball in their own half;
- fouls in the box are penalties;
- the score changes the rhythm but never the finishing: a shot goes in with the probability of its xG.

Player profiles come from their cards and team styles from `generator/tactics.json`. Free matches are calibrated against Premier League averages (goals, shots, xG, passes, accuracy, fouls, tackles, recoveries), and `tests/test_realism.py` checks 100 of them in CI.

**A second, scripted match, `m001`, plants moments with a known answer**, such as a run that drags a defender and opens the equaliser without touching the ball. The tests use it to prove the engine detects them. The engine and the agents never see the script: they only receive events, exactly as they would from a real data feed.

## Microsoft technologies

| Technology | Where |
| --- | --- |
| **Microsoft Foundry** | Models and agents: Curator, Narrator, Personalization, Verifier and Ask the match |
| **Microsoft Agent Framework** | The multi-agent workflow, with shared match state, retries and template fallbacks |
| **MCP** | Server that exposes the engine's query functions, used by Ask the match |
| **Azure Container Apps** | The WebSocket stream and the chat API |
| **Azure Static Web Apps** | The web UI |
| **GitHub Actions** | CI for contracts, engine, agents and UI; container images; web deployment |
| **GitHub Copilot** | Development |

## Repository layout

| Path | What | Owner |
| --- | --- | --- |
| `contracts/` | JSON Schemas for events, insights, graphics orders, positions, stream and chat: the single source of truth between components | All three |
| `src/baja_insights/generator/` | Match generator: decisions from the play (`decisions.py`), team styles (`tactics.json`), the scripted demo (`simulate.py`, `scripts/`) and an xG model | Member 1 |
| `src/baja_insights/engine/` | Insight engine (`core.py`), scoring formulas (`scoring.py`), tunable parameters (`params.py`) and chat query functions (`tools.py`) | Member 1 |
| `src/baja_insights/positions/` | Illustrative positions of the 22 players and the ball, anchored to every event | Member 1 |
| `src/baja_insights/stream/` | WebSocket stream: one shared clock per match, scoreline and graphics orders; `GET /positions/<match_id>` | Member 1 |
| `agents/` | Foundry agents, Agent Framework workflow, Ask the match and the MCP server ([agents/README.md](agents/README.md)) | Member 2 |
| `web/` | Web app, broadcast overlay and cinema mode ([web/README.md](web/README.md)) | Member 3 |
| `data/` | Generated matches: `f091` (no script, the one published), `m001` (scripted, for the tests) and `free-seed2` | Generated |
| `mocks/` | Hand-written sample data that follows the contracts, so everyone could build in parallel | All three |
| `docs/` | Proposal, formulas, contract change log, deployment and team notes (Spanish) | All three |

## Quick start

### Engine (Python 3.11 or later, no runtime dependencies)

```bash
pip install -e ".[dev]"          # jsonschema + pytest for validation and tests

# 1. Play the demo match: same seed, same match
python -m baja_insights generate --seed 91 --script free --match-id f091 --out data/f091/events.jsonl

# 2. Run the insight engine
python -m baja_insights analyze --events data/f091/events.jsonl --out data/f091/insights.json

# 3. Positions of the 22 players and the ball, 2 frames per second
python -m baja_insights positions --events data/f091/events.jsonl --script free --out data/f091/positions.json

# 4. Replay it live, 60x faster, printing insights as they happen
python -m baja_insights stream --events data/f091/events.jsonl --speed 60

# 5. Ask the match, as the chat agent would
python -m baja_insights ask --events data/f091/events.jsonl get_mvp_ranking '{"at": "90:00", "top": 3}'

# 6. Validate any file against the contracts
python -m baja_insights validate data/f091/events.jsonl data/f091/insights.json data/f091/overlays.json

# 7. How football-like the free matches are, against Premier League ranges
python -m baja_insights realism --seeds 30

# 8. WebSocket stream for the UI (see docs/stream.md)
python -m baja_insights serve --data data --port 8080 --speed 60

# Tests
python -m pytest
```

Any other seed plays a new match: `--seed 7 --script free`. The scripted match is `--seed 1387 --script m001`.

### Web UI (Node 20 or later)

```bash
cd web
npm install
BAJA_MATCH=f091 npm run dev       # http://localhost:5173; in PowerShell: $env:BAJA_MATCH = "f091"
```

The UI replays the match from `data/<BAJA_MATCH>`: events, graphics orders and positions. Without `BAJA_MATCH` it plays `m001`. See [web/README.md](web/README.md) for the broadcast and cinema views and the URL parameters.

### Agents

The graphics orders in `data/*/overlays.json` are already generated. To regenerate them with Foundry, or with templates only and no model calls (`--offline`), see [agents/README.md](agents/README.md).

## Team

Baja-Insights, a team of three.

## License

MIT
