import asyncio
import os

from dotenv import load_dotenv
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

load_dotenv()


async def main():
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=AzureCliCredential(),
        ),
        name="Test",
        instructions="You are a football narrator. Respond in one prashe.",
    )
    result = await agent.run("Describe a goal in the last minute.")
    print(result.text)


asyncio.run(main())