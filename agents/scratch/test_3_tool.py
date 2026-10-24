import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field
from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

load_dotenv()
MOCKS = Path(__file__).parent.parent / "mocks"
EXAMPLES = json.loads((MOCKS / "chat_tools_sample.json").read_text(encoding="utf-8"))


def example_result(function_name):
    """Looks for the result of a function in the example conversations."""
    for conversation in EXAMPLES["example_conversations"]:
        for call in conversation["tool_calls"]:
            if call["name"] == function_name:
                return call["result"]
    return None


@tool
def get_mvp_ranking(
    at: Annotated[str, Field(description="Moment of the match in format mm:ss")],
) -> str:
    """Returns the MVP ranking at a given moment of the match."""
    print(f"  [tool] get_mvp_ranking(at={at})")
    return json.dumps(example_result("get_mvp_ranking"), ensure_ascii=False)


@tool
def get_player_summary(
    player: Annotated[str, Field(description="Player name, for example J. Torres")],
    at: Annotated[str, Field(description="Moment of the match in format mm:ss")],
) -> str:
    """Returns accumulated statistics and key plays of a player."""
    print(f"  [tool] get_player_summary(player={player}, at={at})")
    return json.dumps(example_result("get_player_summary"), ensure_ascii=False)


async def main():
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=AzureCliCredential(),
        ),
        name="AskTheMatch",
        instructions=(
            "Answer questions of fans about the match. "
            "You have access to the following tools: get_mvp_ranking and get_player_summary. "
            "Always use the tools to answer questions, and never invent data, just use the data that the tools return. "
            "If the data doesn't exist, say so. Never make predictions. Answer in a maximum of 3 sentences. "
            "The moment of the match is 35:00. "
            "El momento actual del partido es 35:00."
        ),
        tools=[get_mvp_ranking, get_player_summary],
    )
    result = await agent.run("¿Why Torres is in first?")
    print("\n" + result.text)


asyncio.run(main())