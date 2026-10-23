# Cambios al contrato, de v0 a v1

**Para aprobar el jueves 22 en la noche.** Cada punto ya está aplicado en `mocks/`, en los esquemas de `contracts/` y en el motor. El commit "Contrato v1" muestra el diff exacto contra los mocks originales.

Si alguien no está de acuerdo con un punto, lo comenta en el PR o en el chat del equipo antes de dormir. Lo que nadie objete queda como contrato.

Quién se ve afectado: **1** motor, **2** agentes, **3** interfaz.

---

## Cambios que rompen compatibilidad

Revísenlos primero, porque obligan a renombrar campos en el código que ya tengan.

| # | Cambio | Por qué | Afecta |
| --- | --- | --- | --- |
| 1 | `score` como marcador pasa a llamarse **`scoreline`** en eventos (`goal`, `half_time`, `match_end`) y en los insights `goal_chain` y `match_keys`. `final_score` pasa a **`final_scoreline`** en `top3`, `match_summary` y `teams.json` | `score` significaba dos cosas, el marcador y el puntaje MVP | 1, 2, 3 |
| 2 | El puntaje MVP se llama **`mvp_score`** en `mvp_rank_change`, `top3` y en las órdenes `mvp_update` y `top3` (`data.mvp_score` y `data.cards[].mvp_score`) | Mismo motivo | 1, 2, 3 |
| 3 | `avg_line_height_m` pasa a **`def_action_height_m`** y `avg_line_height_first_half_m` a **`def_action_height_first_half_m`** en `team_phase` y en sus órdenes | Los eventos solo traen al jugador con balón, así que la altura de la línea defensiva no se puede calcular. Lo honesto es medir la altura media de las acciones defensivas del equipo, en metros desde su propia portería | 1, 2, 3 |
| 4 | Los insights `mvp_rank_change` y `standout_milestone` agrupan sus números en **`stats`** y **`expected_for_role`** en lugar de campos sueltos. Por ejemplo, `recoveries` pasa a `stats.recoveries` y `role_expected_recoveries_so_far` pasa a `expected_for_role.recoveries` | Misma forma en todos los tipos y en `get_player_summary`, así el narrador y el chat leen los datos igual | 1, 2 |
| 5 | Las funciones del chat devuelven **la misma forma que los `facts` del insight** correspondiente. `get_goal_chain` devuelve la cadena con `event_id`, `action` y `credit`, no una lista de nombres. `get_mvp_ranking` devuelve `{at, at_s, ranking: [...]}` | El integrante 2 programa contra una sola forma de datos | 1, 2 |

## Cambios que agregan campos

No rompen nada, solo hay que empezar a usarlos.

| # | Cambio | Por qué | Afecta |
| --- | --- | --- | --- |
| 6 | Campo **`t_s`** (segundo del partido, `minute * 60 + second`) en eventos e insights | Ordenar y comparar tiempos sin convertir. Las órdenes ya tenían `show_at_s` | 1, 2, 3 |
| 7 | **`card_change`** opcional dentro de `mvp_rank_change` y `standout_milestone` | Las órdenes `mvp_update` y `standout_milestone` de los mocks mostraban una carta que sube, pero ese cambio no venía en ningún insight, así que el agente lo habría tenido que inventar. Ahora siempre viene del motor | 1, 2 |
| 8 | `card_upgrade` y `card_change` incluyen **`overall_from`** y **`overall_to`**. El `overall` es el promedio redondeado de los siete atributos y se recalcula en cada cambio | La interfaz sabe si la media de la carta cambia | 1, 3 |
| 9 | `goal_chain` agrega **`assist`** y **`t_s`** por cada eslabón de la cadena | La interfaz anima la cadena en orden y el narrador nombra al asistente | 1, 2, 3 |
| 10 | `duel_state` agrega **`direct_duels`**, **`chances_created_a`** y `flipped` siempre presente | Completar la comparación para el narrador | 1, 2 |
| 11 | `standout_milestone` agrega **`profile`** con valor `defensive` o `creative`, y quita el campo `note` de texto libre | El motor no escribe frases. El narrador decide cómo contarlo a partir del perfil | 1, 2 |
| 12 | Cada clave de `match_keys` agrega un **`code`** fijo como `win_ball_high` o `keep_possession` | El agente de personalización puede traducir por código en lugar de por frase | 1, 2 |
| 13 | `match_summary` agrega **`goals`**, **`phases`** y **`who_really_won_basis`**, con el líder en xG, el líder en posesión y el MVP | El veredicto "quién ganó realmente" queda respaldado por datos | 1, 2 |
| 14 | `card_upgrade` de visión agrega **`led_to_event_id`** junto a `led_to` | Citar la jugada real | 1, 2 |
| 15 | Nueva función del chat **`get_match_state(at)`** con marcador, goles con su `event_id`, xG y posesión | El agente necesitaba saber qué goles existen antes de llamar a `get_goal_chain` | 1, 2 |
| 16 | `get_player_summary` agrega **`not_tracked`**, la lista de datos que el sistema no mide, como la distancia recorrida | El chat responde "no lo sé" con base en datos y no por omisión | 1, 2 |
| 17 | El parámetro **`at`** de las funciones acepta `"63:09"`, `"63"` o segundos | Comodidad para el modelo | 2 |

