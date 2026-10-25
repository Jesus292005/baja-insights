# Mocks v1.1 y texto de `subscribe`: qué cambió y qué necesita cada quien

Rama `motor/mocks-v1.1`, del integrante 1, sobre `main` en el PR #20 (`308f10d`). Cierra las dos tareas de contrato que seguían abiertas:

- «Actualizar los mocks con un ejemplo de cada campo nuevo», que era tarea de los tres.
- El texto de `subscribe` en `stream.schema.json`.

**Toca `mocks/` y `contracts/`, así que necesita el visto bueno de Diego y de luismar antes del merge** (ver `CONTRIBUTING.md`).

---

## Qué no cambia

- **Ni `src/`, ni `agents/`, ni `web/`, ni `data/`.** Los datos de `m001` siguen congelados para el video.
- **Ningún esquema cambia de forma.** En `stream.schema.json` solo cambia el texto de una `description`. Todo lo que validaba antes sigue validando.
- **El stream en Azure no se toca.** `baja-stream` sigue en `sha-7048698` y `baja-chat` en `sha-623edcc`.
  - El merge va a publicar una imagen nueva de `baja-chat`, porque su workflow se dispara con cambios en `mocks/` y `contracts/`.
  - No hace falta desplegarla: el chat no lee ningún archivo de los que cambiaron.

---

## Qué cambió

### 1. `mocks/insights_sample.json`

- Los tres `mvp_rank_change` (`i04`, `i05` e `i13`) traen ahora `facts.ranking`, con el top 5.
- Las cifras están escritas a mano, como el resto del mock, porque no salen del motor corriendo sobre los 50 eventos del mock:
  - El ranking de `i05` (33:40) coincide con `get_mvp_ranking` a las 35:00 en `chat_tools_sample.json`: Torres 6.2, Rosas 5.9 y Salgado 5.1.
  - El de `i13` (78:22) lleva al top 3 final: Torres, Cota y Rosas.
  - En cada uno, el jugador del insight aparece con su `to_rank` y su `mvp_score`.
- Lo demás de v1.1 ya estaba en este mock desde `motor-realism`: `evidence`, `overall_from` y `overall_to`, `reason_code` y `reason_params`, `type`, `lines_broken` y `cross` en la cadena, e `invisible_assist` como objeto.

### 2. `mocks/overlays_sample.json`

Antes no tenía ningún campo v1.1. Ahora cada orden copia del insight lo mismo que copia `agents/baja_agents/overlays.py`:

| Campo v1.1 | Órdenes del mock |
| --- | --- |
| `evidence` | Todas las que tienen `source_insight`. Los fotogramas de la barra de duelo no lo llevan, igual que en `data/m001` |
| `data.ranking` | `mvp_update`: `o013` a `o016` |
| `data.chain_detail` | `goal_analysis`: `o005` a `o008` (0-1) y `o037` a `o040` (1-1) |
| `data.invisible_assist` como objeto | `o037` a `o040`, con `player`, `dragged_defender`, `space_opened_m` y `touched_ball`. **Antes era el texto `"J. Torres"`** |
| `card.overall_from`, `overall_to`, `reason`, `reason_code` y `reason_params` | Las cartas de `o013` a `o024` y de `o041` a `o044` |
| Orden `chat_answer` con `data` | **Nueva, `o054`**, a las 35:00 en `side_panel`, en modo `fan` y en español |

Sobre la orden `chat_answer` nueva:

- Es la respuesta de «¿Por qué Torres va primero?» de `chat_tools_sample.json`.
- `data` lleva `question`, `status: "answered"`, `tools` (`get_mvp_ranking` y `get_player_summary`) y `evidence` (`739`, `642` y `531`).
- Se comprobó contra `chat_answer_order` de los agentes con la misma respuesta. Todo coincide, incluida la duración de 17 s, menos el `overlay_id`: los agentes usan `chat-<hash>` y el mock sigue con su numeración `oNNN`.

Ahora el mock tiene 54 órdenes en lugar de 53.

### 3. Texto de `subscribe` en `contracts/stream.schema.json`

Antes decía que el servidor reenvía «las órdenes con `show_at_s >= from_t_s`». El servidor siempre ha hecho algo un poco distinto: reenvía cada orden que **sigue en pantalla** en `from_t_s` o después, es decir, con `show_at_s + duration_s > from_t_s`. Así vuelve un gráfico que estaba en pantalla cuando se cortó la conexión.

