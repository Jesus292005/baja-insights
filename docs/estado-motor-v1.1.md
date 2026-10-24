# Motor v1.1: cambios hechos y lo que falta

Rama `motor-v1.1`, del integrante 1 (motor y stream). Va sobre `main` después del PR #3, que aprobó el contrato v1.1.

---

## Lo que se hizo

### 1. Ranking en `mvp_rank_change` (cambio 1 del contrato)

- Cada `mvp_rank_change` trae `facts.ranking` con el top 5 del MVP. Cada fila tiene `rank`, `player`, `team`, `position` y `mvp_score`, igual que `get_mvp_ranking`.
- Las dos salen de la misma función, `PlayerState.ranking_rows`, así que no pueden divergir. El tamaño del top está en `MVP_RANKING_TOP` de `params.py`.
- El ranking se calcula justo después del evento que provocó el cambio. Si en ese mismo segundo hay otro evento, `get_mvp_ranking` puede dar una décima distinta. Por ejemplo, a las 34:45 Montaño tiene 6.2 en el insight y 6.3 en el chat.
- Se regeneraron `data/m001/insights.json` y `data/free-seed2/insights.json`. Solo cambia `facts.ranking`: los demás insights quedan idénticos.

### 2. Servicio de stream (cambio 7)

- Se arranca con `python -m baja_insights serve --data data --port 8080 --speed 60`. Los detalles están en `docs/stream.md`.
- Sigue `contracts/stream.schema.json`: `subscribe`, `state`, `overlay`, `clock` y `error`, todos con `kind`.
- **Reloj.** Hay uno por partido, compartido por todos los espectadores. Arranca con el primer `subscribe`. Con `--half-time-pause` se detiene en 45:00 en fase `half_time`.
- **Marcador.** Sale solo de los eventos `goal`, `half_time` y `match_end`.
- **Envío.** Cada orden llega justo en su `show_at_s`, aunque la velocidad sea alta. El `clock` sale una vez por segundo real. `stream_ended` se manda una vez al terminar, y el latido sigue.
- **Reconexión.** Se reenvían las órdenes con `show_at_s + duration_s > from_t_s`, así que también vuelven los gráficos que estaban en pantalla cuando se cortó la conexión.
- **Infraestructura.** No usa dependencias fuera de la biblioteca estándar. Incluye `GET /healthz` y `stream.Dockerfile` para Azure Container Apps. Debe correr con una sola réplica.

### 3. Herramientas y contratos

- `python -m baja_insights validate` reconoce mensajes de stream (y valida la orden dentro de cada `overlay`) y peticiones y respuestas de chat.
- `contract_version` pasa a `"1.1"` en `mocks/teams.json`, `mocks/chat_tools_sample.json` y `CONTRACT_VERSION`.
- `tests/test_contracts.py` ahora valida `data/m001/overlays.json` y los archivos de `free-seed2`.

### Cómo se verificó

- Pasan 51 tests: 18 nuevos (3 del ranking y 15 del stream) y los 33 anteriores.
- Se grabó un partido completo por el WebSocket. Llegaron las 119 órdenes de `m001`, cada una una vez y en orden, con el marcador 0-1 en el 1060, el medio tiempo y el 1-1 en el 3789. Los 129 mensajes validan con `stream.schema.json`.
- Los pasos de la CI pasan: los mocks y los datos validan, y los eventos e insights de `m001` se regeneran idénticos.
- Las plantillas de los agentes siguen pasando `check_variant` con los insights nuevos.
- **No se pudo probar aquí:** la imagen Docker, porque no hay daemon, y la suite de agentes, porque falta `agent_framework`. El comando del contenedor sí se probó con solo `src/` y `data/`.

---

## Lo que falta: integrante 2, agentes

El PR #4 (`agents-001`) ya resuelve buena parte. Se revisó combinado con esta rama: se mezcla sin conflictos.

### Ya resuelto en el PR #4

- [x] `card_for` copia `overall_from`, `overall_to` y `reason`.
- [x] `data_for` copia `ranking` en `mvp_update` (cuando el motor lo emite) y `chain_detail` en `goal_analysis`.
- [x] `build` copia `evidence` en cada orden.
- [x] `UI_ONLY_FACTS` saca `ranking` de `slim` y de `who_is_who`, así que el modelo no ve el ranking.

### Urgente, al hacer merge de los dos PR

- [ ] **`allowed_numbers` todavía ve el ranking.** `personalizer.py` (línea 83) la llama con el insight completo, así que las puntuaciones de los cinco jugadores cuentan como permitidas. Se comprobó con los dos PR combinados: «L. Montaño sube con 2.5 puntos» pasa la validación, aunque Montaño tiene 2.3 y el 2.5 es de otro jugador.
  - Solución: filtrar `UI_ONLY_FACTS` también en `checks.allowed_numbers`.
  - Ya pasaba algo parecido con `evidence`: los `event_id` (1340, 1353…) cuentan como números permitidos.
- [ ] **Regenerar `data/m001/overlays.json` después de los dos merge.** El del PR #4 se generó con el motor de `main`, que aún no emite `ranking`, así que ninguna de sus órdenes `mvp_update` trae `data.ranking`. Si `UI_ONLY_FACTS` también se filtra en `allowed_numbers`, la caché sigue sirviendo.

### Pendiente del contrato v1.1

- [ ] Endpoint `POST /api/ask` con `chat.schema.json`. La pregunta de los kilómetros de Torres debe responder `not_tracked`, y «¿Quién va a ganar?» debe responder `no_prediction`.
- [ ] Orden `chat_answer` con `data` cuando el productor la ponga en pantalla.

### Detectado en la revisión

- [ ] **`chain_detail.action` viene en español libre** («pase que rompió 2 líneas», «recuperación»), así que en las variantes en inglés saldría en español. Hay dos caminos:
  - Que el motor agregue un código (`pass`, `recovery`, `cross`, `shot`, `off_ball_run`) y `lines_broken` como número aparte. Es un cambio menor del contrato, y lo puedo hacer yo si lo aprueban.
  - Que el agente traduzca la acción, sin tocar el contrato.
- [ ] `agents/test_1_hi.py`, `test_2_narrator.py` y `test_3_tool.py` son prototipos del PR #1 que quedaron sueltos. Se pueden borrar o mover a `agents/scratch/`.

---

## Lo que falta: integrante 3, interfaz

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
- [ ] **Estados vacíos.** Mientras los agentes no copien los campos nuevos, las órdenes de `data/m001/overlays.json` no traen `ranking`, `chain_detail`, `evidence` ni la media de la carta. La UI debe verse bien sin ellos.

---

## Lo que falta: entre los tres

- [ ] Actualizar `mocks/overlays_sample.json` e `insights_sample.json` con un ejemplo de cada campo nuevo, y pasar `invisible_assist` del mock (o037 a o040) de texto a objeto.
  - Las cifras del mock están escritas a mano y no coinciden con lo que da el motor sobre los 50 eventos del mock, así que el ranking de ejemplo hay que escribirlo también a mano.
  - Para que cuadre con el resto del mock, puede salir del ranking de las 35:00 de `chat_tools_sample.json`.
- [ ] Decidir el camino para `chain_detail.action` (ver integrante 2).
