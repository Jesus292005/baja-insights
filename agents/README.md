# Agentes, integrante 2

Aquí van los cuatro agentes en Microsoft Foundry y su orquestación con Microsoft Agent Framework: Curador, Narrador, Personalización y Pregúntale al partido.

## Entrada y salida

- **Entra:** insights con la forma de `contracts/insight.schema.json`. Mientras tanto, puedes usar `mocks/insights_sample.json`, o el partido real en `data/m001/insights.json`.
- **Sale:** órdenes de gráfico con la forma de `contracts/overlay.schema.json`. Ejemplos en `mocks/overlays_sample.json`.

## Leer insights en vivo desde el motor

```bash
python -m baja_insights stream --events data/m001/events.jsonl --speed 60
```

Imprime un insight por línea en JSON en el momento en que ocurre. También se puede usar desde Python:

```python
from baja_insights.roster import Roster
from baja_insights.engine import InsightEngine

engine = InsightEngine(Roster.load())
for event in events:
    for insight in engine.process(event):
        curator.send(insight)
```

## Herramientas para Pregúntale al partido

```python
from baja_insights.engine.tools import MatchQuery

query = MatchQuery.from_files("data/m001/events.jsonl")
query.dispatch("get_mvp_ranking", {"at": "35:00", "top": 3})
```

Las definiciones de las seis funciones, listas para registrarlas como herramientas, están en `mocks/chat_tools_sample.json` bajo `tools`. Las conversaciones de `example_conversations` sirven como casos de prueba.

## Reglas

- Los números salen del insight o de una herramienta. El agente nunca los calcula ni los inventa.
- Si una herramienta responde con `error` o `not_tracked`, el agente dice que no tiene ese dato.
- No hace predicciones del resultado.
- Si un agente falla o tarda, se usa un texto de respaldo y el partido sigue con overlays.
