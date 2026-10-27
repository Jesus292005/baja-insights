# Fórmulas del motor y del generador

Todo lo que el motor calcula es determinista. Los mismos eventos siempre producen los mismos insights. Todos los números ajustables están en `src/baja_insights/engine/params.py`. Si cambias uno, actualiza este documento en el mismo commit.

---

## 1. Dificultad del pase, de 0 a 1

```
dificultad = 0.30 · min(distancia / 40 m, 1)
           + 0.25 · bajo_presión
           + 0.25 · min(líneas_rotas / 2, 1)
           + 0.20 · clip(avance / 30 m, 0, 1)
```

`avance` es lo que el pase gana hacia la portería rival. Ejemplo: el pase de Salgado en el 34:12 mide 27.9 m, va bajo presión, rompe 2 líneas y avanza 26 m, así que su dificultad es **0.88**.

Un **pase progresivo** es un pase completo que avanza al menos 10 m.

## 2. Puntos por acción

| Acción | Puntos |
| --- | --- |
| Pase completo | 0.02 + 0.25 × dificultad |
| Pase fallado | −0.08 × (1 − dificultad). Fallar un pase difícil casi no resta |
| Pase clave, cuando el receptor remata en la misma posesión | +0.20 |
| Asistencia | +0.50 |
| Tiro | 0.05 + 0.60 × xG, más 0.05 si va a puerta |
| Gol | +1.00, contado en el `shot` y no en el evento `goal` |
| Recuperación | 0.20, más 0.15 si es en campo rival |
| Entrada ganada o perdida | +0.20 o −0.05 |
| Duelo ganado o perdido | +0.12 o −0.06, y el rival recibe lo contrario |
| Presión | +0.02, más 0.10 si su equipo recupera el balón (recuperación o entrada ganada) en los 5 s siguientes |
| Falta cometida o recibida | −0.10 o +0.03 |
| Desmarque | 0.05, más 0.02 × metros abiertos si arrastró a un defensa. Si la posesión termina en tiro suma 0.10, y si termina en gol suma 0.50 × min(metros / 10, 1) |

## 3. Comparación con el rol, `vs_role`, de −1 a 1

Para cada estadística del rol (duelos ganados, recuperaciones, pases progresivos y pases clave):

```
esperado = valor_por_90 del rol × minutos jugados / 90
término  = clip((real − esperado) / max(esperado, 1), −1, 2)
vs_role  = clip(promedio de los cuatro términos, −1, 1)
```

0 significa "justo lo que hace un jugador de ese rol en esos minutos". El piso de 1 en el denominador evita que al minuto 3 una sola acción dispare el valor. Los valores por rol están en `mocks/teams.json`, en `role_baselines_per_90`. Son el promedio por 90 minutos de cada posición en 60 partidos libres del generador (semillas 201 a 260), así que un jugador típico de su puesto queda cerca de 0. Si cambia el generador, hay que recalcularlos.

## 4. Puntaje MVP, de 0 a 10

```
ajustado  = puntos_acumulados + 5.0 · vs_role · min(minutos, 90) / 90
mvp_score = 10 · (1 − e^(−ajustado / 7.0))
```

Es acumulado, así que sube a lo largo del partido, y se satura cerca de 10 para que un partido extraordinario no rompa la escala; con la escala 7 el líder suele terminar entre 7 y 9. El ajuste por rol hace que un medio de contención que recupera mucho compita contra un delantero que remata mucho: en 40 partidos libres el MVP es un atacante la mitad de las veces, un mediocampista el 42% y un defensa el 8%. Los porteros no entran al ranking.

**Cuándo se emite `mvp_rank_change`:** solo cuando un jugador que participó en la jugada sube y entra al top 3, después del minuto 10, con al menos 10 minutos entre avisos del mismo jugador, salvo que llegue al primer lugar, y 3 minutos entre avisos de cualquiera. Si alguien sube porque otro bajó, no se avisa.

**Prioridad:** 0.45 + 0.04 × puestos subidos + 0.30 si llega al primer lugar, con un máximo de 0.95.

## 5. Duelos

Se siguen solos los duelos de banda: lateral derecho contra extremo izquierdo y lateral izquierdo contra extremo derecho. Cualquier otro par se puede consultar con `get_duel`.

```
bar = clip((vs_role_A − vs_role_B) / 2, −1, 1)
```

`A` es siempre el jugador local. Un valor positivo indica que gana el local.

El insight `duel_state` se emite al terminar la posesión en la que hubo un duelo directo, para poder contar la ocasión que generó. Entre dos avisos del mismo par pasan al menos 5 minutos, salvo que la barra cambie de signo (`flipped`). Solo cuenta como cambio de signo si la barra nueva queda al menos a 0.10 del cero, para no avisar cuando oscila alrededor del empate.

**Prioridad:** 0.35 + 0.20 × |bar| + 0.15 si se invirtió.

## 6. Hitos del destacado

Se activa una vez por jugador y por tiempo, con al menos 5 minutos entre hitos de cualquiera, cuando se cumplen tres condiciones:
- El jugador lleva al menos 20 minutos en cancha.
- Su `vs_role` es de 0.5 o más.
- Alcanza 5 recuperaciones, 5 duelos ganados o 3 pases clave.

