# Contrato v1.1: lo que hizo el integrante 1 y lo que falta

Integrante 1: motor de insights, generador y servicio de stream. Resumen de todo lo hecho para el contrato v1.1 y de lo que le toca a cada quien.

| PR | Rama | Qué trae | Estado |
| --- | --- | --- | --- |
| #5 | `motor-v1.1` | Ranking del MVP, servicio de stream, `validate` para stream y chat | Fusionado |
| #6 | `motor-v1.1-fixes` | Correcciones en las funciones del chat y este documento | Fusionado |

---

## 1. Lo que se hizo

### Ranking en `mvp_rank_change` (cambio 1 del contrato)

- Cada `mvp_rank_change` trae `facts.ranking` con el top 5 del MVP. Cada fila tiene `rank`, `player`, `team`, `position` y `mvp_score`, igual que `get_mvp_ranking`.
- Las dos salen de la misma función, `PlayerState.ranking_rows`, así que no pueden divergir. El tamaño del top está en `MVP_RANKING_TOP` de `params.py`.
- El ranking se calcula justo después del evento que provocó el cambio. Si en ese mismo segundo hay otro evento, `get_mvp_ranking` puede dar una décima distinta. Por ejemplo, a las 34:45 Montaño tiene 6.2 en el insight y 6.3 en el chat.
- Se regeneraron `data/m001/insights.json` y `data/free-seed2/insights.json`. Solo cambia `facts.ranking`: los demás insights quedan idénticos.

### Servicio de stream (cambio 7)

- Se arranca con `python -m baja_insights serve --data data --port 8080 --speed 60`. Los detalles están en `docs/stream.md`.
- Sigue `contracts/stream.schema.json`: `subscribe`, `state`, `overlay`, `clock` y `error`, todos con `kind`.
- **Reloj.** Hay uno por partido, compartido por todos los espectadores. Arranca con el primer `subscribe`. Con `--half-time-pause` se detiene en 45:00 en fase `half_time`.
- **Marcador.** Sale solo de los eventos `goal`, `half_time` y `match_end`.
- **Envío.** Cada orden llega justo en su `show_at_s`, aunque la velocidad sea alta. El `clock` sale una vez por segundo real. `stream_ended` se manda una vez al terminar, y el latido sigue.
- **Reconexión.** Se reenvían las órdenes con `show_at_s + duration_s > from_t_s`, así que también vuelven los gráficos que estaban en pantalla cuando se cortó la conexión.
- **Infraestructura.** No usa dependencias fuera de la biblioteca estándar. Incluye `GET /healthz` y `stream.Dockerfile` para Azure Container Apps. Debe correr con una sola réplica, porque el reloj vive en memoria.

### Herramientas y contratos

- `python -m baja_insights validate` reconoce mensajes de stream (y valida la orden dentro de cada `overlay`) y peticiones y respuestas de chat.
- `contract_version` pasa a `"1.1"` en `mocks/teams.json`, `mocks/chat_tools_sample.json` y `CONTRACT_VERSION`.
- `tests/test_contracts.py` ahora valida `data/m001/overlays.json` y los archivos de `free-seed2`.
- Las tareas del integrante 1 quedaron marcadas en `docs/cambios-contrato-v1.1.md`.

### Correcciones en las funciones del chat

Se buscaron errores con 26 partidos generados con semillas distintas y con entradas raras en las funciones del chat. Todas las reglas del contrato se cumplieron en los 26 partidos: marcador, cadenas de gol, cartas, ranking e identificadores. Los errores estaban en cómo las funciones del chat leen lo que les manda el agente:

| Problema | Antes | Ahora |
| --- | --- | --- |
| Momento con segundos imposibles | `"99:99"` se leía como el minuto 100:39 | `bad_arguments` |
| Momento negativo | `"-1"` daba `at_s: -60` | `bad_arguments` |
| Momento después del final | `"92:30"` respondía con `at_s: 5550` | Estado final, `"90:00"` y `at_s: 5400` |
| Jugador `null` | `get_player_summary` tronaba con `AttributeError` | `player_not_found` |
| Equipo vacío o de una letra | `""` y `"a"` regresaban datos de Bahía FC | `team_not_found` |
| Nombres sin acento | `"bahia"`, `"cardon"` y `"ramirez"` no se encontraban | Se encuentran, sin importar acentos ni mayúsculas |

