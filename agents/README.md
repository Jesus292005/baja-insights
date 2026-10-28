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
| **Curator** | Chooses what goes on screen. The rules live in code: goals, match keys, the top 3 and the first duel of each half always show, repeats are dropped, and each block has a budget of 3. The model chooses among the rest. | `baja_agents/curator.py` |
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

**Penalties.** A goal's chain has only the shot, and the foul is not a link. When the shot event has `set_piece: "penalty"`, code adds `facts.penalty` (who drew the foul and who gave it away) for the agents and the templates, which then tell it as a penalty (`narrator.with_penalty`). The orders don't copy it, so the contract doesn't change. An `invisible_assist` with `touched_ball: true` (Salgado for f091's 1-2) is never told as "without touching the ball".

Then the verifier reviews the versions that passed. If something fails, the model gets one retry with the problems listed, and each version keeps the latest attempt that passed. Whatever still fails is replaced by a template (`baja_agents/fallback.py`). The same happens when an agent fails, takes longer than 30 s, or the budget of 250 calls per match runs out. Responses are cached in `agents/.cache/`, so running again costs no tokens.

**Duel bar frames.** These are the `duel_bar` orders with `source_insight: null` and `mode`/`language` set to `all`. Every 5 minutes, the bar of the last duel shown is refreshed with the engine's value (`MatchQuery.get_duel`). A frame is skipped if the bar moved less than 0.05, if its slot is busy, or if no duel notice has been shown yet. That is why the first duel of each half always shows: f091's duels never beat the other graphics, and the match had no duel bar. It needs `events.jsonl` next to the insights, or `--events`.

## Running

From the repo root, once:

```bash
agents/venv/Scripts/python.exe -m pip install -e ".[dev]" -r agents/requirements.txt
```

Scripted match with Foundry. Writes `data/m001/overlays.json` and `data/m001/agents_report.json`:

```bash
cd agents
venv/Scripts/python.exe -m baja_agents run
```

The match without a script, `f091`, the one in the video (`docs/aviso-partido-sin-guion.md`). Regenerate it whenever the engine regenerates `data/f091`:

```bash
venv/Scripts/python.exe -m baja_agents run --insights ../data/f091/insights.json
```

The orders take their `match_id` from `events.jsonl`: the engine's CLI writes the insights of every match with `m001`.

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

## Credentials and deployment

The agents authenticate with `DefaultAzureCredential` (`baja_agents/config.py`). There are no API keys:

- **On a laptop** it uses `az login`. Your account needs the **Foundry User** role on the Foundry resource (or its resource group).
- **In Azure Container Apps** it uses the container's managed identity. With a user-assigned identity, also set `AZURE_CLIENT_ID` to its client id.

Environment variables, the same as in `agents/.env`:

| Variable | Value |
| --- | --- |
| `FOUNDRY_PROJECT_ENDPOINT` | `https://<resource>.services.ai.azure.com/api/projects/<project>` |
| `FOUNDRY_MODEL` | Model deployment name, e.g. `gpt-4.1-mini-baja-insights` |
| `FOUNDRY_VERIFIER_MODEL` | Optional, a deployment for the verifier only |
| `AZURE_CLIENT_ID` | Only with a user-assigned managed identity |

**The container must live in the same subscription and tenant as the Foundry resource.** A managed identity cannot get tokens for a Foundry resource in another tenant, and each Azure for Students account usually has its own tenant. The Foundry resource is `diegomanzo-2526-resource` in `rg-baja-insights`.

One-time setup, by the owner of that subscription:

