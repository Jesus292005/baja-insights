# Agents, member 2

This folder holds the four agents on Microsoft Foundry and their orchestration with Microsoft Agent Framework: Curator, Narrator, Personalization and Ask the Match.

## Input and output

- **In:** insights shaped like `contracts/insight.schema.json`. You can use `mocks/insights_sample.json`, or the real match in `data/m001/insights.json`.
- **Out:** graphics orders shaped like `contracts/overlay.schema.json`. Examples in `mocks/overlays_sample.json`.

## How it works

One Agent Framework workflow run for every 5-minute block of play:

```
insights ──▶ Curator ──▶ Narrator ──▶ Personalization ⇄ Verifier ──▶ Composer ──▶ graphics orders
```

| Step | What it does | File |
| --- | --- | --- |
| **Curator** | Chooses what goes on screen. The rules live in code: goals, match keys and the top 3 always show, repeats are dropped, and each block has a budget of 3. The model chooses among the rest. | `baja_agents/curator.py` |
| **Narrator** | Explains why the moment matters, using the scoreline and what has already been on screen. | `baja_agents/narrator.py` |
| **Personalization** | Writes the four versions: fan and analyst, in Spanish and English. | `baja_agents/personalizer.py` |
| **Verifier** | Checks every claim in the four versions against the insight: each player's team, who did what, who is ahead. If it fails, nothing is blocked. | `baja_agents/verifier.py` |
| **Composer** | No AI. Copies the numbers from the insight, picks slot and duration, keeps graphics from overlapping and adds the duel bar frames. | `baja_agents/overlays.py` |

The agents share a context (`MatchContext` in `baja_agents/workflow.py`): the scoreline, the graphics already shown and the final summary. Code prepares the data so the agents don't have to interpret it: per-team values are keyed by team name instead of `home`/`away`, the scoreline comes as text ("Bahía FC 0-1 Real Cardón"), every player comes with their team, and stats come already worded ("16 progressive passes").

**What code checks before accepting a text** (`baja_agents/checks.py`):
- Every number in the text appears in the insight or in the scoreline.
- "N + stat" matches the real value, so 16 progressive passes never show up as 16 key passes.
- Scorelines are written home-away.
- Fan mode shows at most one figure, besides the scoreline.
- Titles have at most 6 words and texts at most 30.

Then the verifier reviews the versions that passed. If something fails, the model gets one retry with the problems listed, and each version keeps the latest attempt that passed. Whatever still fails is replaced by a template (`baja_agents/fallback.py`). The same happens when an agent fails, takes longer than 30 s, or the budget of 250 calls per match runs out. Responses are cached in `agents/.cache/`, so running again costs no tokens.

**Duel bar frames.** These are the `duel_bar` orders with `source_insight: null` and `mode`/`language` set to `all`. Every 5 minutes, the bar of the last duel shown is refreshed with the engine's value (`MatchQuery.get_duel`). A frame is skipped if the bar moved less than 0.05, if its slot is busy, or if no duel notice has been shown yet. It needs `events.jsonl` next to the insights, or `--events`.

## Running

From the repo root, once:

```bash
agents/venv/Scripts/python.exe -m pip install -e ".[dev]" -r agents/requirements.txt
```

Demo match with Foundry. Writes `data/m001/overlays.json` and `data/m001/agents_report.json`:

```bash
cd agents
venv/Scripts/python.exe -m baja_agents run
```

Without Foundry, templates and cache only:

```bash
venv/Scripts/python.exe -m baja_agents run --offline
```

`agents_report.json` shows what the curator decided and why, which versions an agent wrote and which a template, and how many calls were made.

To fact-check an `overlays.json` that was already generated, for example before recording the video:

```bash
venv/Scripts/python.exe -m baja_agents audit
```

The verifier uses the same model as the other agents. To give it a more capable deployment of its own, add `FOUNDRY_VERIFIER_MODEL=<deployment name>` to `agents/.env`.

Offline tests, with fake agents:

```bash
venv/Scripts/python.exe -m pytest tests -q
```

For live use, `Crew.process_block(label, insights)` in `baja_agents/pipeline.py` processes one block and returns its orders.

## Reading insights live from the engine

```bash
python -m baja_insights stream --events data/m001/events.jsonl --speed 60
```

It prints one insight per line, as JSON, at the moment it happens. It can also be used from Python:

```python
from baja_insights.roster import Roster
from baja_insights.engine import InsightEngine

engine = InsightEngine(Roster.load())
for event in events:
    for insight in engine.process(event):
        curator.send(insight)
```

## Tools for Ask the Match

```python
from baja_insights.engine.tools import MatchQuery

query = MatchQuery.from_files("data/m001/events.jsonl")
query.dispatch("get_mvp_ranking", {"at": "35:00", "top": 3})
```

The definitions of the six functions, ready to register as tools, are in `mocks/chat_tools_sample.json` under `tools`. The conversations in `example_conversations` work as test cases.

## Rules

- Numbers come from the insight or from a tool. The agent never computes or invents them.
- If a tool answers with `error` or `not_tracked`, the agent says it doesn't have that data.
- No predictions of the result.
- If an agent fails or is slow, a fallback text is used and the match keeps its overlays.
