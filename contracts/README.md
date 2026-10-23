# Contratos de Baja-Insights, versión 1.0

Esta carpeta es la **fuente de verdad** de los formatos que se pasan entre las tres partes del sistema.

```
Generador ──eventos──▶ Motor ──insights──▶ Agentes ──órdenes de gráfico──▶ Interfaz
  (1)                    (1)  ◀─consultas─  Pregúntale (2)                    (3)
```

| Archivo | Qué valida | Lo produce | Lo consume |
| --- | --- | --- | --- |
| `event.schema.json` | Un evento del partido | Generador, integrante 1 | Motor, integrante 1 |
| `insight.schema.json` | Un insight del motor | Motor, integrante 1 | Agentes, integrante 2 |
| `overlay.schema.json` | Una orden de gráfico | Agentes, integrante 2 | Interfaz, integrante 3 |
| `../mocks/chat_tools_sample.json` | Definición y ejemplos de las funciones del chat | Motor, integrante 1 | Agente Pregúntale, integrante 2 |

Para validar cualquier archivo, JSON o JSONL:

```bash
python -m baja_insights validate mocks/insights_sample.json data/m001/events.jsonl
```

Desde JavaScript se pueden usar los mismos esquemas con [Ajv](https://ajv.js.org/) en modo 2020-12.

**Regla de cambios.** Un PR que toque esta carpeta necesita el visto bueno de los tres integrantes. Si el cambio rompe compatibilidad, sube la versión mayor, y si solo agrega campos, la menor. Cada cambio se anota en `docs/cambios-contrato-*.md`.

---

## Convenciones

- **Campo** de 105 × 68 m con el origen en la esquina inferior izquierda.
- **Dirección de ataque.** El local, Bahía FC, ataca siempre hacia x = 105, y el visitante hacia x = 0, en ambos tiempos.
- **Reloj continuo**, sin tiempo agregado. El segundo tiempo empieza en 45:00 con `period` 2. `t_s = minute · 60 + second`.
- **Posiciones:** POR, LD, LI, DFC, MCD, MC, ED, EI y DC.
- **Atributos de carta:** ritmo, disparo, vision, regate, defensa, fisico y sin_balon.
- **Posesión.** `possession_id` es del equipo con el balón. Las acciones defensivas (pressure, tackle, foul) llevan el id del rival. Una `recovery` abre posesión nueva.
- **Duelos.** Un evento por duelo. `outcome` se lee desde `player`, y `opponent` es obligatorio.
- **Goles.** Puntúa el `shot` con `outcome: "goal"`. El evento `goal` solo trae `scoreline` y `assist`.
- **Nombres** ficticios. Nada de marcas reales.

---

## Evento

Campos siempre presentes: `match_id`, `event_id`, `period`, `minute`, `second`, `t_s`, `type`, `team`, `player`, `position`, `start`, `end`, `outcome`, `speed_kmh`, `under_pressure`, `lines_broken` y `possession_id`.

| `type` | `outcome` | Campos extra |
| --- | --- | --- |
| `match_start` | — | `home`, `away` |
| `pass` | `complete`, `incomplete` | `receiver`, y `cross` opcional |
| `shot` | `goal`, `saved`, `off_target`, `blocked` | `xg` |
| `goal` | — | `assist`, que puede ser null, y `scoreline` |
| `recovery` | `won` | — |
| `tackle`, `duel` | `won`, `lost` | `opponent` |
| `pressure` | — | `target` |
| `foul` | — | `fouled` |
| `off_ball_run` | — | `dragged_defender` y `space_opened_m`, ambos pueden ser null |
| `substitution` | — | `player_in`, `player_out` |
| `half_time`, `match_end` | — | `scoreline` |
| `second_half_start` | — | — |

## Insight

Campos comunes: `insight_id`, `match_id`, `period`, `minute`, `second`, `t_s`, `type`, `priority` (de 0 a 1), `players`, `team`, `facts` y `evidence`, que es la lista de los `event_id` que lo respaldan.

`t_s` es cuándo ocurrió. En vivo, algunos insights se emiten hasta una posesión después, como los duelos y las cartas de Visión, porque esperan a saber en qué terminó la jugada.

| `type` | Campos clave de `facts` |
| --- | --- |
| `mvp_rank_change` | `player`, `from_rank`, `to_rank`, `mvp_score`, `trigger_event_id`, `leader` o `previous_leader`, `stats`, `expected_for_role`, y `card_change` opcional |
| `duel_state` | `player_a` (local), `player_b`, `bar` (de −1 a 1), `a_vs_role`, `b_vs_role`, `duels_won_a`, `duels_won_b`, `direct_duels`, `chances_created_a`, `chances_created_b`, `flipped` |
| `standout_milestone` | `player`, `position`, `profile` (`defensive` o `creative`), `stats`, `expected_for_role`, `vs_role`, `mvp_rank`, y `card_change` opcional |
| `card_upgrade` | `player`, `attribute`, `from`, `to`, `delta`, `reason`, `overall_from`, `overall_to`, más extras según la regla, como `pass_difficulty`, `led_to` o `space_opened_m` |
| `goal_chain` | `scoreline`, `scorer`, `assist`, `xg`, `duration_s`, `chain` (con `event_id`, `player`, `action`, `credit` y `t_s`, ordenada por tiempo y con créditos que suman 1), `invisible_assist` |
| `team_phase` | `label` (`control` o `pressure_shift`), `window`, y métricas según la etiqueta |
| `match_keys` | `scoreline`, `xg`, `possession_pct`, `keys` (por equipo, con `code`, `key` y `evidence`), `no_prediction: true` |
| `top3` | `final_scoreline`, `top3` (con `rank`, `player`, `team`, `position`, `mvp_score`, `why` y `key_events`) |
| `match_summary` | `final_scoreline`, `xg`, `possession_pct`, `goals`, `phases`, `story`, `who_really_won`, `who_really_won_basis` |

`card_change` tiene la forma `{attribute, from, to, delta, reason, overall_from, overall_to}`.

Ejemplos completos en `../mocks/insights_sample.json`, y un partido real en `../data/m001/insights.json`.

## Orden de gráfico

Campos: `overlay_id`, `match_id`, `source_insight` (null para los fotogramas de la barra de duelo), `period`, `show_at` en formato MM:SS, `show_at_s`, `duration_s`, `slot`, `mode` (`fan`, `analyst` o `all`), `language` (`es`, `en` o `all`), `type`, `title`, `text`, y `card` y `data` opcionales.

- **slot:** `top_right`, `lower_third`, `side_panel`, `bottom_bar`, `center` o `full_screen`.
- **type:** `mvp_update`, `duel_bar`, `standout_milestone`, `card_upgrade`, `goal_analysis`, `team_phase`, `match_keys`, `top3` o `chat_answer`.

La interfaz muestra una orden cuando el reloj llega a `show_at_s`, filtrando por el `mode` y el `language` elegidos. Las que tienen `all` se muestran siempre.

## Funciones del chat

Implementadas en `src/baja_insights/engine/tools.py` (`MatchQuery.dispatch(nombre, argumentos)`):

| Función | Devuelve |
| --- | --- |
| `get_match_state(at)` | Marcador, goles con su `event_id`, xG y posesión |
| `get_mvp_ranking(at, top)` | `{at, at_s, ranking: [{rank, player, team, position, mvp_score}]}` |
| `get_player_summary(player, at)` | Estadísticas, `expected_for_role`, `vs_role`, carta actual, `card_changes`, `key_events` y `not_tracked` |
| `get_duel(player_a, player_b, at)` | Misma forma que `duel_state.facts` |
| `get_team_phase(team, from, to)` | Posesión, precisión de pase, pases por minuto, tiros, xG, recuperaciones en campo rival y `def_action_height_m` |
| `get_goal_chain(goal_event_id)` | Misma forma que `goal_chain.facts` |

Si un dato no existe, la función responde con `error` (`player_not_found`, `goal_not_found`, etc.) o lo lista en `not_tracked`. El agente nunca debe completar esos huecos por su cuenta.