El perfil es `defensive` si el umbral alcanzado es de recuperaciones o duelos, y entonces sube +2 en Defensa. Si no, es `creative` y sube +1 en Visión.

**Prioridad:** 0.5 + 0.45 × clip(vs_role, 0, 1).

## 7. Cartas

| Regla | Atributo | `reason_code` | `reason_params` |
| --- | --- | --- | --- |
| Pase completo con dificultad de 0.80 o más que rompe al menos 2 líneas | Visión +2 | `line_breaking_pass` | `lines`, `under_pressure` |
| Tercera recuperación en campo rival dentro de 10 minutos, y cada tercera después | Defensa +2 | `opp_half_recoveries` | `count`, `window_min` |
| Remate a puerta a 105 km/h o más | Disparo +1 | `shot_speed` | `speed_kmh` |
| 4 duelos ganados seguidos | Físico +1 | `duel_streak` | `count` |
| Desmarque que arrastró a un defensa y abrió 8 m o más en una jugada que terminó en gol | Sin balón +3 | `run_opened_goal` | `dragged_defender`, `dragged_position` |
| Desmarque que arrastró a un defensa y abrió 5 m o más en una jugada que terminó en remate sin gol | Sin balón +1 | `run_ended_in_shot` | `dragged_defender` |
| Desmarque a 30 km/h o más | Ritmo +1 | `run_speed` | `speed_kmh` |
| 2 regates (duelos ganados con el balón) en menos de 10 minutos | Regate +1 | `dribbles` | `count`, `window_min` |
| Hito del destacado | Defensa +2 o Visión +1 | `standout_defensive` o `standout_creative` | ninguno |

`reason` es el texto en español, con una cifra como máximo para que quepa en los textos de aficionado. `reason_code` y `reason_params` dicen lo mismo como datos, para que cada idioma escriba su propio texto (contrato v1.1).

Límites: el mismo atributo no sube dos veces en 10 minutos, gana como máximo +6 por partido y no pasa de 99. El `overall` es el promedio redondeado de los siete atributos.

Si el cambio ocurre en la misma jugada que un `mvp_rank_change` o un `standout_milestone` del mismo jugador, viaja dentro de ese insight como `card_change`. Si no, sale como `card_upgrade`. Los de Visión esperan al final de la posesión para incluir `led_to`.

**Prioridad de `card_upgrade`:** 0.5 + 0.1 × delta, con un máximo de 0.9.

## 8. Cadena del gol

Se toman las acciones del equipo que anotó dentro de la posesión del gol y se les asigna un peso:

| Acción | Peso |
| --- | --- |
| Recuperación o entrada ganada que inicia la jugada | 2.0 |
| Pase completo | 0.5 + 1.0 × líneas rotas + 0.5 si fue bajo presión + 1.0 si es la asistencia |
| Desmarque con arrastre de marca | 0.3 × metros abiertos, con un máximo de 3.5 |
| Remate | 2.5 |

Entran a la cadena las acciones con peso de 2.0 o más, y el remate siempre. El crédito es el peso normalizado, redondeado a centésimas y ajustado para que la suma sea exactamente 1.00. La cadena va ordenada por tiempo.

Cada eslabón lleva `action`, la etiqueta en español, y además `type`, `lines_broken` y `cross` (solo en centros), copiados del evento, para que cada idioma arme su propia etiqueta.

La **asistencia invisible** es el desmarque de la cadena cuyo autor no tocó el balón en esa posesión.

## 9. Fases de equipo

Se evalúan cada minuto sobre los últimos 10 minutos del mismo tiempo.

| Etiqueta | Condición |
| --- | --- |
| `control` | 62% de posesión o más, 85% de pases completos o más y al menos 30 pases en la ventana |
| `pressure_shift` | Solo en el segundo tiempo, con al menos 4 recuperaciones en campo rival en la ventana y al menos 2.5 veces el promedio por cada 10 minutos del primer tiempo |

Se emite una vez por equipo, etiqueta y tiempo.

La **posesión** se mide en tiempo de balón en juego. El tiempo entre dos eventos se asigna a la posesión en curso, hasta un máximo de 8 s; lo que pase de ese tope es balón parado (saques, celebraciones) y no cuenta para nadie. Cada posesión pertenece al equipo de su primera acción con balón.

**`def_action_height_m`** es el promedio de la distancia a la propia portería de las recuperaciones, entradas, presiones y duelos del equipo.

## 10. Claves del partido y resumen

`match_keys` sale en `half_time` con reglas fijas por equipo y conserva las dos más fuertes:
- `win_ball_high`: 4 o más recuperaciones en campo rival con menos del 50% de posesión.
- `more_bodies_in_box`: un tiro a puerta o ninguno.
- `keep_possession`: 55% de posesión o más.
- `win_flank`: perdió 2 de los últimos 3 duelos de banda.
- `create_danger`: se usa si no aplica ninguna de las anteriores.

Nunca predice el resultado, y `no_prediction` siempre es `true`.