Los cambios están en `contract.parse_clock`, `tools._at` y `Roster.find` / `Roster.find_team`. Una parte del nombre del equipo solo cuenta si tiene al menos 3 letras y corresponde a un solo equipo.

### Cómo se verificó

- Pasan 57 tests del motor y el stream: 33 anteriores y 24 nuevos (3 del ranking, 15 del stream y 6 de las funciones del chat).
- Se grabó un partido completo por el WebSocket. Llegaron las 119 órdenes de `m001`, cada una una vez y en orden, con el marcador 0-1 en el 1060, el medio tiempo y el 1-1 en el 3789. Los 129 mensajes validan con `stream.schema.json`.
- Los mocks y los datos validan contra los esquemas, y los eventos e insights de `m001` y `free-seed2` se regeneran idénticos.
- **No se pudo probar:** la imagen Docker, porque no había daemon, ni la suite de agentes, porque falta `agent_framework`. El comando del contenedor sí se probó con solo `src/` y `data/`.

---

## 2. Qué cambia para los demás

- **Agente Pregúntale.** Un momento inválido ahora llega como `bad_arguments`, en vez de un minuto inventado. Una pregunta sobre «el minuto 92» responde con el estado final a las 90:00. Los nombres sin acento ya funcionan, así que el agente no necesita corregirlos. Un nombre vacío o ambiguo responde `player_not_found` o `team_not_found`, nunca un equipo al azar.
- **Insights.** `mvp_rank_change` trae `facts.ranking`. Es solo para la interfaz: el modelo no debe verlo ni citarlo (ver integrante 2).
- **Interfaz.** El stream ya existe y sigue `stream.schema.json`, con los detalles de la sección del integrante 3.

---

## 3. Lo que falta: integrante 2, agentes

### Ya resuelto en el PR #4

- [x] `card_for` copia `overall_from`, `overall_to` y `reason` (48 órdenes con carta).
- [x] `data_for` copia `chain_detail` en `goal_analysis`, y `ranking` en `mvp_update` cuando el motor lo emite.
- [x] `build` copia `evidence` en cada orden (112 órdenes; los 7 fotogramas de la barra de duelo no la llevan).
- [x] `UI_ONLY_FACTS` saca `ranking` de `slim` y de `who_is_who`, así que el modelo no ve el ranking.

### Urgente: ya está en `main`

Estos dos problemas los provocó el ranking que agregó el motor, pero se arreglan en código de agentes.

- [ ] **`allowed_numbers` todavía ve el ranking.** `personalizer.py` (línea 83) la llama con el insight completo, así que las puntuaciones de los cinco jugadores cuentan como permitidas. Se comprobó en `main`: «L. Montaño sube con 2.5 puntos» pasa la validación, aunque Montaño tiene 2.3 y el 2.5 es de otro jugador.
  - Propuesta: mover `UI_ONLY_FACTS` de `narrator.py` a `checks.py` (narrator lo importaría de ahí) y quitar esos campos antes de juntar los números:

    ```python
    def allowed_numbers(insight, extra=None):
        facts = {k: v for k, v in insight["facts"].items() if k not in UI_ONLY_FACTS}
        base = numbers(json.dumps([{**insight, "facts": facts}, extra or {}], ensure_ascii=False))
        ...
    ```

  - Se probó en local y después se retiró, para no tocar el código de agentes: con el cambio, el 2.5 se rechaza, el 2.3 pasa, y ninguno de los 112 textos actuales de `m001` cambia de resultado. Las plantillas de `fallback.py` no usan el ranking, así que tampoco les afecta.
  - Test sugerido: tomar un `mvp_rank_change` de `m001`, escribir la puntuación de otro jugador del ranking y comprobar que `check_variant` la marca como número inventado.
  - Ya pasaba algo parecido con `evidence`: los `event_id` (1340, 1353…) cuentan como números permitidos.