Ahora el esquema dice eso. También se ajustaron las líneas que lo repetían en `docs/stream.md` y `docs/cambios-contrato-v1.1.md`.

### 4. Pendientes marcados como hechos

- `docs/cambios-contrato-v1.1.md`: la tarea de los mocks («Los tres»).
- `docs/estado-motor-v1.1.md`: la de los mocks y la del texto de `subscribe`.

---

## Diego (integrante 2, agentes)

**Nada obligatorio. Tus pruebas dan lo mismo antes y después del cambio.**

- [ ] **Revisar y aprobar el PR.**

Por qué no te afecta:

- `test_agents.py` lee `insights_sample.json`.
- El `ranking` nuevo está en `UI_ONLY_FACTS`, así que `allowed_numbers` no lo cuenta como cifra permitida y las plantillas siguen pasando `check_variant`.
- `test_ranking_stays_out_of_the_agents_view` sigue pasando aunque `i05` ya traiga su propio ranking, porque `slim` lo quita.

Opcional:

- `test_v11_fields_are_copied_from_the_insight` puede usar el ranking que ya trae `i05` en lugar de la constante `RANKING`.

## luismar (integrante 3, interfaz)

Ahora puedes desarrollar con el mock todas las piezas v1.1 sin abrir `data/m001`.

- [ ] **Revisar y aprobar el PR.**
- [ ] **`invisible_assist` ahora es un objeto en el mock.** Si `web/` lo leía como texto, toma el nombre de `invisible_assist.player`.
  - El esquema todavía acepta el texto, pero está marcado como obsoleto para v2. Los agentes siempre mandan el objeto.
- [ ] **Carrera MVP.** Dibuja `data.ranking` de `o013` a `o016`. Si una `mvp_update` no lo trae (órdenes v1), muestra solo `rank` y `mvp_score`.
- [ ] **Cadena del gol.** `data.chain_detail` trae cada eslabón con `event_id`, `player`, `action`, `credit`, `t_s`, `type` y `lines_broken`, más `cross` en el centro de Montaño (`o005` a `o008`). Las reglas para escribir la etiqueta en cada idioma están en la sección 5 de `docs/cambios-motor-realismo.md`.
- [ ] **Media de la carta.** En todas las cartas del mock, `overall_from` es igual a `overall_to` (68 → 68 o 70 → 70), así que es el caso de mostrar solo la media, sin flecha. Para ver una media que sí cambia, usa `data/m001/overlays.json`.
- [ ] **Motivo de la carta.** Hay un ejemplo de cada uno: `opp_half_recoveries` (`o013`), `line_breaking_pass` (`o017`), `standout_defensive` (`o021`) y `run_opened_goal` (`o041`). Úsalos para los textos por idioma en `web/src/i18n/strings.ts`, con `reason` de respaldo.
- [ ] **Chat en pantalla.** `o054` es una `chat_answer` lista para dibujar. Las respuestas en vivo de `POST /api/chat-overlay` tienen la misma forma.
- [ ] **Al reconectar al stream.** Después de un `subscribe` pueden llegar órdenes con `show_at_s` menor que el `from_t_s` que mandaste: son las que seguían en pantalla.
  - Dibuja solo las vigentes (`show_at_s + duration_s > clock.t_s`).
  - Si ya tienes una orden con el mismo `overlay_id`, no la repitas.

## Jesús (integrante 1, motor)

- [ ] Subir la rama y abrir el PR cuando esté revisada.
- [ ] Avisar en el chat del equipo con el enlace.
- [ ] Hacer el merge cuando los dos aprueben y la CI esté en verde.

---

## Cómo se verificó

Sobre esta rama:

- **Validación.** `python -m baja_insights validate` da OK en los seis archivos que revisa la CI: `mocks/events_sample.json`, `insights_sample.json`, `overlays_sample.json`, `data/m001/events.jsonl`, `insights.json` y `overlays.json`.
- **Pruebas del motor.** Pasan los 65 tests de `tests/`, incluidos `test_contracts.py` y `test_demo_story.py`, que comparan el mock con `m001`.
- **Pruebas de los agentes.** Se corrieron `agents/tests/test_agents.py` y `test_chat_answer.py` antes y después del cambio, con los mismos resultados.
  - Las pruebas que leen el mock pasan en los dos casos.
  - Cuatro pruebas no se pudieron correr fuera de la CI, porque necesitan `tmp_path` y `monkeypatch` de pytest, Agent Framework y `aiohttp`. Ninguna lee los archivos que cambiaron.
