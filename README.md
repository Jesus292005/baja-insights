# Baja-Insights

> **The scoreboard doesn't tell the whole story. We show who really won the match.**
>
> *From Baja to the Premier: insight has no borders.*

Baja-Insights turns a live stream of football match events into explainable, personalised match intelligence: a live MVP race, flank duels measured against role baselines, standout milestones for the players who usually go unnoticed, goal-chain analysis that credits the *invisible assist*, player cards that level up during the match, and an "Ask the match" chat that only answers from real data.

Built for **Inside the Game: Developer Hackathon** (Microsoft × Premier League). All teams, players and venues are fictional and all data is synthetic.

## How it works

```
┌─────────────────────┐   events (JSONL stream)   ┌─────────────────────┐
│ Synthetic generator │ ────────────────────────▶ │ Insight engine      │
│ scripted beats +    │                           │ deterministic, no   │
│ seeded simulation   │                           │ LLM: scoring, MVP,  │
└─────────────────────┘                           │ duels, cards, chain │
                                                  └──────────┬──────────┘
                                         insights + query     │
                                         functions (MCP)      ▼
                              ┌──────────────────────────────────────────┐
                              │ Agents on Microsoft Foundry,             │
                              │ orchestrated with Microsoft Agent        │
                              │ Framework: Curator · Narrator ·          │
                              │ Personalisation · Ask the match          │
                              └────────────────────┬─────────────────────┘
                                                   │ graphics orders (JSON)
                                                   ▼
                              ┌──────────────────────────────────────────┐
                              │ Web UI / any broadcast graphics engine   │
                              │ cards, MVP race, duel bar, chat,         │
                              │ fan vs analyst mode, ES / EN             │
                              └──────────────────────────────────────────┘
```

**Two layers by design.** Detecting and measuring plays is deterministic code, so every number on screen is exact and reproducible. AI agents decide what to show, explain why it matters and adapt it to each viewer and language. They never invent numbers.

## Repository layout

| Path | What | Owner |
| --- | --- | --- |
| `contracts/` | JSON Schemas for events, insights and graphics orders, the single source of truth between components | All three |
| `src/baja_insights/generator/` | Synthetic match generator: scripted story beats plus seeded stochastic filler and an xG model | Member 1 |
| `src/baja_insights/engine/` | Insight engine (`core.py`), scoring formulas (`scoring.py`), tunable parameters (`params.py`) and chat query functions (`tools.py`) | Member 1 |
| `agents/` | Foundry agents and orchestration | Member 2 |
| `web/` | User interface | Member 3 |
| `mocks/` | Hand-written sample data that follows the contracts, so everyone can build in parallel | All three |
| `data/` | Real output of the generator and engine | Generated |
| `docs/` | Proposal, formulas and contract change log (Spanish) | All three |

## Quick start

Requires Python 3.11 or later. The core has no runtime dependencies.

```bash
pip install -e ".[dev]"          # jsonschema + pytest for validation and tests

# 1. Generate the demo match (same seed, same match)
python -m baja_insights generate --seed 44 --script m001 --out data/m001/events.jsonl

# 2. Run the insight engine
python -m baja_insights analyze --events data/m001/events.jsonl --out data/m001/insights.json

# 3. Replay it live, 60x faster, printing insights as they happen
python -m baja_insights stream --events data/m001/events.jsonl --speed 60

# 4. Ask the match, as the chat agent would
python -m baja_insights ask --events data/m001/events.jsonl get_mvp_ranking '{"at": "35:00", "top": 3}'

# 5. Validate any file against the contracts
python -m baja_insights validate data/m001/events.jsonl data/m001/insights.json mocks/overlays_sample.json

# 6. WebSocket stream for the UI: clock, scoreline and graphics orders (see docs/stream.md)
python -m baja_insights serve --data data --port 8080 --speed 60

# Tests
python -m pytest
```

An unscripted match (`--script free`) uses the same simulator with goals sampled from xG, which shows that the generator is general and not a replay.

## Microsoft technologies

- **Microsoft Foundry** for models and agents
- **Microsoft Agent Framework** for multi-agent orchestration
- **MCP** to expose the engine's query functions to the "Ask the match" agent
- **Azure Container Apps** for the engine and the WebSocket stream
- **Azure Static Web Apps** for the UI
- **GitHub Copilot** and **GitHub Actions** for development and CI

## Team

Baja-Insights, a team of three.

## License

MIT