`match_summary` dice quién generó más peligro según el xG frente a quién tuvo más la pelota. Las frases de `story` y `why` son plantillas en español con números reales. Los agentes las reescriben y traducen.

---

## 11. Generador

### Modelo de xG

```
xG = logística(−1.2 + 1.6 · ángulo − 0.09 · distancia − 0.4 · bajo_presión − 0.3 · tras_centro)
```

`ángulo` es la apertura de la portería vista desde el tiro, en radianes. A 6 m del centro da cerca de 0.50, en el punto penal 0.24 y a 25 m 0.05.

### Simulación de posesiones

En cada paso el rival puede presionar, con más probabilidad cuanto más arriba esté. Una presión puede convertirse en una **entrada** (más probable si quien presiona es defensa o contención), que si se gana le da el balón a su equipo sin evento de recuperación y si se pierde puede terminar en falta. Si no hay entrada, la presión puede recuperar el balón en el acto. También puede haber un duelo uno contra uno, un tiro desde el último tercio, una falta, un desmarque o un pase.

El pase elige un objetivo según la verticalidad del equipo y un receptor cercano a esa zona. La probabilidad de completarlo baja con su dificultad. Un pase fallado sale de la cancha la mitad de las veces, lo que provoca un saque sin recuperación. La otra mitad termina en una recuperación del rival. Desde el propio tercio, a veces el pase va **atrás al portero**; esos pases casi nunca se pierden (97%) y, si fallan, el balón sale de la cancha.

Quién presiona o recupera depende de la cercanía al balón, del rol (un medio de contención recupera más que un delantero) y de la forma del jugador según el guion.

Todas las tasas están en `GEN`, al inicio de `generator/simulate.py`:

| Tasa | Valor | Qué controla |
| --- | --- | --- |
| `tackle_attempt` | 0.20 | Una presión se vuelve entrada, por el factor de recuperación del rol |
| `tackle_win` | 0.60 | Entradas ganadas, antes de la forma en duelos |
| `foul_on_lost_tackle` | 0.20 | Una entrada perdida es falta |
| `shot_base` y `shot_slope` | 0.12 y 0.04 | Probabilidad de tiro por paso desde 83 m de avance, más 0.04 por metro más cerca |
| `foul` | 0.022 | Falta recibida por paso |
| `backpass` y `backpass_pressure` | 0.20 y 0.20 | Pase atrás al portero desde el propio tercio, más si hay presión |

### Realismo

`python -m baja_insights realism --seeds 30` mide los partidos libres (la tabla usa esas mismas 30 semillas) contra rangos aproximados de la Premier League, por equipo y partido salvo que se indique. `tests/test_realism.py` exige que los 40 primeros partidos libres caigan dentro de todos los rangos.

| Métrica | Antes del 23 de octubre | Ahora | Referencia |
| --- | --- | --- | --- |
| Goles por partido | 1.1 | 2.9 | 2.2 a 3.4 |
| Empates | 37% | 23% | 12% a 35% |
| Tiros | 6.8 | 11.3 | 9 a 16 |
| Tiros a puerta | 2.7 | 4.8 | 3 a 6 |
| xG | 0.58 | 1.47 | 1.0 a 1.8 |
| xG por tiro | 0.08 | 0.14 | 0.08 a 0.14 |
| Faltas | 5.7 | 10.5 | 8 a 14 |
| Entradas | 0 | 15 | 10 a 22 |
| Acciones del portero con balón | 9 | 24 | 20 a 50 |
| Titulares | 10.5 (Bahía jugaba con 10) | 11 | 11 |
| Pases | 455 | 424 | 350 a 600 |
| Precisión de pase | 82% | 83% | 75% a 88% |

### Guion

`scripts/m001.json` define tres cosas:
- Los **momentos clave**, tomados tal cual de `mocks/events_sample.json`.
- Las **fases** de cada equipo: precisión de pase, ritmo, presión y verticalidad por tramo de tiempo.
- La **forma** de algunos jugadores: multiplicadores para presionar, recuperar, recibir, romper líneas o ganar duelos.

Con `lock_scoreline` el marcador solo cambia en los momentos clave. Sin guion (`--script free`), los goles se sortean con el xG de cada tiro.

---

## 12. Partido de demo

El partido de demo es **m001 con la semilla 1387** (`DEMO_SEED` en `generator/simulate.py`).

**Desde el 27 de octubre de 2026 el guion solo fija las jugadas que inserta tal cual:** el 1-1 en el 17 y el 63 y la cadena del empate (recuperación de Cota, desmarque de Torres arrastrando a Cárdenas, pase de Salgado y remate de Ramírez). El análisis del gol, los avisos y el video dependen de ellas. Todo lo demás sale de la semilla y puede cambiar cuando cambia el generador: quién lidera la carrera del MVP, quién la gana, los duelos, las fases y el veredicto. Así el generador se puede mejorar sin buscar una semilla nueva cada vez.

`tests/test_demo_story.py` protege lo que se conserva: los goles, y que la cadena del 1-1 tenga los mismos jugadores, acciones y créditos que el mock, con la asistencia invisible de Torres y las coordenadas para dibujarla.
