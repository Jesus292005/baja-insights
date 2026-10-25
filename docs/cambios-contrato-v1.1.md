# Cambios al contrato, de v1 a v1.1

**Aprobada por los tres integrantes el 23 de octubre de 2026.** Los esquemas de `contracts/` ya tienen estos cambios. Los mocks, el motor y los agentes todavía no los producen: las tareas de cada quien están abajo. Todo lo nuevo es opcional y nada de lo que ya existe deja de validar.

Quién se ve afectado: **1** motor, **2** agentes, **3** interfaz.

---

## Por qué

Al diseñar la interfaz salieron cinco datos que la UI necesita y que hoy no le llegan. Sin ellos tendría que inventarlos o recalcularlos, y la regla del proyecto es que la interfaz nunca hace ninguna de las dos cosas.

| Hueco | Qué pasa hoy | Consecuencia en pantalla |
| --- | --- | --- |
| Carrera MVP | `mvp_update` solo trae el puesto de **un** jugador | No se puede dibujar el ranking sin adivinar los demás puestos |
| Cadena del gol | La orden trae nombres y crédito, pero no la acción, el tiempo ni la jugada de cada eslabón | El modo analista no puede decir «pase que rompió 2 líneas, jugada #1355» |
| Cartas | `card` no trae la media (`overall`) | La carta tendría que promediar siete atributos, o sea recalcular |
| Chat | `chat_answer` existe como tipo, pero sin forma de `data` ni ejemplos, y el chat es pregunta y respuesta, no una orden programada | Cada quien implementaría su propia forma |
| Stream | Solo viajan órdenes. No hay marcador, reloj ni latido | El marcador se tendría que deducir y la UI no sabe cuándo se cortó la conexión |

Además apareció una **divergencia** que ya existe en v1: `goal_analysis.data.invisible_assist` es un texto en el mock (`"J. Torres"`) y un objeto en la salida real de los agentes (`data/m001/overlays.json`, orden o084). El esquema v1 no lo restringía, así que ambos validaban.

---

## Cambios que agregan campos

No rompen nada. Todos son opcionales en el esquema.

| # | Cambio | Dónde | Por qué | Afecta |
| --- | --- | --- | --- | --- |
| 1 | **`ranking`** en `mvp_rank_change.facts`: top del MVP justo después del cambio, con la misma forma que `get_mvp_ranking` (`rank`, `player`, `team`, `position`, `mvp_score`). Se recomienda el top 5 | `insight.schema.json` | El motor ya lo tiene al calcular el cambio de puesto. Así la cifra sale del motor y no del agente | 1, 2 |
| 2 | **`data.ranking`** en `mvp_update`, copiado del insight | `overlay.schema.json` | La carrera MVP del rail se dibuja con datos del motor | 2, 3 |
| 3 | **`evidence`** en la orden, con los `event_id` del insight de origen. No va en los fotogramas de la barra de duelo | `overlay.schema.json` | El modo analista muestra «Evidencia: #1340 #1353» y cualquiera puede rastrear la cifra | 2, 3 |
| 4 | **`card.overall_from`**, **`card.overall_to`** y **`card.reason`**, copiados del `card_change` o del `card_upgrade` | `overlay.schema.json` | La carta muestra su media y el motivo sin calcular nada | 2, 3 |
| 5 | **`data.chain_detail`** en `goal_analysis`, con los mismos eslabones de `goal_chain.facts.chain` (`event_id`, `player`, `action`, `credit`, `t_s`) | `overlay.schema.json` | La cadena del gol en modo analista, animada en orden de `t_s` | 2, 3 |
| 6 | **`data`** de `chat_answer` definido: `question`, `status` (`answered`, `not_tracked`, `not_found`, `no_prediction`), `tools` y `evidence` opcional | `overlay.schema.json` | Para cuando el productor pone una respuesta del chat en pantalla | 2, 3 |
| 7 | Nuevo **`stream.schema.json`** con los mensajes del WebSocket: `subscribe` (UI → servidor), `overlay`, `clock`, `state` y `error` (servidor → UI) | Nuevo archivo | Marcador desde los eventos, latido para detectar la reconexión y reenvío de órdenes al reconectar | 1, 3 |
| 8 | Nuevo **`chat.schema.json`** con la petición y la respuesta de `POST /api/ask` | Nuevo archivo | Una sola forma para el agente Pregúntale y para la interfaz | 2, 3 |

### Detalle del stream (cambio 7)

```
UI ──subscribe {match_id, from_t_s}──▶ servidor
UI ◀──state {t_s, home, away, scoreline}── servidor        al suscribirse, en cada gol, al medio tiempo y al final
UI ◀──overlay {order}── servidor                           todas las variantes; la UI filtra por modo e idioma
UI ◀──clock {t_s, period, phase, speed}── servidor         una vez por segundo de reloj real
UI ◀──error {code, detail}── servidor
```

- **Reconexión.** Si pasan 3 segundos sin `clock`, la UI muestra «Reconectando» y conserva el último dato con su minuto. Al volver, manda `subscribe` con el último `t_s` que tenía y el servidor responde con `state` y reenvía las órdenes con `show_at_s ≥ from_t_s`.
- **Marcador.** Sale de los eventos `goal`, `half_time` y `match_end`, que ya traen `scoreline`. La UI no lo deduce de las órdenes de gol.
- El campo `order` de un mensaje `overlay` se valida aparte con `overlay.schema.json`. Así `stream.schema.json` no depende de resolver referencias externas.