## Convenciones que se aclaran

| # | Convención | Afecta |
| --- | --- | --- |
| 18 | **Duelos y entradas.** Un solo evento por duelo. `player` es el protagonista y `outcome` se lee desde su punto de vista, con `won` o `lost`, y `opponent` es obligatorio. El generador emite el duelo desde quien lo ganó | 1 |
| 19 | **Posesión.** `possession_id` pertenece al equipo con el balón. Las acciones defensivas (`pressure`, `tackle`, `foul`) llevan el `possession_id` del rival. Una `recovery` abre una posesión nueva para quien recupera | 1 |
| 20 | **Goles.** El gol suma puntos en el `shot` con `outcome: "goal"`. El evento `goal` solo trae el marcador y la asistencia y no suma puntos, para no contar el gol dos veces | 1 |
| 21 | **`possession_change` desaparece** de los tipos de evento. Los cambios de posesión ya se leen en `possession_id` | 1 |
| 22 | **Desmarques sin balón.** Pasan al núcleo solo para las jugadas guionizadas del partido de demo. El generador los emite y el motor solo lee `dragged_defender` y `space_opened_m`. El resto del sistema no depende de ellos | 1, 2, 3 |

## Números de los mocks que cambiaron

Ahora todos salen de las fórmulas de `docs/formulas.md`, así que el motor real y los mocks coinciden.

| Dónde | Antes | Ahora | Motivo |
| --- | --- | --- | --- |
| Barra del duelo Mena-Verdugo en i01 y o001 a o004 | -0.35 | -0.50 | `bar = (a_vs_role - b_vs_role) / 2` |
| Barra del duelo en i08 y o025 a o028 | 0.15 | 0.10 | Misma fórmula |
| Dificultad del pase de Salgado en i06, o018 y o020 | 0.82 | 0.88 | Fórmula de dificultad |
| Crédito del gol 0-1 en i02 y o005 a o008 | 0.15, 0.35, 0.25, 0.25 | 0.20, 0.30, 0.25, 0.25 | Fórmula de crédito |
| Cadena del gol 1-1 en i11 y o037 a o040 | Salgado antes que Torres, Torres 30% | Ordenada por tiempo, con Cota, Torres, Salgado y Ramírez. Torres 25% | El desmarque fue antes del pase y el crédito sale de la fórmula |
| Prioridades de i04, i05, i08, i12 e i13 | 0.6, 0.85, 0.55, 0.7, 0.5 | 0.61, 0.83, 0.52, 0.8, 0.49 | Fórmulas de prioridad |
| Top 3, Cota en i14, o046 y o048 | "9 recuperaciones, el doble de lo esperado" | "9 recuperaciones, 2 más de lo esperado para su rol" | Lo esperado para un MCD son 7, así que 9 no es el doble |
| Recuperaciones esperadas de Torres en i05 | 0.9 | 0.94 | 2.5 por 90 minutos × 33.7 minutos |
| Motivo de la carta de Salgado en i06 | "dos líneas" | "2 líneas" | El motor escribe los números con dígitos |

---

## Checklist de aprobación

- [ ] Integrante 1
- [ ] Integrante 2
- [ ] Integrante 3
