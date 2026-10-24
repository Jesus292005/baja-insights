import asyncio
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

load_dotenv()
MOCKS = Path(__file__).parent.parent / "mocks"


class Variant(BaseModel):
    title: str
    text: str


class Variants(BaseModel):
    fan_es: Variant
    analyst_es: Variant
    fan_en: Variant
    analyst_en: Variant


INSTRUCCIONES = """
You're the narrator of Baja-Insights. You receive a football insight in JSON and write four versions to display on screen.

Rules
- Only use the data that comes in the insight. Never invent figures, names, or plays.
- Explain why the moment matters, not just what happened.
- Write four versions: fan_es, analyst_es, fan_en, analyst_en.
- fan is for a casual fan. Tell the story, with one figure at most.
- analyst is for an analyst. Use the figures from the insight.
- Maximum 6-word title and 30-word text.
- Never make predictions about the outcome.
- Write fan_es and analyst_es in Spanish and fan_en and analyst_en in English.
"""


def numeros(texto):
    """Extracts all the numbers from a text."""
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", texto)}


def numeros_en_json(obj):
    """Extracts all the numbers from an insight, including those that come in texts."""
    base = numeros(json.dumps(obj, ensure_ascii=False))
    porcentajes = {round(n * 100) for n in base if 0 < n <= 1}
    return base | {float(p) for p in porcentajes}


def validar(insight, variantes):
    """Returns the numbers that appear in the text but not in the insight."""
    permitidos = numeros_en_json(insight)
    errores = {}
    for nombre, v in variantes.model_dump().items():
        inventados = numeros(v["title"] + " " + v["text"]) - permitidos
        if inventados:
            errores[nombre] = sorted(inventados)
    return errores


async def main():
    insights = json.loads((MOCKS / "insights_sample.json").read_text(encoding="utf-8"))
    insight = next(i for i in insights if i["insight_id"] == "i05")

    narrador = Agent(
        client=FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=AzureCliCredential(),
        ),
        name="narrator",
        instructions=INSTRUCCIONES,
    )

    response = await narrador.run(
        json.dumps(insight, ensure_ascii=False),
        options={"response_format": Variants},
    )
    variantes = response.value
    if variantes is None:
        print("The response could not be parsed as Variantes. Here is the raw response:")
        print(response.text)
        return

    print(json.dumps(variantes.model_dump(), ensure_ascii=False, indent=2))

    errores = validar(insight, variantes)
    if errores:
        print("\nInvented numbers", errores)
    else:
        print("\nCorrect validation, the numbers in the text match those in the insight.")


asyncio.run(main())