### Detalle del chat (cambio 8)

- **Petición:** `match_id`, `question` (de 1 a 500 caracteres), `at`, `mode`, `language`, y opcionales `favorite_team` y `history` (hasta 6 turnos, para preguntas como «¿y Cota?»).
- **Respuesta:** `match_id`, `question`, `at_s`, `status`, `answer`, `tools` y opcionales `evidence` y `error`.
- `status: "error"` obliga a mandar `answer: null` y un código en `error` (`timeout`, `engine_unavailable`, `agent_failed`). Cualquier otro `status` obliga a mandar un `answer` con texto.
- `not_tracked` es lo que debe responder la pregunta de los kilómetros de Torres de `chat_tools_sample.json`, porque `distance_km` está en `not_tracked`. La interfaz lo marca distinto de una respuesta normal.

---

## Cambios que restringen, sin romper nada que exista hoy

| # | Cambio | Por qué es seguro | Afecta |
| --- | --- | --- | --- |
| 9 | Una orden `chat_answer` ahora **debe** traer `data` con la forma del cambio 6 | Nadie emite `chat_answer` todavía: no hay ninguna en `mocks/` ni en `data/` | 2 |
| 10 | `goal_analysis.data.invisible_assist` acepta **solo** `null`, un texto o el objeto completo del insight (`player`, `dragged_defender`, `space_opened_m`, `touched_ball`). Antes aceptaba cualquier cosa | Los dos casos que existen (texto en el mock, objeto en `data/m001`) siguen validando | 2, 3 |

## Lo que se marca como obsoleto

| # | Qué | Reemplazo | Se quita en |
| --- | --- | --- | --- |
| 11 | `invisible_assist` como texto (solo el nombre) | El objeto, que es lo que ya producen los agentes y lo que pide la regla de «misma forma que el insight» | v2 |

---

## Qué tiene que hacer cada quien

### Integrante 1, motor

- [x] Agregar `ranking` (top 5) a los `facts` de `mvp_rank_change` en `src/baja_insights/engine/core.py`. Puede salir de la misma lógica que `get_mvp_ranking` en `tools.py`.
- [x] Servicio de stream en Container Apps con los mensajes de `stream.schema.json`. Ver `docs/stream.md`.
- [x] Opcional: que `python -m baja_insights validate` reconozca archivos de `stream` y `chat`. Hoy solo detecta eventos, insights y órdenes.

### Integrante 2, agentes

Todo en `agents/baja_agents/overlays.py`, que ya copia del insight lo que no es texto:

- [x] `data_for`: copiar `facts["ranking"]` en `mvp_update` y `facts["chain"]` como `chain_detail` en `goal_analysis`. Hecho en el PR #4.
- [x] `card_for`: copiar `overall_from`, `overall_to` y `reason` del `card_change`. Hecho en el PR #4; desde el PR #12 también copia `reason_code` y `reason_params`.
- [x] `build`: copiar `insight["evidence"]` en cada orden. Hecho en el PR #4.
- [x] Endpoint `POST /api/ask` con `chat.schema.json`, y la orden `chat_answer` con `data` cuando aplique.
  - **`/api/ask`:** PR #14 y #15, desplegado como `baja-chat`.
  - **`chat_answer`:** `POST /api/chat-overlay`, que convierte una respuesta del chat en una orden `chat_answer` válida, sin llamar al modelo.
  - Detalles en `agents/README.md`.

### Integrante 3, interfaz

- [ ] Tipos en `web/src/contracts/overlay.ts`, que ya siguen esta propuesta.
- [ ] Mostrar un estado vacío honesto cuando falte cualquier campo de v1.1. La UI debe funcionar con órdenes v1.

### Los tres, ahora que está aprobada

- [ ] Actualizar `mocks/overlays_sample.json` e `insights_sample.json` con un ejemplo de cada campo nuevo, y cambiar `invisible_assist` del mock al objeto.
- [x] Subir `contract_version` a `"1.1"` en `mocks/teams.json` y `mocks/chat_tools_sample.json`.
- [x] Agregar `data/m001/overlays.json` a los casos de `tests/test_contracts.py`, que hoy no lo valida.

---

## Cómo se verificó

Con `jsonschema` 4.26 y los esquemas de esta propuesta:

- Siguen validando sin errores todos los archivos actuales: `mocks/events_sample.jsonl`, `insights_sample.json`, `overlays_sample.json`, `data/m001/events.jsonl`, `insights.json`, `overlays.json` y `data/free-seed2/insights.json`.
- Validan ejemplos de cada campo nuevo, construidos con datos reales del mock (la cadena del gol 1-1, el ranking del 35:00 y las seis conversaciones de `chat_tools_sample.json`).
- Se rechazan los casos inválidos: ranking sin `mvp_score`, eslabón sin `event_id`, `invisible_assist` incompleto, `chat_answer` sin `data` o con una función que no existe, `overall_to` mayor que 99, `clock` con periodo 3, `state` sin marcador, error del chat sin código y respuesta `answered` sin texto.
- `pytest tests` (33 tests) y `pytest agents/tests` (83 tests) pasan.

---

## Checklist de aprobación

- [x] Integrante 1
- [x] Integrante 2
- [x] Integrante 3