- [ ] **`data/m001/overlays.json` no trae `data.ranking`.** Se generó antes de que el motor emitiera `ranking`, así que a sus 28 órdenes `mvp_update` les falta. Hay dos opciones:
  - Volver a correr `python -m baja_agents run`. Con la caché, solo se repiten las llamadas de los `mvp_rank_change`, si es que el payload cambió.
  - Copiar `facts.ranking` de cada insight en `data.ranking`, igual que hace `data_for`, sin tocar los textos. Se probó en local: las 28 órdenes quedan bien y cumplen el esquema.

### Pendiente del contrato v1.1

- [ ] Endpoint `POST /api/ask` con `chat.schema.json`. La pregunta de los kilómetros de Torres debe responder `not_tracked`, y «¿Quién va a ganar?» debe responder `no_prediction`.
- [ ] Orden `chat_answer` con `data` cuando el productor la ponga en pantalla.

### Detectado en la revisión

- [ ] **`chain_detail.action` viene en español libre** («pase que rompió 2 líneas», «recuperación»), así que en las variantes en inglés sale en español. Hay dos caminos:
  - Que el motor agregue un código (`pass`, `recovery`, `cross`, `shot`, `off_ball_run`) y `lines_broken` como número aparte. Es un cambio menor del contrato que puede hacer el integrante 1 si los tres lo aprueban.
  - Que el agente traduzca la acción, sin tocar el contrato.
- [ ] `agents/test_1_hi.py`, `test_2_narrator.py` y `test_3_tool.py` son prototipos del PR #1 que quedaron sueltos. Se pueden borrar o mover a `agents/scratch/`.

---

## 4. Lo que falta: integrante 3, interfaz

### Para conectarse al stream

- [ ] **Cliente WebSocket.** Todavía no existe: `web/` solo tiene tipos, tokens, props y textos.
  - URL: `wss://<app>.azurecontainerapps.io/ws`.
  - En local: `python -m baja_insights serve --speed 60` y `ws://localhost:8080/ws`.
- [ ] **Primera conexión con `from_t_s: 0`.** El servidor manda todas las órdenes ya vencidas desde el saque inicial. Solo hay que dibujar las que siguen vigentes (`show_at_s + duration_s > clock.t_s`). Las demás pueden ir a un historial o ignorarse.
- [ ] **`phase`.** `pre` nunca llega, porque el reloj arranca en el saque inicial. `half_time` llega en el segundo 2700 y durante la pausa del medio tiempo, con `period: 1`.
- [ ] **`stream_ended`.** No es una falla: el partido terminó y el latido sigue, así que no debe mostrar «Reconectando».
- [ ] **`server_error`.** Si la UI manda un mensaje que el servidor no entiende, llega este código, porque el esquema no tiene otro para eso. Si prefieres uno propio (`invalid_message`), se agrega al esquema y al servidor.

### Ajustes al contrato que conviene hacer

- [ ] La descripción de `subscribe` en `stream.schema.json` dice «reenvía las órdenes con `show_at_s ≥ from_t_s`», pero el servidor reenvía también las que estaban en pantalla. Habría que actualizar el texto.
- [ ] En `web/src/contracts/overlay.ts`, los campos siguen marcados `@proposed v1.1` aunque el contrato ya está aprobado.

### Para pintar

- [ ] **Media de la carta sin cambio.** Hay `card_change` donde `overall_from` y `overall_to` son iguales (70 → 70). La carta debería mostrar solo la media, sin flecha.
- [ ] **Carrera MVP sin datos.** Mientras el integrante 2 no actualice `data/m001/overlays.json`, las órdenes `mvp_update` no traen `data.ranking`. La UI debe verse bien sin él. Los demás campos v1.1 (`chain_detail`, `evidence` y la media de la carta) ya vienen.

---

## 5. Lo que falta: entre los tres

- [ ] Actualizar `mocks/overlays_sample.json` e `insights_sample.json` con un ejemplo de cada campo nuevo, y pasar `invisible_assist` del mock (o037 a o040) de texto a objeto.
  - Las cifras del mock están escritas a mano y no coinciden con lo que da el motor sobre los 50 eventos del mock, así que el ranking de ejemplo hay que escribirlo también a mano.
  - Para que cuadre con el resto del mock, puede salir del ranking de las 35:00 de `chat_tools_sample.json`.
- [ ] Decidir el camino para `chain_detail.action` (ver integrante 2).