```bash
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

After creating the container app with a system-assigned identity, give it access to Foundry:

```bash
PRINCIPAL=$(az containerapp identity show -g rg-baja-insights -n <app> --query principalId -o tsv)
FOUNDRY=$(az cognitiveservices account show -g rg-baja-insights -n diegomanzo-2526-resource --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Foundry User" --scope "$FOUNDRY"
```

In Git Bash on Windows, run `export MSYS_NO_PATHCONV=1` first, or it rewrites the `/subscriptions/...` scope. The role can take a few minutes to apply; until then the agents get a 401 or 403 and fall back to templates.

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

## Ask the Match

`POST /api/ask`, shaped like `contracts/chat.schema.json`. The code is in `baja_agents/ask.py` (the agent) and `baja_agents/server.py` (the HTTP service).

The agent answers only through the six engine functions of `MatchQuery` (`get_match_state`, `get_mvp_ranking`, `get_player_summary`, `get_duel`, `get_team_phase` and `get_goal_chain`). They are registered with the definitions in `mocks/chat_tools_sample.json`, so the agent and the contract describe the same functions.

**What code enforces, not the prompt:**
- **No future.** Every moment the agent asks for is clipped to the moment of the question, and `get_goal_chain` only finds goals already scored, so a live chat never reveals what comes next.
- **No invented numbers.** Every number in the answer must appear in a function result; ids don't count. If one doesn't, the agent gets one retry with the problem listed, and if it still fails the answer is `status: "error"` and the UI shows its fallback.
- **No predictions.** "Who will win?" is detected in code and always answered with `no_prediction`. The agent still says what each team needs, with data, as in the examples.
- **Style.** A fan answer shows at most 3 figures besides the scoreline. Breaking this is worth a retry, but an accurate answer is kept even if the retry still breaks it.
- `not_tracked` (for example distance run) and `not_found` (a player who isn't in the match) come from what the functions return.
- **Flank duels without names.** `get_duel` needs two players, and "who's winning the flank duel?" names none. With every question, code computes the flank duels up to that moment (each full-back against the opposing winger, plus any substitute pair that already had a duel), most contested first, and gives them to the agent as `flank_duels`. The agent takes the names from there and asks `get_duel` for the figures.
- **Lineups.** No function returns lineups, so the agent used to guess them from the flat list of all 25 players in a `player_not_found`, mixing teams and substitutes. With every question, code now gives it `lineups` for that moment, from the roster and the substitution events: each team's eleven on the pitch with positions, the bench and the substitutions so far. A question about lineups, the bench or substitutions (detected in code, like predictions) may be answered from it with no function call; every other question still needs one.
- **Goals.** For a question about a goal (detected in code), the agent also gets `goals`: every goal scored so far with its chain (who started it, who passed, who finished, the run without the ball), with team names and no ids or coordinates. Before this, gpt-4.1-mini sometimes explained the equaliser from the team's phase instead of the chain. It may answer from it with no function call, and the response lists `get_match_state` and `get_goal_chain` as the functions behind it. A goal scored from the spot comes with `penalty`, in `goals` and in what `get_goal_chain` returns to the agent.
- **"Not in this match"** (`not_found`) may also be answered from `lineups` with no function call.
- **Scorelines.** Only a scoreline written backwards ("1-0" when it is 0-1) is rejected; "3-1 in duels" is not a scoreline.
- **Reasoning effort.** `FOUNDRY_REASONING_EFFORT` (`none`, `low`, `medium`...) is passed to reasoning models such as gpt-5.4-mini. Leave it empty for gpt-4.1 and gpt-4.1-mini, which reject the option.
- **Markdown.** The answer is Markdown (paragraphs, `- ` and `1. ` lists, bold, italics), rendered by the chat in `web/src/chat/ChatMarkdown.tsx`. The checks read it without its markup (`checks.plain_text`), so a `1. ` list marker is not a figure, and `POST /api/chat-overlay` puts the plain text on the stage.
- **Language.** The answer is always in the request's `language`, the one the fan chose in the app, even when the question is typed in another language.

**Service:**
- `GET /healthz` and `POST /api/ask`, with open CORS for the UI.
- Requests are validated against the contract: an invalid one gets 400, and an unknown `match_id` gets 404.
- Every `data/<match>/events.jsonl` is loaded at startup (`m001` and `f002`).
- At most `CHAT_PER_MINUTE` questions per minute reach the model (20 by default). Beyond that the answer is 429.
- Answers are cached by match, question, moment, mode, language, favorite team and history (`CHAT_CACHE_DIR`), so the questions from the video or the judges cost nothing the second time.
- A first answer takes about 4 to 7 seconds; a cached one, a few milliseconds.

```bash
venv/Scripts/python.exe -m baja_agents serve --port 8080
venv/Scripts/python.exe -m baja_agents ask "¿Quién lidera la carrera al MVP?" --at 35:00
```

The image is `chat.Dockerfile`, built by `.github/workflows/chat-image.yml` into `ghcr.io/jesus292005/baja-chat`, and deployed as `baja-chat` (see `docs/despliegue.md`). Offline tests are in `tests/test_ask.py`: a fake agent calls the real engine functions.

### Putting an answer on screen (`chat_answer`)

When the producer wants a fan's question and its answer on screen, the UI sends the `/api/ask` response to `POST /api/chat-overlay` and gets back a `chat_answer` graphics order that matches `overlay.schema.json`:

```json
{"answer": {"match_id": "m001", "question": "...", "at_s": 1800, "status": "answered", "answer": "...", "tools": ["get_match_state"]},
 "mode": "fan", "language": "es", "show_at_s": 1802, "slot": "side_panel"}
```

- `show_at_s` and `slot` are optional. They default to the answer's moment and `side_panel`.
- The order is built in code (`overlays.chat_answer_order`), with no model call. The title is the question, the text is the answer, and `data` (`question`, `status`, `tools`, `evidence`) is copied from it. `source_insight` is `null`, and the duration depends on the length (8 to 20 s).
- The `overlay_id` is stable (`chat-<hash>`), so the same answer is never shown twice.
- An answer with `status: "error"` has no text and gets 422. An invalid body gets 400.
- The stream replays files and does not take new orders live, so the UI draws this order itself.

## MCP server

The same six engine functions are also an **MCP server** (Model Context Protocol), at `POST /mcp` on the chat service (`baja_agents/mcp_server.py`). Any MCP client can query the match with them: Agent Framework's `MCPStreamableHTTPTool`, a Foundry agent, Claude, VS Code, or the MCP Inspector.

- **Tools:** the six functions with the descriptions of `mocks/chat_tools_sample.json`, plus `list_matches`.
- **Arguments:** every tool takes `match_id` (default `m001`) and an optional `as_of` (`MM:SS`). With `as_of`, the server answers as if the match were live at that moment: every moment is clipped to it and only goals already scored can be looked up, with the same code as Ask the Match. Without it, the whole match is available.
- **Errors:** "not found" and "not tracked" (`goal_not_found`, `player_not_found`, `match_not_found`, `not_tracked`) are answers, so they come back as data with `isError: false`, as in the chat. Only a malformed call (`bad_arguments`) is a tool error (`isError: true`), which clients such as Agent Framework raise.
- **Transport:** Streamable HTTP, stateless, answering every request with `application/json`. It supports `initialize`, `tools/list`, `tools/call` and `ping`, and returns empty lists for prompts and resources.
- **No SDK on the server.** On Windows, Application Control can block the `pywin32` DLL that the MCP SDK imports. The client test (`tests/test_mcp.py`) uses Agent Framework's MCP client on the official SDK. It skips locally when the SDK can't load, and CI requires it (`REQUIRE_MCP_CLIENT=1`, with `agents/requirements-dev.txt`).

```python
from agent_framework import MCPStreamableHTTPTool

async with MCPStreamableHTTPTool(name="baja", url="https://baja-chat.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/mcp") as tool:
    agent = Agent(client=client, name="analyst", tools=tool)
    print(await agent.run("Who led the MVP race at 35:00 in m001, and why?"))
```

## Rules

- Numbers come from the insight or from a tool. The agent never computes or invents them.
- If a tool answers with `error` or `not_tracked`, the agent says it doesn't have that data.
- No predictions of the result.
- If an agent fails or is slow, a fallback text is used and the match keeps its overlays.
